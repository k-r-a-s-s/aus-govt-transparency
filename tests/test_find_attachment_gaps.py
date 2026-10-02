import csv
import importlib.util
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "find_attachment_gaps", ROOT / "scripts" / "find_attachment_gaps.py"
)
gaps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gaps)


def _item(section, owner, page, entity, description=None):
    return {"section": section, "owner": owner, "page": page,
            "entity_name": entity, "description": description or entity}


def _write(root, stem, items, notes=""):
    p = root / "45" / f"{stem}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"pdf_path": f"pdfs/45/{stem}.pdf", "items": items,
                             "extraction_notes": notes}))


def _v1(path, rows):
    con = sqlite3.connect(path)
    con.execute("create table disclosures (pdf_filename text, raw_entity text)")
    con.executemany("insert into disclosures values (?, ?)", rows)
    con.commit()
    con.close()


def test_scan_flags_unitemised_attachments(tmp_path):
    ex = tmp_path / "house"
    # (a) "see attached" in s7 with nothing after it.
    _write(ex, "gap_45p", [_item(7, "self", 5, None, "SMSF holdings - see Attachment A"),
                           _item(1, "self", 2, "Acme Pty Ltd")])
    # Itemised attachment: the reference is followed by 3 holdings on later pages.
    _write(ex, "ok_45p", [_item(7, "self", 5, None, "see attached list")]
           + [_item(7, "self", 9, n) for n in ("BHP", "CSL", "Westpac")])
    # (b) notes mention an attachment and v1 has >= 3 names v2 lacks.
    _write(ex, "notes_45p", [_item(7, "self", 3, "Telstra")],
           notes="Page 9 contains a broker statement")
    # Notes hit but v1 names all matched: not a candidate.
    _write(ex, "matched_45p", [_item(7, "self", 3, "Telstra Corporation Limited")],
           notes="attachment on page 4")
    db = tmp_path / "v1.db"
    _v1(db, [("notes_45p.pdf", n) for n in ("Amcor", "Magellan Global", "Caltex", "Telstra")]
        + [("matched_45p.pdf", "TELSTRA CORPORATION")])

    rows = {r["stem"]: r for r in gaps.scan(ex, db)}

    assert set(rows) == {"gap_45p", "notes_45p"}
    assert rows["gap_45p"]["reason"] == "a:item-references-attachment"
    assert (rows["gap_45p"]["ref_page"], rows["gap_45p"]["ref_section"]) == ("5", "7")
    assert rows["notes_45p"]["reason"] == "b:notes-attachment+v1-unmatched"
    assert rows["notes_45p"]["v1_unmatched_count"] == 3
    assert "Telstra" not in rows["notes_45p"]["v1_unmatched_sample"]


def test_main_writes_csv_with_blank_verdict(tmp_path):
    ex = tmp_path / "house"
    _write(ex, "gap_45p", [_item(13, "spouse", 6, None, "as per attached schedule")])
    out = tmp_path / "gaps.csv"
    assert gaps.main(["--extractions", str(ex), "--v1", str(tmp_path / "none.db"),
                      "--out", str(out)]) == 0
    rows = list(csv.DictReader(out.open()))
    assert [r["stem"] for r in rows] == ["gap_45p"]
    assert rows[0]["verdict"] == ""
    assert list(rows[0]) == gaps.FIELDS
