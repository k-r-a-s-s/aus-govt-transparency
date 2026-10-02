import sqlite3
from pathlib import Path

import pytest

from disclosures.cli import main
from disclosures.entities import (Resolution, entity_id_for, load_generic_terms, resolve,
                                  run_entities)
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
