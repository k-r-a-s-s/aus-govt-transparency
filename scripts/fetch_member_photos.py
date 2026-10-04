"""Fetch every member's official portrait from the Parliament of Australia into ``web/media``.

Run by hand when members change (network; never part of ``web build``, which makes no network
calls, ADR-W2):

    python scripts/fetch_member_photos.py [--media web/media] [--only member_id,...]

Reads ``<media>/aph_ids.csv`` (member_id -> APH parliamentarian ID, from Wikidata P10020 with
the ambiguous names resolved by hand; see its ``how`` column), downloads
``https://www.aph.gov.au/api/parliamentarian/<aph_id>/image`` to ``<media>/photos/<member_id>.jpg``
byte for byte (no resizing or re-encoding: the photos are CC BY-NC-ND 4.0, so the file is
published as received and only cropped at display time by CSS/canvas), and rewrites the
``photos`` list in ``<media>/media.json`` with source, licence, credit and sha256 per photo.
APH serves a small PNG placeholder for a parliamentarian without a photo; that is recorded as
missing, not saved.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

IMAGE_URL = "https://www.aph.gov.au/api/parliamentarian/{}/image"
PAGE_URL = "https://www.aph.gov.au/Senators_and_Members/Parliamentarian?MPID={}"
LICENCE = "CC BY-NC-ND 4.0"
LICENCE_URL = "https://creativecommons.org/licenses/by-nc-nd/4.0/"
CREDIT = "Parliament of Australia"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
      "Version/17.0 Safari/605.1.15 aus-interests-media/1.0 (+https://interests.kevinrassool.com)")


def load_media(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"media_version": 1, "photos": [], "logos": []}


def save_media(path: Path, doc: dict) -> None:
    doc["photos"].sort(key=lambda r: r["member_id"])
    doc["logos"].sort(key=lambda r: r["entity_id"])
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")


def get(url: str, tries: int = 3) -> tuple[bytes, str]:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise AssertionError("unreachable")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--media", default="web/media", help="media folder (default: %(default)s)")
    p.add_argument("--only", default="", help="comma-separated member ids to (re)fetch")
    a = p.parse_args(argv)
    media = Path(a.media)
    only = {x for x in a.only.split(",") if x}
    rows = list(csv.DictReader((media / "aph_ids.csv").open(encoding="utf-8")))
    doc = load_media(media / "media.json")
    keep = {r["member_id"]: r for r in doc["photos"]}
    today = dt.date.today().isoformat()
    (media / "photos").mkdir(parents=True, exist_ok=True)
    missing = []
    for r in rows:
        mid, aph = r["member_id"], r["aph_id"]
        if only and mid not in only:
            continue
        data, ctype = get(IMAGE_URL.format(aph))
        if not data.startswith(b"\xff\xd8") or len(data) < 4000:
            missing.append((mid, aph, ctype, len(data)))
            keep.pop(mid, None)
            continue
        rel = f"photos/{mid}.jpg"
        (media / rel).write_bytes(data)
        keep[mid] = {
            "member_id": mid, "file": rel, "sha256": hashlib.sha256(data).hexdigest(),
            "aph_id": aph, "source_url": IMAGE_URL.format(aph),
            "source_page": PAGE_URL.format(aph), "licence": LICENCE, "licence_url": LICENCE_URL,
            "credit": CREDIT, "retrieved": today,
        }
        time.sleep(0.2)
    doc["photos"] = list(keep.values())
    save_media(media / "media.json", doc)
    print(f"fetch_member_photos: {len(doc['photos'])} photos in {media}/photos; "
          f"{len(missing)} without a photo")
    for m in missing:
        print("  no photo:", *m, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
