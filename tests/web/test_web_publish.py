"""AC-D3: ``web publish-data`` stages the R2 files for a version and ``latest/``, writes the
CORS JSON and the upload script, prints the commands, and uploads nothing. The CSV is
byte-identical to ``python -m disclosures export``'s."""
from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3

from web_support import MINI_DB, MINI_MANIFEST

from disclosures import export
from disclosures.cli import main
from disclosures.web import publish as P

NAMES = {"disclosures_v2.db", "disclosures_v2.csv", "disclosures_v2.csv.gz",
         "disclosures_v2.jsonl.gz", "README.md", "datapackage.json", "MANIFEST.json"}


def version():
    con = sqlite3.connect(f"file:{MINI_DB}?mode=ro", uri=True)
    loaded = dict(con.execute("select key, value from meta"))["loaded_at"]
    return f"v2.{loaded[:10]}"


def test_publish_data_dry_run(tmp_path, capsys):
    out = tmp_path / "data"
    assert main(["web", "publish-data", "--db", str(MINI_DB), "--manifest", str(MINI_MANIFEST),
                 "--version", "auto", "--out", str(out), "--dry-run"]) == 0
    printed = capsys.readouterr().out
    v = version()
    vdir, latest = out / "interests" / v, out / "interests" / "latest"
    assert {p.name for p in vdir.iterdir()} == NAMES
    for name in NAMES:  # latest mirrors the version
        assert (latest / name).read_bytes() == (vdir / name).read_bytes()
    assert (vdir / "disclosures_v2.db").read_bytes() == MINI_DB.read_bytes()

    # the CSV is export's CSV
    export.export(MINI_DB, tmp_path / "exp", MINI_MANIFEST)
    csv_bytes = (vdir / export.CSV_NAME).read_bytes()
    assert csv_bytes == (tmp_path / "exp" / export.CSV_NAME).read_bytes()
    assert gzip.decompress((vdir / "disclosures_v2.csv.gz").read_bytes()) == csv_bytes

    # JSON Lines: one object per CSV row, published names, null for empty
    lines = gzip.decompress((vdir / "disclosures_v2.jsonl.gz").read_bytes()).decode().splitlines()
    n = len(csv_bytes.decode().splitlines()) - 1
    assert len(lines) == n
    first = json.loads(lines[0])
    assert list(first) == export.HEADER and "" not in first.values()

    manifest = json.loads((vdir / "MANIFEST.json").read_text())
    assert manifest["version"] == v and manifest["rows"] == n
    for f in manifest["files"]:
        data = (vdir / f["name"]).read_bytes()
        assert f["bytes"] == len(data) and f["sha256"] == hashlib.sha256(data).hexdigest()
    assert {f["name"] for f in manifest["files"]} == NAMES - {"MANIFEST.json"}
    dp = json.loads((vdir / "datapackage.json").read_text())
    assert [x["name"] for x in dp["resources"][0]["schema"]["fields"]] == export.HEADER

    # commands: CORS, then every file into the version, then latest; nothing ran
    assert json.loads((out / "cors.json").read_text()) == P.CORS
    script = (out / "upload.sh").read_text()
    puts = [l for l in script.splitlines() if "r2 object put" in l]
    assert len(puts) == 2 * len(NAMES) and all("--remote" in l for l in puts)
    assert all(f"/interests/{v}/" in l for l in puts[:len(NAMES)])
    assert all("/interests/latest/" in l for l in puts[len(NAMES):])
    assert "r2 bucket cors set aus-interests-data" in script
    assert "nothing uploaded" in printed and printed.count("r2 object put") == len(puts)


def test_publish_data_is_deterministic(tmp_path):
    a = P.publish_data(MINI_DB, MINI_MANIFEST, tmp_path / "a")
    b = P.publish_data(MINI_DB, MINI_MANIFEST, tmp_path / "b")
    assert [(f["name"], f["sha256"]) for f in a["files"]] == [(f["name"], f["sha256"]) for f in b["files"]]


def test_publish_data_refuses_non_empty_out(tmp_path, capsys):
    (tmp_path / "x").write_text("keep")
    assert main(["web", "publish-data", "--db", str(MINI_DB), "--out", str(tmp_path)]) == 2
    assert (tmp_path / "x").read_text() == "keep"
