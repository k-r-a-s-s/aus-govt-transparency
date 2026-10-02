import datetime as dt
import sqlite3
from pathlib import Path

import httpx
import pytest

from disclosures.cli import main
from disclosures.entities import (ASX_URL, Resolution, entity_id_for, fetch_asx,
                                  load_generic_terms, newest_asx_snapshot, read_asx_snapshot,
                                  resolve, run_entities)
from disclosures.load import DDL, member_slug
from disclosures.normalise import normalise_entity

REPO = Path(__file__).resolve().parent.parent

ITEMS = [
    ("i01", "Qantas Airways Limited"),
    ("i02", "QANTAS AIRWAYS LTD"),
    ("i03", "Qantas Airways Ltd."),
    ("i04", "Family Trust"),
    ("i05", "N/A"),
    ("i06", "Westpac"),
    ("i07", None),
    ("i08", "L'Oreal Australia"),
    ("i09", "L'Oréal Australia"),
    ("i10", "Samson Oil & Gas Ltd"),
    ("i11", "Samson Oil Gas Ltd"),
]


def make_db(path: Path, items=ITEMS) -> Path:
    con = sqlite3.connect(path)
    con.executescript(DDL)
    con.executemany(
        "insert into items (item_id, pdf_sha256, member_id, chamber, parliament, section, "
        "category, owner, entity_name_raw, description, is_alteration, change_type, "
        "date_precision, page, confidence) values (?, 'sha', 'm', 'house', 47, 1, "
        "'Shareholding', 'self', ?, 'd', 0, 'initial', 'unknown', 1, 'high')", items)
    con.commit()
    con.close()
    return path


def make_data(root: Path, generic=("family trust", "n/a"), aliases_csv=None) -> Path:
    d = root / "entities"
    d.mkdir(parents=True, exist_ok=True)
    (d / "generic_terms.csv").write_text("term,note\n" + "".join(f"{t},x\n" for t in generic))
    if aliases_csv is not None:
        (d / "aliases.csv").write_text(aliases_csv)
    return d


def dump(db: Path):
    con = sqlite3.connect(db)
    out = {t: con.execute(f"select * from {t} order by 1").fetchall()
           for t in ("entities", "entity_aliases")}
    out["items"] = con.execute("select item_id, entity_id from items order by 1").fetchall()
    con.close()
    return out


def item_entities(db: Path) -> dict:
    return dict(dump(db)["items"])


def test_normalisation_is_the_shared_one(tmp_path):
    db = make_db(tmp_path / "v2.db")
    run_entities(db, make_data(tmp_path))
    aliases = {a for a, *_ in dump(db)["entity_aliases"]}
    expected = {normalise_entity(r) for _, r in ITEMS if r}
    assert aliases == expected
    assert "qantas airways" in aliases


def test_generic_alias_gets_null_entity(tmp_path):
    db = make_db(tmp_path / "v2.db")
    s = run_entities(db, make_data(tmp_path))
    rows = {a: (eid, m) for a, eid, m, _ in dump(db)["entity_aliases"]}
    assert rows["family trust"] == (None, "generic")
    assert rows["n a"] == (None, "generic")  # "N/A" normalises to "n a"; the CSV term too
    ie = item_entities(db)
    assert ie["i04"] is None and ie["i05"] is None
    assert s["items"]["generic"] == 2 and s["unresolved"] == 0


def test_null_entity_name_gets_no_entity(tmp_path):
    db = make_db(tmp_path / "v2.db")
    run_entities(db, make_data(tmp_path))
    assert item_entities(db)["i07"] is None


def test_singletons_one_entity_per_alias(tmp_path):
    db = make_db(tmp_path / "v2.db")
    s = run_entities(db, make_data(tmp_path))
    d = dump(db)
    ie = item_entities(db)
    # three spellings, one alias, one entity named by the commonest (then smallest) spelling
    assert ie["i01"] == ie["i02"] == ie["i03"]
    ents = {eid: (name, et, asx) for eid, name, et, asx in d["entities"]}
    name, et, asx = ents[ie["i01"]]
    assert name == "QANTAS AIRWAYS LTD" and et is None and asx is None
    assert ie["i01"] == member_slug(name)
    assert ents[ie["i06"]][0] == "Westpac"
    assert set(m for _, _, m, _ in d["entity_aliases"]) == {"generic", "singleton"}
    assert s["unresolved"] == 0


def test_same_slug_aliases_share_an_entity(tmp_path):
    db = make_db(tmp_path / "v2.db")
    run_entities(db, make_data(tmp_path))
    ie = item_entities(db)
    assert ie["i08"] == ie["i09"] == "l_oreal_australia"  # "loreal" / "loréal" aliases
    assert ie["i10"] == ie["i11"]  # "samson oil and gas" / "samson oil gas"


def test_curated_beats_singleton(tmp_path):
    db = make_db(tmp_path / "v2.db")
    csv = ("alias,canonical_name,entity_type,asx_code,review_flag,note\n"
           "Qantas Airways,Qantas Airways Limited,airline,QAN,,\n"
           "westpac,Westpac Banking Corporation,bank_or_financial,WBC,,\n")
    s = run_entities(db, make_data(tmp_path, aliases_csv=csv))
    d = dump(db)
    ents = {eid: rest for eid, *rest in d["entities"]}
    assert ents["qantas_airways_limited"] == ["Qantas Airways Limited", "airline", "QAN"]
    ie = item_entities(db)
    assert ie["i01"] == "qantas_airways_limited" and ie["i06"] == "westpac_banking_corporation"
    assert s["aliases"]["curated"] == 2 and s["items"]["curated"] == 4


def test_stages_are_pluggable_and_ordered():
    items = [("a", "Foo"), ("b", "Bar")]
    calls = []

    def first(aliases, ctx):
        calls.append(("first", list(aliases)))
        return {"foo": Resolution("Foo Corp", "other")}

    def second(aliases, ctx):
        calls.append(("second", list(aliases)))
        return {a: Resolution(a.title()) for a in aliases}

    ents, aliases, ie = resolve(items, Path("/nonexistent"), stages=[("asx", first),
                                                                    ("singleton", second)])
    assert calls == [("first", ["bar", "foo"]), ("second", ["bar"])]
    assert aliases["foo"] == ("foo_corp", "asx", None)
    assert aliases["bar"] == ("bar", "singleton", None)
    assert ents["foo_corp"] == ("Foo Corp", "other", None)


def test_two_runs_identical(tmp_path):
    db = make_db(tmp_path / "v2.db")
    data = make_data(tmp_path)
    run_entities(db, data)
    first = dump(db)
    run_entities(db, data)
    assert dump(db) == first
    # and a fresh DB with the items inserted in another order gives the same tables
    db2 = make_db(tmp_path / "v2b.db", items=list(reversed(ITEMS)))
    run_entities(db2, data)
    assert dump(db2) == first


def test_entity_id_fallback_for_non_ascii():
    assert entity_id_for("Qantas Airways Limited") == "qantas_airways_limited"
    assert entity_id_for("北京").startswith("entity_")


def test_real_generic_terms_file_normalises():
    terms = load_generic_terms(REPO / "data" / "entities")
    assert {"family trust", "smsf", "self managed super fund", "n a", "nil", "various",
            "superannuation"} <= terms
    assert "" not in terms


def test_cli_offline(tmp_path, capsys):
    db = make_db(tmp_path / "v2.db")
    rc = main(["entities", "--offline", "--db", str(db), "--data", str(make_data(tmp_path))])
    out = capsys.readouterr().out
    assert rc == 0
    assert "singleton" in out and "(AC-3.3): 0 OK" in out


def test_cli_missing_db(tmp_path, capsys):
    rc = main(["entities", "--db", str(tmp_path / "nope.db")])
    assert rc == 2 and "run `python -m disclosures load` first" in capsys.readouterr().err


def test_refuses_v1_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    make_db(tmp_path / "disclosures.db")
    with pytest.raises(ValueError, match="frozen v1"):
        run_entities(tmp_path / "disclosures.db", make_data(tmp_path))


# --- ASX stage (T2.2) ---------------------------------------------------------------------

ASX_CSV = (
    "ASX listed companies as at Fri Oct 02 23:02:35 AEST 2026\n"
    "\n"
    "Company name,ASX code,GICS industry group\n"
    '"BHP GROUP LIMITED","BHP","Materials"\n'
    '"COMMONWEALTH BANK OF AUSTRALIA.","CBA","Banks"\n'
    '"QANTAS AIRWAYS LIMITED","QAN","Transportation"\n'
    '"INGHAMS GROUP LIMITED","ING","Food, Beverage & Tobacco"\n'
    '"TWIN CO LTD","TW1","Other"\n'
    '"TWIN CO LIMITED","TW2","Other"\n'
)

ASX_ITEMS = [  # (item_id, raw, section)
    ("a1", "BHP Group Ltd", 1),
    ("a2", "BHP Group Limited", 1),
    ("a3", "BHP", 1),
    ("a4", "CBA", 8),                 # ticker, but never on a section-1 item: not eligible
    ("a5", "Qantas Airways Limited", 1),
    ("a6", "Qantas Airways Ltd", 12),  # same alias, other section: gets the entity too
    ("a7", "ING", 1),                  # excluded alias
    ("a8", "ING", 8),
    ("a9", "Twin Co", 1),              # two listed companies normalise to "twin": ambiguous
    ("a10", "QAN", 1),                 # ticker-only alias joins the name-matched entity
]


def make_sectioned_db(path: Path, items=ASX_ITEMS) -> Path:
    con = sqlite3.connect(path)
    con.executescript(DDL)
    con.executemany(
        "insert into items (item_id, pdf_sha256, member_id, chamber, parliament, section, "
        "category, owner, entity_name_raw, description, is_alteration, change_type, "
        "date_precision, page, confidence) values (?, 'sha', 'm', 'house', 47, ?, "
        "'x', 'self', ?, 'd', 0, 'initial', 'unknown', 1, 'high')",
        [(iid, sec, raw) for iid, raw, sec in items])
    con.commit()
    con.close()
    return path


def make_reference(root: Path, files=None) -> Path:
    ref = root / "reference"
    ref.mkdir(parents=True, exist_ok=True)
    for name, text in (files or {"asx_listed_companies_2026-10-02.csv": ASX_CSV}).items():
        (ref / name).write_text(text)
    return ref


def test_read_asx_snapshot_skips_title(tmp_path):
    ref = make_reference(tmp_path)
    rows = read_asx_snapshot(ref / "asx_listed_companies_2026-10-02.csv")
    assert rows[0] == ("BHP GROUP LIMITED", "BHP") and len(rows) == 6


def test_asx_stage_name_ticker_scope_exclusions(tmp_path):
    db = make_sectioned_db(tmp_path / "v2.db")
    data = make_data(tmp_path)  # tmp/entities -> reference dir defaults to tmp/reference
    (data / "asx_exclusions.csv").write_text("alias,note\nING,ambiguous\n")
    make_reference(tmp_path)
    s = run_entities(db, data)
    ie = item_entities(db)
    con = sqlite3.connect(db)
    ents = {r[0]: r[1:] for r in con.execute("select * from entities")}
    methods = dict(con.execute("select alias_normalised, method from entity_aliases"))
    con.close()
    # name match: both spellings normalise to "bhp group"; the ticker alias joins them
    assert ie["a1"] == ie["a2"] == ie["a3"]
    # canonical: commonest raw spelling of the name-matched aliases, ties alphabetical
    assert ents[ie["a1"]] == ("BHP Group Limited", "listed_company", "BHP")
    assert methods["bhp group"] == methods["bhp"] == "asx"
    # every item with a matched alias gets it, whatever its section
    assert ie["a5"] == ie["a6"] == ie["a10"]
    assert ents[ie["a5"]][1:] == ("listed_company", "QAN")
    assert methods["qan"] == "asx"
    # no section-1 item -> not eligible; excluded; ambiguous name
    assert methods["cba"] == methods["ing"] == methods["twin"] == "singleton"
    assert s["aliases"]["asx"] == 4 and s["items"]["asx"] == 6
    assert s["unresolved"] == 0


def test_asx_ticker_only_uses_asx_name(tmp_path):
    db = make_sectioned_db(tmp_path / "v2.db", items=[("t1", "CBA", 1)])
    make_reference(tmp_path)
    run_entities(db, make_data(tmp_path))
    con = sqlite3.connect(db)
    assert con.execute("select * from entities").fetchall() == [
        ("commonwealth_bank_of_australia", "Commonwealth Bank Of Australia.",
         "listed_company", "CBA")]
    con.close()


def test_curated_beats_asx(tmp_path):
    db = make_sectioned_db(tmp_path / "v2.db", items=[("c1", "BHP", 1)])
    make_reference(tmp_path)
    csv_text = "alias,canonical_name,entity_type,asx_code\nBHP,BHP,listed_company,BHP\n"
    run_entities(db, make_data(tmp_path, aliases_csv=csv_text))
    con = sqlite3.connect(db)
    assert con.execute("select method from entity_aliases").fetchall() == [("curated",)]
    con.close()


def test_newest_snapshot_wins(tmp_path):
    old = ASX_CSV.replace('"QANTAS AIRWAYS LIMITED","QAN"', '"QANTAS AIRWAYS LIMITED","OLD"')
    ref = make_reference(tmp_path, {"asx_listed_companies_2025-01-01.csv": old,
                                    "asx_listed_companies_2026-10-02.csv": ASX_CSV,
                                    "notes.csv": "x\n"})
    assert newest_asx_snapshot(ref).name == "asx_listed_companies_2026-10-02.csv"
    assert newest_asx_snapshot(tmp_path / "missing") is None
    db = make_sectioned_db(tmp_path / "v2.db", items=[("q1", "Qantas Airways", 1)])
    run_entities(db, make_data(tmp_path), reference_dir=ref)
    con = sqlite3.connect(db)
    assert con.execute("select asx_code from entities").fetchone() == ("QAN",)
    con.close()


def test_asx_runs_are_deterministic(tmp_path):
    data = make_data(tmp_path)
    make_reference(tmp_path)
    db = make_sectioned_db(tmp_path / "v2.db")
    run_entities(db, data)
    first = dump(db)
    db2 = make_sectioned_db(tmp_path / "v2b.db", items=list(reversed(ASX_ITEMS)))
    run_entities(db2, data)
    assert dump(db2) == first


def test_fetch_asx_sends_ua_and_writes_dated_file(tmp_path):
    seen = {}

    def handler(request):
        seen["ua"] = request.headers.get("user-agent")
        seen["url"] = str(request.url)
        return httpx.Response(200, content=ASX_CSV.encode())

    http = httpx.Client(transport=httpx.MockTransport(handler))
    path, n = fetch_asx(tmp_path / "ref", http=http, today=dt.date(2026, 10, 2))
    assert seen["url"] == ASX_URL and "Mozilla/5.0" in seen["ua"]
    assert path == tmp_path / "ref" / "asx_listed_companies_2026-10-02.csv" and n == 6
    assert path.read_text() == ASX_CSV


def test_fetch_asx_rejects_bad_responses(tmp_path):
    ref = tmp_path / "ref"
    blocked = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_asx(ref, http=blocked)
    html = httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=b"<html>blocked</html>")))
    with pytest.raises(ValueError):
        fetch_asx(ref, http=html)
    assert not ref.exists() or list(ref.iterdir()) == []


def test_cli_fetch_asx(tmp_path, monkeypatch, capsys):
    from disclosures import entities as ent

    calls = []
    monkeypatch.setattr(ent, "fetch_asx", lambda ref: calls.append(ref) or (ref / "f.csv", 6))
    rc = main(["entities", "--fetch-asx", "--data", str(tmp_path / "entities")])
    assert rc == 0 and calls == [tmp_path / "reference"]
    assert "(6 companies)" in capsys.readouterr().out


def test_real_asx_snapshot():
    snap = newest_asx_snapshot(REPO / "data" / "reference")
    assert snap is not None
    rows = read_asx_snapshot(snap)
    assert 1500 < len(rows) < 3000
    codes = {c for _, c in rows}
    assert {"BHP", "CBA", "QAN", "NAB"} <= codes


# --- T2.3: --draft-candidates worksheet -----------------------------------------------------

CANDIDATE_ITEMS = [  # (item_id, raw, section)
    ("c1", "Qantas", 8), ("c2", "QANTAS", 8), ("c3", "Qantas", 12),
    ("c4", "Qantas Airways Limited", 1), ("c5", "Qantas Club", 8),
    ("c6", "Westpac", 1), ("c7", "Westpac Bank", 1),
    ("c8", "Family Trust", 1), ("c9", "Family Trust", 1), ("c10", "Family Trust", 1),
    ("c11", "Telstra", 8), ("c12", "WESTPAC", 8),
]


def read_candidates(path: Path):
    import csv
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_draft_candidates_heads_variants_asx(tmp_path, capsys):
    from disclosures.entities import CANDIDATE_FIELDS
    db = make_sectioned_db(tmp_path / "v2.db", CANDIDATE_ITEMS)
    data = make_data(tmp_path)
    make_reference(tmp_path)
    assert main(["entities", "--db", str(db), "--data", str(data),
                 "--draft-candidates", "--top", "3"]) == 0
    out = data / "alias_candidates.csv"
    assert "3 heads" in capsys.readouterr().out
    rows = read_candidates(out)
    assert tuple(rows[0]) == CANDIDATE_FIELDS
    # generic "family trust" (3 items) is skipped; ties break alphabetically
    assert [r["alias"] for r in rows] == ["qantas", "westpac", "qantas airways"]
    q = rows[0]
    assert q["rank"] == "1" and q["item_count"] == "3" and q["sections"] == "8 12"
    assert q["sample_spellings"] == "Qantas (2) | QANTAS (1)"
    assert q["asx_code"] == ""  # "qantas" is neither an ASX name nor a ticker
    assert q["variants"] == "qantas airways (1) [QAN] | qantas club (1)"
    assert q["variant_count"] == "2"
    qa = rows[2]
    assert qa["asx_code"] == "QAN" and qa["asx_name"] == "QANTAS AIRWAYS LIMITED"
    assert rows[1]["variants"] == "westpac bank (1)"
    # the entity tables are untouched: drafting reads the DB only
    assert dump(db)["entities"] == []


def test_draft_candidates_custom_path_and_missing_db(tmp_path, capsys):
    db = make_sectioned_db(tmp_path / "v2.db", CANDIDATE_ITEMS)
    data = make_data(tmp_path)
    out = tmp_path / "x" / "c.csv"
    assert main(["entities", "--db", str(db), "--data", str(data),
                 "--draft-candidates", str(out)]) == 0
    assert len(read_candidates(out)) == 6  # fewer names than --top: all of them
    assert main(["entities", "--db", str(tmp_path / "nope.db"), "--data", str(data),
                 "--draft-candidates"]) == 2


AC31_GROUPS = [
    {"cba", "commonwealth bank", "commonwealth bank of australia"},
    {"nab", "national australia bank"},
    {"anz", "australia and new zealand banking group"},
    {"qantas", "qantas airways"},
    {"virgin australia", "virgin australia airlines"},
    {"westpac", "westpac banking"},
    {"telstra", "telstra corporation"},
]


def test_real_candidates_cover_ac31():
    """The committed worksheet covers 200 heads and every AC-3.1 group (head or variant)."""
    path = REPO / "data" / "entities" / "alias_candidates.csv"
    rows = read_candidates(path)
    assert len(rows) == 200
    seen = set()
    for r in rows:
        seen.add(r["alias"])
        seen.update(v.rsplit(" (", 1)[0] for v in r["variants"].split(" | ") if v)
    for group in AC31_GROUPS:
        assert seen & {normalise_entity(n) for n in group}, group
