"""Member photos and organisation logos: read ``web/media`` and copy it into the site.

The images are fetched outside the build (``scripts/fetch_member_photos.py`` for the APH
portraits, ``web/scripts/import-logos.mjs`` for the logos) and committed with
``web/media/media.json``, which records each file's sha256, source, licence and credit. The
build only reads that folder: it checks every listed file against its sha256, copies it to
``media/<kind>/<id>.<sha8>.<ext>`` (cached for a year, like ``assets/``) and returns the hrefs
for the pages, ``data/media.json`` (the explorer graph) and the credits on the about page.
No network (ADR-W2).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .bundle import dumps, write

MEDIA_DIR = "media"
SAFE_ID = re.compile(r"^[a-z0-9_]+$")
EXTS = {".jpg", ".png", ".webp"}
KINDS = {"photos": ("member_id", "p"), "logos": ("entity_id", "l")}


class MediaError(ValueError):
    """A media.json entry that does not match its file (exit 2)."""


@dataclass
class Media:
    photos: Dict[str, dict] = field(default_factory=dict)   # member_id -> entry + "href"
    logos: Dict[str, dict] = field(default_factory=dict)    # entity_id -> entry + "href"

    def photo(self, member_id: str) -> Optional[str]:
        e = self.photos.get(member_id)
        return e["href"] if e else None

    def logo(self, entity_id: str) -> Optional[str]:
        e = self.logos.get(entity_id)
        return e["href"] if e else None


def _entries(doc: dict, kind: str) -> List[dict]:
    rows = doc.get(kind) or []
    if not isinstance(rows, list):
        raise MediaError(f"media.json: {kind} must be a list")
    return rows


def copy_media(media_dir: Optional[Path], stage: Path, member_ids: Iterable[str],
               entity_ids: Iterable[str]) -> Media:
    """Copy the photos of ``member_ids`` and the logos of ``entity_ids`` that ``media_dir``
    holds into ``stage/media/`` and write ``stage/data/media.json``. Entries for ids not in the
    dataset are skipped (the test fixture is a subset). ``media_dir`` None: no images."""
    out = Media()
    if media_dir is not None:
        doc = json.loads((media_dir / "media.json").read_text(encoding="utf-8"))
        wanted = {"photos": set(member_ids), "logos": set(entity_ids)}
        for kind, (key, short) in KINDS.items():
            target = out.photos if kind == "photos" else out.logos
            for e in sorted(_entries(doc, kind), key=lambda r: r.get(key, "")):
                ident = e.get(key, "")
                if not SAFE_ID.match(ident):
                    raise MediaError(f"media.json: unsafe {key} {ident!r}")
                if ident not in wanted[kind]:
                    continue
                src = media_dir / e["file"]
                if src.suffix not in EXTS or not src.is_file():
                    raise MediaError(f"media.json: {e['file']} is missing or not an image")
                data = src.read_bytes()
                if hashlib.sha256(data).hexdigest() != e["sha256"]:
                    raise MediaError(f"media.json: sha256 of {e['file']} does not match")
                rel = f"{MEDIA_DIR}/{short}/{ident}.{e['sha256'][:8]}{src.suffix}"
                write(stage, rel, data)
                target[ident] = {**e, "href": "/" + rel}
    write(stage, "data/media.json", dumps({
        "members": {k: v["href"] for k, v in sorted(out.photos.items())},
        "entities": {k: v["href"] for k, v in sorted(out.logos.items())},
    }))
    return out


__all__ = ["Media", "MediaError", "copy_media", "MEDIA_DIR"]
