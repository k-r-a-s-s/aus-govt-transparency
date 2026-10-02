"""OpenRouter transport for the ``gemini-api`` extractor (ADR-5, added 2026-10-02).

OpenRouter exposes an OpenAI-compatible ``POST /api/v1/chat/completions``. The PDF chunk is
sent as a ``file`` content part (a ``data:application/pdf;base64,…`` URL) with the
``file-parser`` plugin pinned to the ``native`` engine, so the model reads the pages itself
(64% of the corpus pages have no text layer; a text-extraction engine would see nothing).
Output is constrained with ``response_format: {"type": "json_schema", "strict": true}`` and
``provider.require_parameters`` so OpenRouter only routes to endpoints that honour the schema.
Request shape verified against https://openrouter.ai/docs (PDF inputs, structured outputs,
provider routing) and live on 2026-10-02.

Transport-level facts learned on the live probe:
- OpenAI ``openai/*`` models reject ``temperature``; it is omitted for them.
- A specific endpoint tier is chosen with ``provider.order`` (e.g. ``google-ai-studio/flex``
  is Gemini at half price, slower; ``:batch`` is a separate async API and is not used).
- ``usage.include: true`` makes the response carry ``usage.cost`` (USD), which the extractor
  reports instead of the Gemini price table; ``completion_tokens`` already includes reasoning.
- ``finish_reason`` is normalised by OpenRouter to ``stop | length | content_filter | error |
  tool_calls``; ``length`` maps onto the extractor's ``MAX_TOKENS`` re-split rule.

Model ids are OpenRouter ids (``google/gemini-3.8-flash``, ``openai/gpt-6-luna``,
``anthropic/claude-sonnet-5.5``). Gemini ids still pass through
:func:`disclosures.gemini_model.resolve_gemini_model` (the 0.x–2.x ban applies).
"""
from __future__ import annotations

import base64
import copy
import json
import os
import re
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import httpx

from .gemini_model import resolve_gemini_model

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY_ENV_VARS = ("OPENROUTER_KEY", "OPENROUTER_API_KEY")
NO_TEMPERATURE_PREFIXES = ("openai/",)
RETRYABLE_STATUS = {408, 429}  # plus every 5xx
DEFAULT_TIMEOUT_S = 600.0
APP_TITLE = "aus-govt-transparency disclosures v2"
FINISH_MAP = {"stop": "STOP", "length": "MAX_TOKENS"}


def resolve_openrouter_key(env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """OPENROUTER_KEY, falling back to OPENROUTER_API_KEY; None if neither is set."""
    env = os.environ if env is None else env
    for name in API_KEY_ENV_VARS:
        value = env.get(name, "").strip()
        if value:
            return value
    return None


def resolve_openrouter_model(explicit: Optional[str] = None,
                             env: Optional[Mapping[str, str]] = None) -> str:
    """OpenRouter model id. No argument -> ``google/`` + the resolved Gemini id (so
    ``GEMINI_MODEL`` and the default still apply). A Gemini id, bare or ``google/``-prefixed,
    goes through :func:`resolve_gemini_model` (banned generations raise). Anything else is
    passed through unchanged (``openai/gpt-6-luna``, ``anthropic/claude-sonnet-5.5``, ...)."""
    env = os.environ if env is None else env
    if explicit is None or not explicit.strip():
        return "google/" + resolve_gemini_model(None, env=env)
    m = explicit.strip()
    if m.startswith("google/"):
        return "google/" + resolve_gemini_model(m[len("google/"):], env=env)
    if m.startswith("gemini-") or m.startswith("models/gemini-"):
        return "google/" + resolve_gemini_model(m, env=env)
    if "/" not in m:
        raise ValueError(f"OpenRouter model id {m!r} must be '<vendor>/<model>' (e.g. openai/gpt-6-luna)")
    return m


def default_source_id(provider: str, model: str) -> str:
    """``gemini-api`` for any Gemini model (either transport); ``openrouter-<model>`` otherwise,
    so each bake-off arm lands in its own ``extractions/<source_id>/`` tree."""
    if provider == "gemini" or model.startswith("google/gemini-"):
        return "gemini-api"
    slug = re.sub(r"[^a-z0-9.]+", "-", model.split("/", 1)[-1].lower()).strip("-")
    return f"openrouter-{slug}"


def strict_schema(schema: dict) -> dict:
    """Copy of ``schema`` with ``additionalProperties: false`` on every object, which OpenAI-
    and Anthropic-style strict modes require (every property is already in ``required``)."""
    s = copy.deepcopy(schema)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node.setdefault("additionalProperties", False)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(s)
    return s


class OpenRouterError(Exception):
    """A non-success response from OpenRouter (HTTP status or an ``error`` body)."""

    def __init__(self, code: Optional[int], message: str, metadata: Any = None):
        super().__init__(message)
        self.code = code
        self.metadata = metadata

    def __str__(self) -> str:
        meta = ""
        if self.metadata:
            try:
                meta = " " + json.dumps(self.metadata)[:300]
            except (TypeError, ValueError):
                meta = f" {self.metadata!r}"[:300]
        return f"{self.code} {self.args[0]}{meta}"


class OpenRouterBackend:
    """``generate(chunk_pdf_bytes, text, label, retry) -> CallResult`` over OpenRouter.

    ``http`` is an ``httpx.Client`` (tests inject one with ``httpx.MockTransport``).
    ``provider_order`` pins endpoints (``["google-ai-studio/flex"]``) with fallbacks disabled.
    ``ignore_providers`` becomes ``provider.ignore`` (slugs OpenRouter must skip, e.g. ``["azure"]``).
    """

    name = "openrouter"

    def __init__(self, api_key: str, model: str, *, http: Optional[httpx.Client] = None,
                 provider_order: Optional[Sequence[str]] = None,
                 ignore_providers: Optional[Sequence[str]] = None,
                 reasoning_effort: Optional[str] = None, temperature: Optional[float] = 0.0,
                 max_tokens: int = 65536, response_schema: Optional[dict] = None,
                 timeout_s: float = DEFAULT_TIMEOUT_S, url: str = OPENROUTER_URL):
        if response_schema is None:
            from .extract_gemini import response_schema as _rs

            response_schema = _rs()
        self.api_key = api_key
        self.model = model
        self.http = http or httpx.Client(timeout=httpx.Timeout(timeout_s, connect=30.0))
        self.provider_order = list(provider_order) if provider_order else None
        self.ignore_providers = list(ignore_providers) if ignore_providers else None
        self.reasoning_effort = reasoning_effort
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.schema = strict_schema(response_schema)
        self.url = url

    # -- request ---------------------------------------------------------------------------
    def build_request(self, chunk: bytes, text: str, filename: str) -> Dict[str, Any]:
        data_url = "data:application/pdf;base64," + base64.b64encode(chunk).decode("ascii")
        provider: Dict[str, Any] = {"require_parameters": True}
        if self.provider_order:
            provider["order"] = self.provider_order
            provider["allow_fallbacks"] = False
        if self.ignore_providers:
            provider["ignore"] = self.ignore_providers
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": [
                {"type": "file", "file": {"filename": filename, "file_data": data_url}},
                {"type": "text", "text": text},
            ]}],
            "plugins": [{"id": "file-parser", "pdf": {"engine": "native"}}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "extraction", "strict": True, "schema": self.schema}},
            "max_tokens": self.max_tokens,
            "provider": provider,
            "usage": {"include": True},
        }
        if self.temperature is not None and not self.model.startswith(NO_TEMPERATURE_PREFIXES):
            body["temperature"] = self.temperature
        if self.reasoning_effort:
            body["reasoning"] = {"effort": self.reasoning_effort}
        return body

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                "X-OpenRouter-Title": APP_TITLE}

    def _post(self, body: dict) -> dict:
        resp = self.http.post(self.url, json=body, headers=self._headers())
        try:
            data = resp.json()
        except ValueError:
            data = None
        if resp.status_code != 200:
            err = (data or {}).get("error") if isinstance(data, dict) else None
            if isinstance(err, dict):
                raise OpenRouterError(err.get("code", resp.status_code), str(err.get("message")), err.get("metadata"))
            raise OpenRouterError(resp.status_code, (resp.text or "")[:300])
        if not isinstance(data, dict):
            raise OpenRouterError(200, "response body is not a JSON object")
        if "error" in data:  # OpenRouter can report a provider error with HTTP 200
            err = data["error"] if isinstance(data["error"], dict) else {"message": str(data["error"])}
            code = err.get("code")
            raise OpenRouterError(code if isinstance(code, int) else 200, str(err.get("message")), err.get("metadata"))
        return data

    # -- retry policy ------------------------------------------------------------------------
    @staticmethod
    def is_retryable(exc: Exception) -> bool:
        if isinstance(exc, httpx.TransportError):  # timeouts, connection resets, ...
            return True
        if isinstance(exc, OpenRouterError):
            c = exc.code
            return isinstance(c, int) and (c in RETRYABLE_STATUS or 500 <= c < 600)
        return False

    # -- call ---------------------------------------------------------------------------------
    def generate(self, chunk: bytes, text: str, label: str, retry: Callable[[Callable[[], Any]], Any]):
        from .extract_gemini import BackendError, CallResult

        body = self.build_request(chunk, text, "chunk.pdf")
        try:
            data = retry(lambda: self._post(body))
        except OpenRouterError as exc:
            raise BackendError(exc.code, str(exc)) from exc
        except httpx.HTTPError as exc:
            raise BackendError(None, f"{type(exc).__name__}: {exc}") from exc
        choices = data.get("choices") or []
        if not choices:
            raise BackendError(200, f"no choices in response: {json.dumps(data)[:300]}")
        choice = choices[0]
        if isinstance(choice.get("error"), dict):
            e = choice["error"]
            raise BackendError(e.get("code"), f"{e.get('message')} {json.dumps(e.get('metadata'))[:300]}")
        content = (choice.get("message") or {}).get("content")
        if isinstance(content, list):  # some providers return content parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        fr = choice.get("finish_reason")
        finish = None if fr is None else FINISH_MAP.get(str(fr).lower(), str(fr).upper())
        u = data.get("usage") or {}
        cost = u.get("cost")
        return CallResult(text=content or "", finish_reason=finish,
                          input_tokens=int(u.get("prompt_tokens") or 0),
                          output_tokens=int(u.get("completion_tokens") or 0),
                          cost_usd=float(cost) if isinstance(cost, (int, float)) else None,
                          provider=data.get("provider"), native_finish_reason=choice.get("native_finish_reason"))
