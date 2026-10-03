"""AC-A2: ``web make-fixture`` is deterministic; the committed fixture matches the v2 schema."""
from __future__ import annotations

import csv
import hashlib
import sqlite3

import pytest
from web_support import FIXTURE_DIR, MINI_DB, MINI_MANIFEST, REAL_DB, REAL_MANIFEST, needs_real, ro

from disclosures.cli import main

FIXTURE_IDS = ["ken_o_dowd", "russell_broadbent", "josh_wilson", "richard_colbeck",
               "nicolette_boele", "wayne_swan"]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _make(out):
    return main(["web", "make-fixture", "--db", str(REAL_DB), "--manifest", str(REAL_MANIFEST),
                 "--out", str(out), "--members", "6", "--seed", "1"])


@needs_real
def test_make_fixture_is_deterministic_and_matches_committed(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert _make(a) == 0
    assert _make(b) == 0
    for name in ("mini.db", "mini-manifest.csv"):
        assert sha(a / name) == sha(b / name), name
        assert sha(a / name) == sha(FIXTURE_DIR / name), f"committed {name} is stale"


@needs_real
def test_make_fixture_rejects_too_few_members(tmp_path):
    assert main(["web", "make-fixture", "--db", str(REAL_DB), "--manifest", str(REAL_MANIFEST),
                 "--out", str(tmp_path), "--members", "3"]) == 2


def test_committed_fixture_size():
    assert MINI_DB.stat().st_size <= 2_000_000
    assert MINI_MANIFEST.exists()


def _columns(con):
    out = {}
    for (t,) in con.execute("select name from sqlite_master where type='table' order by 1"):
        out[t] = [(r[1], r[2], r[3], r[5]) for r in con.execute(f"pragma table_info({t})")]
    return out


def _indexes(con):
    return sorted(r[0] for r in con.execute(
        "select name from sqlite_master where type='index' and name not like 'sqlite_%'"))


def test_fixture_matches_v2_loader_schema():
    from disclosures.load import DDL

    ref = sqlite3.connect(":memory:")
    ref.executescript(DDL)
    con = ro(MINI_DB)
    assert _columns(con) == _columns(ref)
    assert _indexes(con) == _indexes(ref)
    meta = dict(con.execute("select key, value from meta"))
    assert meta["fixture"] == "1"
    assert meta["schema_version"].startswith("2")
    assert con.execute("pragma integrity_check").fetchone()[0] == "ok"
    assert con.execute("pragma foreign_key_check").fetchall() == []


@needs_real
def test_fixture_schema_sql_equals_real_db():
    q = "select type, name, sql from sqlite_master where sql is not null order by name"
    assert ro(MINI_DB).execute(q).fetchall() == ro(REAL_DB).execute(q).fetchall()


def test_fixture_covers_the_required_shapes():
    from disclosures.web import urls as U

    con = ro(MINI_DB)
    assert sorted(r[0] for r in con.execute("select member_id from members")) == \
        sorted(FIXTURE_IDS)
    urls = {r["pdf_sha256"]: r["source_url"] for r in csv.DictReader(MINI_MANIFEST.open())}
    docs = con.execute("select pdf_sha256, chamber, parliament from documents").fetchall()
    assert len(urls) == len(docs) and all(d[0] in urls for d in docs)
    classes = {(U.classify(urls[s]), ch, p) for s, ch, p in docs}
    assert (U.HOUSE_REDIRECT, "house", 43) in classes
    assert (U.HOUSE_PDF, "house", 47) in classes
    assert (U.HOUSE_API, "house", 48) in classes
    assert (U.SENATE_JSON, "senate", 48) in classes
    owners = {r[0] for r in con.execute("select distinct owner from items")}
    assert {"self", "spouse", "dependent_child"} <= owners
    assert {r[0] for r in con.execute("select distinct political_bloc from member_terms")} == \
        {"Labor", "Coalition", "Crossbench"}
    assert con.execute("select count(*) from items where confidence = 'low'").fetchone()[0] >= 1
    assert con.execute("select max(n) from (select count(*) n from items where is_alteration "
                       "group by member_id)").fetchone()[0] >= 100
    # entities touched by the items are all present; every item's entity resolves
    assert con.execute("select count(*) from items i left join entities e using(entity_id) "
                       "where i.entity_id is not null and e.entity_id is null").fetchone()[0] == 0
    assert con.execute("select count(*) from (select entity_id from items where entity_id is "
                       "not null group by 1 having count(*) >= 2)").fetchone()[0] > 0


def test_fixture_aliases_give_the_same_match_methods_as_real():
    """Each fixture item's match method (normalise_entity -> entity_aliases) resolves."""
    from disclosures.normalise import normalise_entity

    con = ro(MINI_DB)
    methods = dict(con.execute("select alias_normalised, method from entity_aliases"))
    raws = [r[0] for r in con.execute("select entity_name_raw from items "
                                      "where entity_id is not null")]
    assert all(normalise_entity(r) in methods for r in raws)


def test_readme_lists_the_six_members():
    text = (FIXTURE_DIR / "README.md").read_text()
    for mid in FIXTURE_IDS:
        assert f"`{mid}`" in text


@pytest.mark.parametrize("name", ["mini.db", "mini-manifest.csv"])
def test_fixture_files_are_tracked_not_ignored(name):
    import subprocess

    from web_support import REPO

    r = subprocess.run(["git", "check-ignore", "-q", str(FIXTURE_DIR / name)], cwd=REPO)
    assert r.returncode == 1, f"{name} is git-ignored"
