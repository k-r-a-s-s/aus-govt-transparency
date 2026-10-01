"""ADR-6 step 1 entity-name normalisation (shared by score and the entities pipeline)."""
from __future__ import annotations

import re
import unicodedata

# Multi-word suffixes first so "pty ltd" is removed as a unit.
LEGAL_SUFFIXES = (
    "pty ltd",
    "pty limited",
    "pty",
    "ltd",
    "limited",
    "inc",
    "plc",
    "nl",
    "corporation",
    "corp",
    "co",
)

# Full stops inside dotted acronyms are deleted ("A.N.Z." -> "anz", "B.H.P" -> "bhp"); any
# other full stop becomes a space ("Delta pty.ltd" -> "delta pty ltd"). Apostrophes are
# deleted ("Macy's" -> "macys"); all other punctuation becomes a space ("Hi-Fi" -> "hi fi").
_ACRONYM_RE = re.compile(r"(?<![^\W_])(?:[^\W\d_]\.)+[^\W\d_](?![^\W_])\.?")
_DELETE_RE = re.compile(r"['\u2019\u2018`]")
_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalise_entity(name: str | None) -> str:
    """NFKC, casefold, & -> and, strip punctuation, collapse whitespace,
    strip leading "the ", strip trailing legal suffixes repeatedly.

    "group", "holdings" and "bank" are deliberately kept.
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).casefold()
    s = s.replace("&", " and ")
    s = _ACRONYM_RE.sub(lambda m: m.group(0).replace(".", ""), s)
    s = _DELETE_RE.sub("", s)
    s = _PUNCT_RE.sub(" ", s).replace("_", " ")
    s = _WS_RE.sub(" ", s).strip()
    if s.startswith("the "):
        s = s[4:]
    unstripped = s
    changed = True
    while changed:
        changed = False
        for suffix in LEGAL_SUFFIXES:
            if s == suffix:
                continue  # never reduce a name to nothing
            if s.endswith(" " + suffix):
                s = s[: -len(suffix) - 1].rstrip()
                changed = True
                break
    if s != unstripped and s in LEGAL_SUFFIXES:
        return unstripped  # the name was only legal suffixes ("Pty Ltd"): keep it whole
    return s
