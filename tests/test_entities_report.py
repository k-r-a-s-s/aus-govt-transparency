"""T2.7: join_by_name, the AC-3.3 / AC-3.4 checks, and the entities report."""

import sqlite3

import pytest

from disclosures.cli import main
from disclosures.entities import join_by_name, run_entities
from disclosures.entities_report import (BEGIN, END, ac33_unresolved, ac34_problems, top_v2,
                                         write_report)
from test_entities import (REAL_DB, REPO, make_data, make_reference, make_sectioned_db,  # noqa: F401
                           no_llm)

REAL_REFERENCE = REPO / "data" / "reference"


def test_join_by_name_rules():
    entities = {
        "qantas_airways": ("Qantas Airways", "airline", "QAN"),
        "qantas": ("Qantas", "airline", None),            # llm, name is a curated alias
        "agest_super": ("AGEST Super", "trust_or_fund", None),       # llm
        "agest_super_pty_ltd": ("AGEST Super Pty Ltd", None, None),  # singleton
        "tower_limited": ("Tower Limited", "listed_company", "TWR"),  # asx: never moved
        "tower_australia": ("Tower Australia", "bank_or_financial", None),
        "lonely": ("Lonely", "other", None),               # llm, name owned by nobody
    }
    aliases = {
        "qantas": ("qantas_airways", "curated", None),
        "qf": ("qantas", "llm", "high"),
        "agest superannuation": ("agest_super", "llm", "high"),
        "agest super": ("agest_super_pty_ltd", "singleton", None),
        "twr": ("tower_limited", "asx", None),
        "tower": ("tower_australia", "llm", "high"),
        "lonely one": ("lonely", "llm", "high"),
        "family trust": (None, "generic", None),
    }
    join_by_name(entities, aliases)
    assert aliases["qf"] == ("qantas_airways", "llm", "high")
    assert aliases["agest super"] == ("agest_super", "singleton", None)
    assert aliases["twr"][0] == "tower_limited" and aliases["tower"][0] == "tower_australia"
    assert aliases["lonely one"][0] == "lonely"
    assert set(entities) == {"qantas_airways", "agest_super", "tower_limited",
                             "tower_australia", "lonely"}


def built(tmp_path):
    db = make_sectioned_db(tmp_path / "v2.db")
    data = make_data(tmp_path, aliases_csv="alias,canonical_name,entity_type,asx_code\n"
                                           "qantas airways,Qantas Airways,airline,QAN\n")
    (data / "asx_exclusions.csv").write_text("alias,note\nING,ambiguous\n")
    ref = make_reference(tmp_path)
    run_entities(db, data, reference_dir=ref)
    return db, ref


@pytest.mark.usefixtures("no_llm")
def test_ac33_ac34_on_fixture(tmp_path):
    db, ref = built(tmp_path)
    con = sqlite3.connect(db)
    assert ac33_unresolved(con) == []
    # fixture has curated and asx but no generic alias, and the BHP entity is listed
    assert ac34_problems(con, ref) == ["no generic aliases"]
    con.execute("update items set entity_id = NULL where item_id = 'a1'")
    con.execute("update entities set asx_code = 'ZZZ' where entity_type = 'listed_company'")
    assert ac33_unresolved(con) == ["BHP Group Ltd"]
    assert any("asx_code ZZZ, not in" in p for p in ac34_problems(con, ref))
    con.close()


@pytest.mark.usefixtures("no_llm")
def test_report_keeps_hand_written_text(tmp_path):
    db, ref = built(tmp_path)
    out = tmp_path / "report.md"
    out.write_text(f"# Title\n\nintro\n\n{BEGIN}\nold\n{END}\n\n## Review\n\nmine\n")
    write_report(db, ref, out, v1_path=tmp_path / "missing.db")
    text = out.read_text()
    assert text.startswith("# Title\n\nintro\n\n" + BEGIN) and text.endswith("## Review\n\nmine\n")
    assert "old" not in text and "Result: **0** (PASS)" in text and "BHP Group Limited" in text
    first = text
    write_report(db, ref, out, v1_path=tmp_path / "missing.db")
    assert out.read_text() == first  # deterministic, idempotent


@pytest.mark.usefixtures("no_llm")
def test_cli_report(tmp_path, capsys):
    db, ref = built(tmp_path)
    out = tmp_path / "r.md"
    assert main(["entities", "--db", str(db), "--data", str(tmp_path / "entities"),
                 "--offline", "--report", str(out)]) == 0
    assert out.read_text().startswith("# Entities report") and "wrote" in capsys.readouterr().out


def real_con():
    if not REAL_DB.exists():
        pytest.skip("disclosures_v2.db not built")
    con = sqlite3.connect(f"file:{REAL_DB}?mode=ro", uri=True)
    if not con.execute("select count(*) from entity_aliases").fetchone()[0]:
        con.close()
        pytest.skip("entities not run on disclosures_v2.db")
    return con


def test_ac33_real_db():
    """AC-3.3: non-generic named items without an entity = 0."""
    con = real_con()
    assert ac33_unresolved(con) == []
    con.close()


def test_ac34_real_db():
    """AC-3.4: curated, asx and generic aliases all > 0; every listed_company entity has an
    asx_code in the saved ASX snapshot."""
    con = real_con()
    assert ac34_problems(con, REAL_REFERENCE) == []
    con.close()


def test_top20_real_db_has_no_known_duplicates():
    """AC-3.6 guard: no two top-20 canonical names normalise alike or share an ASX code, and
    none is a name another entity owns as an alias."""
    from disclosures.normalise import normalise_entity
    con = real_con()
    top = top_v2(con)
    owner = dict(con.execute("select alias_normalised, entity_id from entity_aliases"))
    ids = {n: e for e, n in con.execute("select entity_id, canonical_name from entities")}
    con.close()
    assert len(top) == 20
    assert len({normalise_entity(n) for n, *_ in top}) == 20
    codes = [c for _, _, c, _ in top if c]
    assert len(codes) == len(set(codes))
    for name, *_ in top:
        assert owner.get(normalise_entity(name), ids[name]) == ids[name], name
