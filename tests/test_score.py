import copy
import json
import sqlite3

import pytest
from conftest import write_json

from disclosures.cli import main
from disclosures.score import match_items, pair_docs, score_dirs, score_pairs, score_v1


def item(section, entity, description=None, owner="self", page=1, lodged=None,
         change="initial", alt=False):
    return {
        "section": section, "subsection": None, "owner": owner, "entity_name": entity,
        "description": description or entity or "", "location": None, "purpose": None,
        "is_alteration": alt, "change_type": change, "lodged_date": lodged,
        "date_precision": "day" if lodged else "unknown", "page": page, "confidence": "high",
    }


def doc(items, stem="x_45p", sha="a" * 64):
    return {"pdf_path": f"pdfs/45/{stem}.pdf", "pdf_sha256": sha, "items": items}


GOLD_ITEMS = [
    item(1, "BHP Group Limited", lodged="2016-08-30"),           # hit
    item(8, "Commonwealth Bank of Australia", "Savings account"),  # hit
    item(3, None, "Residential home, Canberra ACT"),             # hit (description key)
    item(4, "Acme Widgets Pty Ltd"),                             # pred puts it in section 1
    item(13, "Australian Labor Party"),                          # pred gets owner wrong
    item(11, "Qantas Chairman's Lounge", page=2),                # missed entirely
]


def hand_built_pred():
    p = copy.deepcopy(GOLD_ITEMS[:5])
    p[1]["entity_name"] = "Commonwealth Bank of Australia Ltd"  # normalises equal
    p[3]["section"] = 1                                        # mis-sectioned
    p[4]["owner"] = "spouse"                                   # wrong owner
    p.append(item(9, None, "Vintage motor vehicle"))           # extra item
    return p


def test_hand_built_exact_prf():
    r = score_pairs([(doc(GOLD_ITEMS), doc(hand_built_pred()))])
    # section-strict: 4 matched of 6 gold, 6 pred. The mis-sectioned item is a miss AND an extra.
    assert r["counts"] == {"n_gold": 6, "n_pred": 6, "matched": 4, "matched_section_ignored": 5}
    assert r["precision"] == pytest.approx(4 / 6)
    assert r["recall"] == pytest.approx(4 / 6)
    assert r["f1"] == pytest.approx(4 / 6)
    # section-ignored: the mis-sectioned item is a hit.
    assert r["section_ignored"]["precision"] == pytest.approx(5 / 6)
    assert r["section_ignored"]["recall"] == pytest.approx(5 / 6)
    assert r["section_ignored"]["f1"] == pytest.approx(5 / 6)
    # field accuracies on the 4 matched pairs: one wrong owner.
    assert r["accuracy"]["owner"] == pytest.approx(3 / 4)
    for f in ("change_type", "is_alteration", "page"):
        assert r["accuracy"][f] == 1.0
    # lodged_date accuracy only over matched pairs with non-null gold lodged_date (1 pair).
    assert r["accuracy_counts"]["lodged_date"] == {"correct": 1, "total": 1}
    misses = r["worst_misses"]
    assert [m["entity_name"] for m in misses] == ["Qantas Chairman's Lounge", "Acme Widgets Pty Ltd"]
    assert misses[0]["matched_if_section_ignored"] is False and misses[0]["page"] == 2
    assert misses[1]["matched_if_section_ignored"] is True
    assert r["per_pdf"][0]["recall"] == pytest.approx(4 / 6)


@pytest.mark.parametrize(
    "mutate,expected",
    [
        # one missed item: P = 5/5, R = 5/6
        (lambda p: p.pop(5), (1.0, 5 / 6)),
        # one extra item: P = 6/7, R = 1
        (lambda p: p.append(item(9, None, "Vintage motor vehicle")), (6 / 7, 1.0)),
        # one mis-sectioned item: P = R = 5/6 strict
        (lambda p: p[3].update(section=1), (5 / 6, 5 / 6)),
        # one wrong owner: still matched, P = R = 1
        (lambda p: p[4].update(owner="spouse"), (1.0, 1.0)),
    ],
    ids=["missed", "extra", "mis-sectioned", "wrong-owner"],
)
def test_single_error_cases(mutate, expected):
    pred = copy.deepcopy(GOLD_ITEMS)
    mutate(pred)
    r = score_pairs([(doc(GOLD_ITEMS), doc(pred))])
    p, rec = expected
    assert r["precision"] == pytest.approx(p)
    assert r["recall"] == pytest.approx(rec)
    assert r["f1"] == pytest.approx(2 * p * rec / (p + rec))


def test_wrong_owner_lowers_owner_accuracy_only():
    pred = copy.deepcopy(GOLD_ITEMS)
    pred[4]["owner"] = "spouse"
    r = score_pairs([(doc(GOLD_ITEMS), doc(pred))])
    assert r["accuracy"]["owner"] == pytest.approx(5 / 6)
    assert r["accuracy"]["page"] == 1.0


def test_self_consistency_all_ones(tmp_path):
    gold = tmp_path / "gold"
    write_json(gold / "x_45p.json", doc(GOLD_ITEMS))
    write_json(gold / "y_46p.json", doc(GOLD_ITEMS[:2], stem="y_46p", sha="b" * 64))
    write_json(gold / "selection.json", {"seed": 1, "pdfs": []})  # must be ignored
    r = score_dirs(gold, gold)
    assert r["n_pdfs"] == 2
    assert r["precision"] == r["recall"] == r["f1"] == 1.0
    assert all(v == 1.0 for v in r["section_ignored"].values())
    assert all(v == 1.0 for v in r["accuracy"].values())
    assert r["worst_misses"] == []


def test_missing_pred_counts_all_items_missed_and_stem_fallback(tmp_path):
    g1, g2 = doc(GOLD_ITEMS, stem="a_45p", sha="1" * 64), doc(GOLD_ITEMS[:2], stem="b_45p", sha="2" * 64)
    p2 = doc(GOLD_ITEMS[:2], stem="b_45p", sha="9" * 64)  # sha differs -> pair by stem
    pairs = pair_docs([p2], [g1, g2])
    assert pairs[0][1] is None and pairs[1][1] is p2
    r = score_pairs(pairs)
    assert r["recall"] == pytest.approx(2 / 8) and r["precision"] == 1.0
    assert r["n_pdfs_without_pred"] == 1


def test_entity_null_on_one_side_falls_back_to_description():
    g = [item(8, None, "Westpac savings account")]
    p = [item(8, "Westpac", "Westpac savings account")]
    assert len(match_items(p, g)) == 1
    # with both entity names present the entity key is used, so descriptions don't matter
    g2 = [item(8, "Westpac", "anything")]
    p2 = [item(8, "Westpac Banking Corporation", "something else")]
    assert len(match_items(p2, g2)) == 1


def test_duplicate_entities_paired_by_page():
    g = [item(1, "BHP", page=2), item(1, "BHP", page=5)]
    p = [item(1, "BHP", page=5), item(1, "BHP", page=2)]
    r = score_pairs([(doc(g), doc(p))])
    assert r["accuracy"]["page"] == 1.0


def test_v1_mode_section_ignored_only(tmp_path):
    db = tmp_path / "v1.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE disclosures (pdf_filename TEXT, raw_entity TEXT, raw_description TEXT)")
    con.executemany("INSERT INTO disclosures VALUES (?,?,?)", [
        ("x_45p.pdf", "BHP Group Ltd", "Shares"),
        ("x_45p.pdf", "", "Residential home, Canberra ACT"),
        ("x_45p.pdf", "Telstra", "Shares"),          # extra
        ("other_45p.pdf", "Qantas", "Lounge"),       # different PDF, ignored
    ])
    con.commit()
    con.close()
    gold = tmp_path / "gold"
    write_json(gold / "x_45p.json", doc(GOLD_ITEMS))
    r = score_v1(db, gold)
    assert r["mode"] == "v1"
    assert r["counts"]["n_pred"] == 3 and r["counts"]["matched_section_ignored"] == 2
    assert r["section_ignored"]["precision"] == pytest.approx(2 / 3)
    assert r["section_ignored"]["recall"] == pytest.approx(2 / 6)
    assert r["precision"] is None and all(v is None for v in r["accuracy"].values())


def test_cli_score_writes_json(tmp_path, capsys):
    gold = tmp_path / "gold"
    write_json(gold / "x_45p.json", doc(GOLD_ITEMS))
    pred = tmp_path / "pred"
    write_json(pred / "house" / "45" / "x_45p.json", doc(hand_built_pred()))
    out = tmp_path / "out.json"
    assert main(["score", "--pred", str(pred), "--gold", str(gold), "--json", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["recall"] == pytest.approx(4 / 6)
    assert "precision=0.667 recall=0.667" in capsys.readouterr().out


def test_cli_empty_gold_dir_does_not_crash(tmp_path):
    gold = tmp_path / "gold"
    gold.mkdir()
    out = tmp_path / "o.json"
    assert main(["score", "--pred", str(gold), "--gold", str(gold), "--json", str(out)]) == 0
    assert json.loads(out.read_text())["counts"]["n_gold"] == 0
