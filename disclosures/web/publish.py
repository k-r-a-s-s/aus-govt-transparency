"""``web publish-data`` (ADR-W6, AC-D3): stage the R2 data files and write the upload script.

Writes ``<out>/interests/<version>/`` and an identical ``<out>/interests/latest/`` holding
``metadata.R2_FILES``: the DB (copied byte for byte), the CSV (``export.fetch_rows`` +
``export.write_csv``, so byte-identical to ``python -m disclosures export``), its gzip, a gzipped
JSON Lines file (one object per item, published column names, null for empty), the README
(``export.render_readme``), a Frictionless ``datapackage.json`` and ``MANIFEST.json`` (sha256 and
size per file). Parquet only when ``pyarrow`` is importable.

It never uploads: the web package makes no network calls and starts no processes (ADR-W2,
``test_web_guard``). It writes ``<out>/cors.json`` and ``<out>/upload.sh`` (the ``wrangler r2
bucket cors set`` and ``wrangler r2 object put --remote`` commands, ``latest/`` last so it only
moves once the versioned copy is up) and prints them; run ``sh <out>/upload.sh`` from ``web/``.
Gzip output sets mtime 0, so the same DB gives the same bytes.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import shlex
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from .. import export
from .metadata import DATASET_NAME, LICENSE_URL, R2_FILES, dataset_description, dataset_version

BUCKET = "aus-interests-data"
PREFIX = "interests"
CORS = {"rules": [{
    "allowed": {"origins": ["*"], "methods": ["GET", "HEAD"], "headers": ["Range"]},
    "exposeHeaders": ["Content-Length", "Content-Range", "ETag"],
    "maxAgeSeconds": 86400,
}]}
CACHE = {"latest": "public, max-age=3600", "version": "public, max-age=31536000, immutable"}
FRICTIONLESS_TYPES = {"string": "string", "integer": "integer", "boolean": "boolean"}


class PublishError(Exception):
    """Bad input or an existing staging folder (exit 2)."""


def _gzip(src: Path, dst: Path) -> None:
    with src.open("rb") as f, dst.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as g:
            shutil.copyfileobj(f, g, 1 << 20)


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _jsonl_rows(rows: List[list]) -> bytes:
    types = {name: typ for name, typ, _ in export.COLUMNS}
    out = []
    for r in rows:
        obj = {}
        for name, v in zip(export.HEADER, r):
            obj[name] = None if v == "" else (bool(v) if types[name] == "boolean" else v)
        out.append(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    return ("\n".join(out) + "\n").encode("utf-8")


def datapackage(version: str, summary: dict) -> dict:
    return {
        "name": "australian-parliament-registers-of-interests",
        "title": DATASET_NAME,
        "description": dataset_description(summary),
        "version": version,
        "licenses": [{"name": "CC-BY-4.0", "path": LICENSE_URL, "title": "CC BY 4.0"}],
        "homepage": "https://interests.kevinrassool.com/",
        "resources": [{
            "name": "disclosures",
            "path": export.CSV_NAME,
            "format": "csv",
            "mediatype": "text/csv",
            "encoding": "utf-8",
            "schema": {"fields": [{"name": n, "type": FRICTIONLESS_TYPES.get(t, "string"),
                                   "description": d} for n, t, d in export.COLUMNS],
                       "primaryKey": "item_id"},
        }],
    }


def publish_data(db: str | Path, manifest: str | Path, out: str | Path,
                 version: str = "auto") -> dict:
    db, out = Path(db), Path(out)
    if not db.is_file():
        raise PublishError(f"{db} not found")
    if out.exists() and any(out.iterdir()):
        raise PublishError(f"{out} exists and is not empty")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        meta = dict(con.execute("select key, value from meta"))
        rows = export.fetch_rows(con, export.manifest_urls(Path(manifest)))
        n_items = con.execute("select count(*) from items").fetchone()[0]
        readme = export.render_readme(con, len(rows))
        summary = {
            "items": n_items,
            "statements": con.execute("select count(*) from documents").fetchone()[0],
            "members": con.execute("select count(distinct member_id) from items").fetchone()[0],
        }
    finally:
        con.close()
    if len(rows) != n_items:
        raise PublishError(f"export has {len(rows)} rows but items has {n_items}")
    version = dataset_version(meta) if version == "auto" else version

    vdir = out / PREFIX / version
    vdir.mkdir(parents=True)
    shutil.copyfile(db, vdir / export.DB_NAME)
    export.write_csv(rows, vdir / export.CSV_NAME)
    _gzip(vdir / export.CSV_NAME, vdir / (export.CSV_NAME + ".gz"))
    jsonl = vdir / "disclosures_v2.jsonl"
    jsonl.write_bytes(_jsonl_rows(rows))
    _gzip(jsonl, vdir / "disclosures_v2.jsonl.gz")
    jsonl.unlink()
    (vdir / "README.md").write_text(readme, encoding="utf-8")
    (vdir / "datapackage.json").write_text(json.dumps(datapackage(version, summary), indent=2)
                                           + "\n", encoding="utf-8")
    try:  # optional
        import pyarrow.csv
        import pyarrow.parquet as pq
        pq.write_table(pyarrow.csv.read_csv(vdir / export.CSV_NAME), vdir / "disclosures_v2.parquet")
    except ImportError:
        pass
    files = [{"name": name, "bytes": (vdir / name).stat().st_size, "sha256": _sha256(vdir / name),
              "media_type": media} for name, media, *_ in R2_FILES if (vdir / name).exists()]
    (vdir / "MANIFEST.json").write_text(json.dumps(
        {"dataset": DATASET_NAME, "version": version, "loaded_at": meta.get("loaded_at"),
         "rows": n_items, "files": files}, indent=2) + "\n", encoding="utf-8")
    shutil.copytree(vdir, out / PREFIX / "latest")

    media = {name: m for name, m, *_ in R2_FILES}
    (out / "cors.json").write_text(json.dumps(CORS, indent=2) + "\n", encoding="utf-8")
    cmds = [f"npx wrangler r2 bucket cors set {BUCKET} --file {shlex.quote(str(out / 'cors.json'))}"]
    for folder, cache in ((version, CACHE["version"]), ("latest", CACHE["latest"])):
        for name, m in media.items():
            p = out / PREFIX / folder / name
            if p.exists():
                cmds.append(f"npx wrangler r2 object put {BUCKET}/{PREFIX}/{folder}/{name} "
                            f"--remote --file {shlex.quote(str(p))} --content-type {shlex.quote(m)} "
                            f"--cache-control {shlex.quote(cache)}")
    script = out / "upload.sh"
    script.write_text("#!/bin/sh\n# Upload the staged data files to R2 (run from web/ so wrangler "
                      "reads web/.env).\nset -eu\n" + "\n".join(cmds) + "\n", encoding="utf-8")
    script.chmod(0o755)
    return {"version": version, "out": str(out), "files": files, "commands": cmds,
            "script": str(script)}


def run_publish(db, manifest, out: Optional[str], version: str, dry_run: bool) -> int:
    import tempfile

    out = out or tempfile.mkdtemp(prefix="aus-interests-data-")
    try:
        s = publish_data(db, manifest, out, version)
    except PublishError as e:
        print(f"web publish-data: {e}")
        return 2
    for c in s["commands"]:
        print(c)
    total = sum(f["bytes"] for f in s["files"])
    print(f"web publish-data: {s['version']}, {len(s['files'])} files ({total:,} bytes) staged in "
          f"{s['out']}/{PREFIX}/{{{s['version']},latest}}; nothing uploaded. "
          f"Upload: (cd web && sh {s['script']})" + (" [dry run]" if dry_run else ""))
    return 0


__all__ = ["publish_data", "run_publish", "PublishError", "BUCKET", "PREFIX", "CORS"]
