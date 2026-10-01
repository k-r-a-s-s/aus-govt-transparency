"""Single resolver for the Gemini model id (ADR-5).

Every Gemini call site (the extractor, and Phase 3's long-tail entity LLM) must obtain its
model id from :func:`resolve_gemini_model`. Precedence: explicit argument (``--model``) >
``GEMINI_MODEL`` environment variable > :data:`DEFAULT_GEMINI_MODEL`.

Gemini generations 0-2 are banned regardless of where the id came from (the older Flash
models are shut down or about to be), so any id matching ``^gemini-[0-2]\\.`` raises.

This module never loads ``.env.local``; the CLI does that (see ``extract_gemini.main``).
"""
from __future__ import annotations

import os
import re
from typing import Mapping, Optional

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
BANNED_RE = re.compile(r"^gemini-[0-2]\.")
API_KEY_ENV_VARS = ("GOOGLE_API_KEY", "GEMINI_API_KEY")


def resolve_gemini_model(explicit: Optional[str] = None, env: Optional[Mapping[str, str]] = None) -> str:
    """Return the Gemini model id to use; raise ValueError for a banned or empty id."""
    env = os.environ if env is None else env
    if explicit is not None and explicit.strip():
        model, source = explicit, "argument (--model)"
    elif env.get("GEMINI_MODEL", "").strip():
        model, source = env["GEMINI_MODEL"], "GEMINI_MODEL environment variable"
    else:
        model, source = DEFAULT_GEMINI_MODEL, "default"
    model = model.strip()
    if model.startswith("models/"):
        model = model[len("models/"):]
    if not model:
        raise ValueError(f"empty Gemini model id from {source}")
    if BANNED_RE.match(model):
        raise ValueError(
            f"Gemini model {model!r} (from {source}) is banned: Gemini 0.x-2.x models are shut "
            f"down or retiring (ADR-5). Use a gemini-3.x or newer id, e.g. {DEFAULT_GEMINI_MODEL!r}."
        )
    return model


def resolve_api_key(env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """GOOGLE_API_KEY, falling back to GEMINI_API_KEY; None if neither is set."""
    env = os.environ if env is None else env
    for name in API_KEY_ENV_VARS:
        value = env.get(name, "").strip()
        if value:
            return value
    return None
