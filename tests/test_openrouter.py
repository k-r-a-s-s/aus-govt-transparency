"""OpenRouter transport for the extractor (ADR-5): mocked HTTP, no network (ADR-11)."""
import argparse
import base64
import io
import json
import re
from pathlib import Path

import httpx
import pymupdf
import pytest

from disclosures import extract_gemini as eg
from disclosures import openrouter as orr
from disclosures.validate import validate_file

from test_extract_gemini import chunk_doc, item, make_pdf, one_item_per_page

RANGE_RE = re.compile(r"pages (\d+)–(\d+) of a (\d+)-page PDF")


# --------------------------------------------------------------------------- helpers

def completion(data=None, *, text=None, finish="stop", tin=100, tout=50, cost=0.001, provider="Google AI Studio",
               native=None):
    return {
        "id": "gen-1", "provider": provider, "model": "x",
        "choices": [{"index": 0, "finish_reason": finish, "native_finish_reason": native or finish,
                     "message": {"role": "assistant", "content": text if text is not None else json.dumps(data)}}],
        "usage": {"prompt_tokens": tin, "completion_tokens": tout, "cost": cost,
                  "completion_tokens_details": {"reasoning_tokens": 0}},
    }


class FakeServer:
    """httpx.MockTransport handler: parses the chunk from the request and calls ``responder(start, end, n)``.
    The responder returns a completion dict, an int HTTP status (error), a dict with ``error`` (HTTP 200 error),
    or an Exception to raise (transport errors)."""

    def __init__(self, responder):
        self.responder = responder
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append((request, body))
        file_part, text_part = body["messages"][0]["content"]
        assert file_part["type"] == "file" and file_part["file"]["filename"] == "chunk.pdf"
        prefix = "data:application/pdf;base64,"
        assert file_part["file"]["file_data"].startswith(prefix)
        pdf = base64.b64decode(file_part["file"]["file_data"][len(prefix):])
        m = RANGE_RE.search(text_part["text"])
        assert m, "chunk preamble missing"
        start, end, total = map(int, m.groups())
        with pymupdf.open(stream=pdf, filetype="pdf") as d:
            assert d.page_count == end - start + 1
        r = self.responder(start, end, len(self.requests))
        if isinstance(r, Exception):
            raise r
        if isinstance(r, int):
            return httpx.Response(r, json={"error": {"code": r, "message": f"http {r}", "metadata": {"raw": "x"}}})
        return httpx.Response(200, json=r)


def backend(responder, model="google/gemini-3.8-flash", **kw):
    server = FakeServer(responder)
    b = orr.OpenRouterBackend("sk-test", model, http=httpx.Client(transport=httpx.MockTransport(server)), **kw)
    return b, server


def run(paths, b, **kw):
    out = io.StringIO()
    kw.setdefault("sleep", lambda s: None)
    kw.setdefault("now", lambda: "2026-10-02T00:00:00+00:00")
    kw.setdefault("source_id", orr.default_source_id("openrouter", b.model))
    kw.setdefault("out_root", f"extractions/{kw['source_id']}")
    res = eg.extract_pdfs(paths, backend=b, model=b.model, out=out, **kw)
    return res, out.getvalue()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


# --------------------------------------------------------------------------- request shape

def test_request_shape_matches_openrouter_docs():
    b, _ = backend(lambda s, e, n: completion(chunk_doc([])), provider_order=["google-ai-studio/flex"],
                   reasoning_effort="low")
    body = b.build_request(b"%PDF-1.4 fake", "hello", "chunk.pdf")
    assert body["model"] == "google/gemini-3.8-flash"
    file_part, text_part = body["messages"][0]["content"]
    assert file_part == {"type": "file", "file": {"filename": "chunk.pdf",
                         "file_data": "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.4 fake").decode()}}
    assert text_part == {"type": "text", "text": "hello"}
    assert body["plugins"] == [{"id": "file-parser", "pdf": {"engine": "native"}}]
    rf = body["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["name"] == "extraction" and rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["schema"] == orr.strict_schema(eg.response_schema())
    assert body["provider"] == {"require_parameters": True, "order": ["google-ai-studio/flex"], "allow_fallbacks": False}
    assert body["usage"] == {"include": True}
    assert body["temperature"] == 0.0 and body["max_tokens"] == eg.MAX_OUTPUT_TOKENS
    assert body["reasoning"] == {"effort": "low"}
    assert "key" not in json.dumps(body)


def test_no_provider_order_means_no_pin_and_openai_gets_no_temperature():
    b, _ = backend(lambda s, e, n: None, model="openai/gpt-6-luna")
    body = b.build_request(b"x", "t", "chunk.pdf")
    assert body["provider"] == {"require_parameters": True}
    assert "temperature" not in body and "reasoning" not in body
    b2, _ = backend(lambda s, e, n: None, model="anthropic/claude-sonnet-5.5")
    assert b2.build_request(b"x", "t", "chunk.pdf")["temperature"] == 0.0


def test_ignore_providers_becomes_provider_ignore():
    b, _ = backend(lambda s, e, n: None, model="anthropic/claude-sonnet-5.5", ignore_providers=["azure"])
    assert b.build_request(b"x", "t", "chunk.pdf")["provider"] == {"require_parameters": True, "ignore": ["azure"]}
    b2, _ = backend(lambda s, e, n: None, provider_order=["google-ai-studio/flex"], ignore_providers=[])
    assert "ignore" not in b2.build_request(b"x", "t", "chunk.pdf")["provider"]


def test_strict_schema_closes_every_object_and_keeps_required():
    s = orr.strict_schema(eg.response_schema())
    assert s["additionalProperties"] is False
    assert s["properties"]["items"]["items"]["additionalProperties"] is False
    assert s["required"] == eg.response_schema()["required"]
    assert "additionalProperties" not in eg.response_schema()  # the genai path is unchanged


def test_headers_carry_bearer_key_and_title(repo):
    rel = make_pdf(repo, "pdfs/45/a_45p.pdf", 2)
    b, server = backend(lambda s, e, n: completion(one_item_per_page(s, e)))
    run([rel], b)
    req, _ = server.requests[0]
    assert req.headers["authorization"] == "Bearer sk-test"
    assert req.headers["content-type"] == "application/json"
    assert req.url == httpx.URL(orr.OPENROUTER_URL)


# --------------------------------------------------------------------------- end to end

def test_end_to_end_writes_valid_file_with_model_and_source_id(repo):
    rel = make_pdf(repo, "pdfs/45/big_45p.pdf", 45)
    b, server = backend(lambda s, e, n: completion(one_item_per_page(s, e), tin=1000, tout=200, cost=0.01),
                        model="openai/gpt-6-luna")
    res, out = run([rel], b, workers=1)
    assert res.ok == [rel] and res.exit_code == 0
    dest = Path("extractions/openrouter-gpt-6-luna/house/45/big_45p.json")
    assert validate_file(dest, root=repo) == []
    doc = json.loads(dest.read_text())
    assert doc["source_id"] == "openrouter-gpt-6-luna" and doc["model"] == "openai/gpt-6-luna"
    assert len(doc["items"]) == 45 and [it["page"] for it in doc["items"]] == list(range(1, 46))
    assert doc["usage"] == {"input_tokens": 3000, "output_tokens": 600}
    assert res.usage.actual_cost_usd == pytest.approx(0.03) and res.usage.calls == 3
    assert "cost US$0.0300 (as reported by the provider)" in out and "est. cost" not in out
    ranges = [RANGE_RE.search(r[1]["messages"][0]["content"][1]["text"]).groups()[:2] for r in server.requests]
    assert ranges == [("1", "20"), ("21", "40"), ("41", "45")]


def test_gemini_via_openrouter_lands_in_gemini_api(repo):
    rel = make_pdf(repo, "pdfs/45/a_45p.pdf", 3)
    b, _ = backend(lambda s, e, n: completion(one_item_per_page(s, e)))
    res, _ = run([rel], b)
    doc = json.loads(Path("extractions/gemini-api/house/45/a_45p.json").read_text())
    assert doc["source_id"] == "gemini-api" and doc["model"] == "google/gemini-3.8-flash"


def test_length_finish_resplits_like_max_tokens(repo):
    rel = make_pdf(repo, "pdfs/45/a_45p.pdf", 8)

    def responder(s, e, n):
        if e - s + 1 > 4:
            return completion(text="{\"items\": [", finish="length", native="MAX_TOKENS")
        return completion(one_item_per_page(s, e))

    b, server = backend(responder)
    res, _ = run([rel], b)
    assert res.ok == [rel]
    ranges = [tuple(map(int, RANGE_RE.search(r[1]["messages"][0]["content"][1]["text"]).groups()[:2]))
              for r in server.requests]
    assert ranges == [(1, 8), (1, 4), (5, 8)]
    doc = json.loads(Path("extractions/gemini-api/house/45/a_45p.json").read_text())
    assert [it["page"] for it in doc["items"]] == list(range(1, 9))


def test_content_filter_finish_fails_pdf_without_resplit(repo):
    rel = make_pdf(repo, "pdfs/45/a_45p.pdf", 2)
    b, server = backend(lambda s, e, n: completion(chunk_doc([]), finish="content_filter", native="SAFETY"))
    res, _ = run([rel], b)
    assert "finish_reason CONTENT_FILTER (SAFETY)" in res.failed[rel] and len(server.requests) == 1
    assert not Path("extractions/gemini-api").exists()


def test_content_parts_list_is_joined(repo):
    rel = make_pdf(repo, "pdfs/45/a_45p.pdf", 1)
    doc = one_item_per_page(1, 1)
    c = completion(doc)
    c["choices"][0]["message"]["content"] = [{"type": "text", "text": json.dumps(doc)[:10]},
                                             {"type": "text", "text": json.dumps(doc)[10:]}]
    b, _ = backend(lambda s, e, n: c)
    res, _ = run([rel], b)
    assert res.ok == [rel]


# --------------------------------------------------------------------------- errors and retries

def test_429_and_5xx_and_timeouts_retried_then_success(repo):
    rel = make_pdf(repo, "pdfs/45/a_45p.pdf", 1)
    script = [429, 503, httpx.ReadTimeout("slow"), httpx.ConnectError("reset")]
    b, server = backend(lambda s, e, n: script.pop(0) if script else completion(one_item_per_page(s, e)))
    slept = []
    res, _ = run([rel], b, sleep=slept.append, max_retries=4)
    assert res.ok == [rel] and len(server.requests) == 5 and len(slept) == 4
    assert slept[0] < slept[1] < slept[2] < slept[3]  # exponential backoff
    assert res.usage.calls == 1  # only the successful call counts


def test_402_not_retried_and_message_includes_code(repo):
    rel = make_pdf(repo, "pdfs/45/a_45p.pdf", 1)
    b, server = backend(lambda s, e, n: 402)
    res, out = run([rel], b)
    assert len(server.requests) == 1
    assert "API error 402" in res.failed[rel] and "http 402" in res.failed[rel]
    assert "FAILED" in out and not Path("extractions").exists()


def test_http_200_with_error_body_is_an_api_error(repo):
    rel = make_pdf(repo, "pdfs/45/a_45p.pdf", 1)
    b, server = backend(lambda s, e, n: {"error": {"code": 404, "message": "No endpoints found", "metadata": {}}})
    res, _ = run([rel], b)
    assert "API error 404" in res.failed[rel] and "No endpoints found" in res.failed[rel]
    assert len(server.requests) == 1


def test_retries_exhausted_reports_last_error(repo):
    rel = make_pdf(repo, "pdfs/45/a_45p.pdf", 1)
    b, server = backend(lambda s, e, n: 500)
    res, _ = run([rel], b, max_retries=2)
    assert len(server.requests) == 3 and "API error 500" in res.failed[rel]


def test_is_retryable():
    assert orr.OpenRouterBackend.is_retryable(orr.OpenRouterError(429, "x"))
    assert orr.OpenRouterBackend.is_retryable(orr.OpenRouterError(502, "x"))
    assert orr.OpenRouterBackend.is_retryable(httpx.ReadTimeout("x"))
    assert not orr.OpenRouterBackend.is_retryable(orr.OpenRouterError(402, "x"))
    assert not orr.OpenRouterBackend.is_retryable(orr.OpenRouterError(400, "x"))
    assert not orr.OpenRouterBackend.is_retryable(ValueError("x"))


# --------------------------------------------------------------------------- workers

def test_workers_run_pdfs_concurrently_with_same_result(repo):
    rels = [make_pdf(repo, f"pdfs/45/w{i}_45p.pdf", 3) for i in range(6)]
    rels.append("pdfs/45/missing_45p.pdf")
    b, _ = backend(lambda s, e, n: completion(one_item_per_page(s, e), cost=0.002))
    res, out = run(rels, b, workers=4)
    assert sorted(res.ok) == sorted(rels[:6]) and list(res.failed) == ["pdfs/45/missing_45p.pdf"]
    assert res.exit_code == 1 and res.usage.calls == 6 and res.usage.actual_cost_usd == pytest.approx(0.012)
    assert out.count("ok      pdfs/45/w") == 6 and "6 ok, 1 failed, 0 skipped" in out
    for r in rels[:6]:
        assert validate_file(Path(f"extractions/gemini-api/house/45/{Path(r).stem}.json"), root=repo) == []


# --------------------------------------------------------------------------- model / source id resolution

def test_resolve_openrouter_model():
    assert orr.resolve_openrouter_model(None, env={}) == "google/gemini-3.8-flash"
    assert orr.resolve_openrouter_model(None, env={"GEMINI_MODEL": "gemini-3.7-flash"}) == "google/gemini-3.7-flash"
    assert orr.resolve_openrouter_model("gemini-3.8-flash", env={}) == "google/gemini-3.8-flash"
    assert orr.resolve_openrouter_model("google/gemini-3.8-flash", env={}) == "google/gemini-3.8-flash"
    assert orr.resolve_openrouter_model("openai/gpt-6-luna", env={}) == "openai/gpt-6-luna"
    assert orr.resolve_openrouter_model("anthropic/claude-sonnet-5.5", env={"GEMINI_MODEL": "x"}) == "anthropic/claude-sonnet-5.5"
    with pytest.raises(ValueError, match="banned"):
        orr.resolve_openrouter_model("google/gemini-2.5-flash", env={})
    with pytest.raises(ValueError, match="banned"):
        orr.resolve_openrouter_model("gemini-2.0-flash", env={})
    with pytest.raises(ValueError, match="vendor"):
        orr.resolve_openrouter_model("gpt-6-luna", env={})


def test_default_source_id():
    assert orr.default_source_id("gemini", "gemini-3.8-flash") == "gemini-api"
    assert orr.default_source_id("openrouter", "google/gemini-3.8-flash") == "gemini-api"
    assert orr.default_source_id("openrouter", "openai/gpt-6-luna") == "openrouter-gpt-6-luna"
    assert orr.default_source_id("openrouter", "anthropic/claude-sonnet-5.5") == "openrouter-claude-sonnet-5.5"


def test_resolve_openrouter_key():
    assert orr.resolve_openrouter_key({}) is None
    assert orr.resolve_openrouter_key({"OPENROUTER_KEY": " k "}) == "k"
    assert orr.resolve_openrouter_key({"OPENROUTER_API_KEY": "k2"}) == "k2"


# --------------------------------------------------------------------------- CLI

def ns(**kw):
    base = dict(source="gemini", provider="auto", model=None, provider_order=None, reasoning_effort=None,
                source_id=None, out_root=None, chunk_pages=20, max_retries=0, workers=1, force=False, batch=False,
                pdfs=["pdfs/45/a_45p.pdf"])
    base.update(kw)
    return argparse.Namespace(**base)


def test_cli_auto_picks_openrouter_when_key_set(repo, capsys):
    rel = make_pdf(repo, "pdfs/45/a_45p.pdf", 2)
    server = FakeServer(lambda s, e, n: completion(one_item_per_page(s, e)))
    http = httpx.Client(transport=httpx.MockTransport(server))
    assert eg.run(ns(provider_order="google-ai-studio/flex", workers=2), env={"OPENROUTER_KEY": "k"}, http=http) == 0
    out = capsys.readouterr().out
    assert "provider=openrouter model=google/gemini-3.8-flash endpoints=google-ai-studio/flex" in out
    assert server.requests[0][1]["provider"]["order"] == ["google-ai-studio/flex"]
    assert server.requests[0][0].headers["authorization"] == "Bearer k"
    assert validate_file(Path("extractions/gemini-api/house/45/a_45p.json"), root=repo) == []


def test_cli_openrouter_non_gemini_model_and_custom_out_root(repo, capsys):
    rel = make_pdf(repo, "pdfs/45/a_45p.pdf", 1)
    server = FakeServer(lambda s, e, n: completion(one_item_per_page(s, e)))
    http = httpx.Client(transport=httpx.MockTransport(server))
    args = ns(provider="openrouter", model="openai/gpt-6-luna", out_root="extractions/custom", reasoning_effort="high")
    assert eg.run(args, env={"OPENROUTER_KEY": "k", "GOOGLE_API_KEY": "g"}, http=http) == 0
    assert "source=openrouter-gpt-6-luna provider=openrouter model=openai/gpt-6-luna" in capsys.readouterr().out
    body = server.requests[0][1]
    assert "temperature" not in body and body["reasoning"] == {"effort": "high"}
    assert json.loads(Path("extractions/custom/house/45/a_45p.json").read_text())["source_id"] == "openrouter-gpt-6-luna"


def test_cli_openrouter_errors(repo, capsys):
    assert eg.run(ns(provider="openrouter"), env={}) == 2
    assert "OPENROUTER_KEY" in capsys.readouterr().err
    assert eg.run(ns(provider="openrouter", model="google/gemini-2.5-flash"), env={"OPENROUTER_KEY": "k"}) == 2
    assert "banned" in capsys.readouterr().err
    assert eg.run(ns(provider="auto"), env={}) == 2  # falls back to gemini: no key there either
    assert "no API key" in capsys.readouterr().err
    assert eg.run(ns(workers=0), env={"OPENROUTER_KEY": "k"}) == 2
    assert "--workers" in capsys.readouterr().err


def test_cli_parser_accepts_new_options():
    from disclosures.cli import build_parser

    a = build_parser().parse_args(["extract", "--source", "gemini", "--provider", "openrouter", "--model",
                                   "openai/gpt-6-luna", "--provider-order", "openai/flex", "--workers", "4",
                                   "--reasoning-effort", "low", "pdfs/45/a.pdf"])
    assert (a.provider, a.model, a.provider_order, a.workers, a.reasoning_effort) == \
        ("openrouter", "openai/gpt-6-luna", "openai/flex", 4, "low")
    assert a.out_root is None and a.source_id is None


# --------------------------------------------------------------------------- fallback model

def test_blocked_chunk_goes_to_fallback_model_and_is_recorded(repo):
    rel = make_pdf(repo, "pdfs/47/m_47p.pdf", 29)
    primary, pserver = backend(lambda s, e, n: completion(chunk_doc([]), finish="error", native="RECITATION")
                               if s == 21 else completion(one_item_per_page(s, e), cost=0.01))
    fb, fserver = backend(lambda s, e, n: completion(one_item_per_page(s, e), cost=0.1), model="anthropic/claude-sonnet-5.5")
    res, out = run([rel], primary, fallback=fb)
    assert res.ok == [rel]
    assert len(pserver.requests) == 2 and len(fserver.requests) == 1
    assert RANGE_RE.search(fserver.requests[0][1]["messages"][0]["content"][1]["text"]).groups()[:2] == ("21", "29")
    doc = json.loads(Path("extractions/gemini-api/house/47/m_47p.json").read_text())
    assert doc["model"] == "google/gemini-3.8-flash+anthropic/claude-sonnet-5.5"
    assert "pages 21-29: fallback anthropic/claude-sonnet-5.5 after primary google/gemini-3.8-flash returned finish_reason ERROR (RECITATION)" in doc["extraction_notes"]
    assert [it["page"] for it in doc["items"]] == list(range(1, 30))
    assert res.usage.calls == 3 and res.usage.actual_cost_usd == pytest.approx(0.111)  # the blocked call is counted too
    assert validate_file(Path("extractions/gemini-api/house/47/m_47p.json"), root=repo) == []


def test_no_fallback_keeps_old_behaviour_and_fallback_failure_is_reported(repo):
    rel = make_pdf(repo, "pdfs/47/m_47p.pdf", 3)
    primary, _ = backend(lambda s, e, n: completion(chunk_doc([]), finish="content_filter", native="SAFETY"))
    res, _ = run([rel], primary)
    assert "finish_reason CONTENT_FILTER (SAFETY)" in res.failed[rel]
    fb, _ = backend(lambda s, e, n: 402, model="openai/gpt-6-luna")
    res, _ = run([rel], primary, fallback=fb)
    assert "fallback openai/gpt-6-luna also failed" in res.failed[rel] and "API error 402" in res.failed[rel]
    assert not Path("extractions").exists()


def test_model_field_unchanged_when_fallback_configured_but_unused(repo):
    rel = make_pdf(repo, "pdfs/47/m_47p.pdf", 2)
    primary, _ = backend(lambda s, e, n: completion(one_item_per_page(s, e)))
    fb, fserver = backend(lambda s, e, n: completion(one_item_per_page(s, e)), model="openai/gpt-6-luna")
    run([rel], primary, fallback=fb)
    doc = json.loads(Path("extractions/gemini-api/house/47/m_47p.json").read_text())
    assert doc["model"] == "google/gemini-3.8-flash" and "fallback" not in doc["extraction_notes"]
    assert fserver.requests == []


def test_cli_fallback_model(repo, capsys):
    rel = make_pdf(repo, "pdfs/45/a_45p.pdf", 1)
    calls = []

    def responder(s, e, n):
        return completion(one_item_per_page(s, e))
    server = FakeServer(responder)
    http = httpx.Client(transport=httpx.MockTransport(server))
    assert eg.run(ns(provider="openrouter", fallback_model="anthropic/claude-sonnet-5.5"),
                  env={"OPENROUTER_KEY": "k"}, http=http) == 0
    assert "fallback=anthropic/claude-sonnet-5.5" in capsys.readouterr().out
    assert eg.run(ns(provider="gemini", fallback_model="x/y"), env={"GOOGLE_API_KEY": "g"}, client=object()) == 2
    assert "--fallback-model needs --provider openrouter" in capsys.readouterr().err
    assert eg.run(ns(provider="openrouter", fallback_model="google/gemini-2.5-flash"), env={"OPENROUTER_KEY": "k"}, http=http) == 2
    assert "banned" in capsys.readouterr().err


def test_cli_ignore_providers_reaches_primary_and_fallback(repo, capsys):
    rel = make_pdf(repo, "pdfs/47/m_47p.pdf", 2)
    server = FakeServer(lambda s, e, n: completion(chunk_doc([]), finish="error", native="RECITATION")
                        if n == 1 else completion(one_item_per_page(s, e)))
    http = httpx.Client(transport=httpx.MockTransport(server))
    args = ns(provider="openrouter", fallback_model="anthropic/claude-sonnet-5.5", ignore_providers="azure, ,deepinfra",
              pdfs=[rel])
    assert eg.run(args, env={"OPENROUTER_KEY": "k"}, http=http) == 0
    assert "ignore=azure,deepinfra " in capsys.readouterr().out
    (_, primary), (_, fallback) = server.requests
    assert primary["model"] == "google/gemini-3.8-flash" and fallback["model"] == "anthropic/claude-sonnet-5.5"
    assert primary["provider"]["ignore"] == fallback["provider"]["ignore"] == ["azure", "deepinfra"]
    from disclosures.cli import build_parser

    a = build_parser().parse_args(["extract", "--source", "gemini", "--ignore-providers", "azure", "pdfs/45/a.pdf"])
    assert a.ignore_providers == "azure"
