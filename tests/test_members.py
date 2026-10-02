"""disclosures.members (D3 new-members rule, T3.3b): fake overrides + manifest, and the real
48th rows."""
import csv
import io
from collections import defaultdict
from pathlib import Path

from disclosures import members as MB
from disclosures.load import Overrides, norm_person_name

REPO = Path(__file__).resolve().parent.parent
MAN_HEADER = ["chamber", "parliament", "member_name", "electorate_or_state", "source_url",
              "listed_date", "pdf_path", "pdf_sha256", "page_count", "fetched_at"]


def _write(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _read(path: Path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def fake_repo(tmp_path: Path, extra_aliases=()):
    ov = tmp_path / "data" / "overrides"
    _write(ov / "pdf_members.csv", MB.PDF_MEMBERS_HEADER, [
        ["pdfs/47/katterb_47p.pdf", "bob_katter", "Bob Katter", "Kennedy", "v1"],
        ["pdfs/47/smitht_47p.pdf", "tony_smith", "Tony Smith", "Casey", "v1"],
    ])
    _write(ov / "member_aliases.csv", MB.ALIASES_HEADER, [
        ["Bob Katter", "Kennedy", "bob_katter", "Bob Katter", "canonical"],
        ["Tony Smith", "Casey", "tony_smith", "Tony Smith", "canonical"],
        *extra_aliases,
    ])
    man = [["house", "47", "Bob Katter", "Kennedy", "", "", "pdfs/47/katterb_47p.pdf", "x", "1", ""],
           ["house", "48", "Robert Katter", "Kennedy", "", "", "pdfs/48/katterr_48p.pdf", "x", "1", ""],
           ["house", "48", "Tony Smith", "Casey", "", "", "pdfs/48/smitht_48p.pdf", "x", "1", ""],
           ["house", "48", "Matt Smith", "Leichhardt", "", "", "pdfs/48/smithm_48p.pdf", "x", "1", ""]]
    _write(tmp_path / "pdfs" / "manifest.csv", MAN_HEADER, man)
    return ov


def test_new_returning_and_lookalike_report(tmp_path):
    ov = fake_repo(tmp_path)
    out = io.StringIO()
    counts = MB.resolve("house", 48, root=tmp_path, out=out)
    assert counts == {"returning": 1, "new": 2, "already": 0, "collisions": 0}
    text = out.getvalue()
    # an unaliased "Robert Katter" is new, but the eyeball list names Bob Katter
    assert "NEW robert_katter" in text and "bob_katter (Kennedy, 47-47)" in text
    assert "tony_smith (Casey, 47-47)" in text  # same-surname check for Matt Smith
    rows = {r["pdf_path"]: r for r in _read(ov / "pdf_members.csv")}
    assert rows["pdfs/48/smitht_48p.pdf"]["member_id"] == "tony_smith"
    assert rows["pdfs/48/smithm_48p.pdf"] == {
        "pdf_path": "pdfs/48/smithm_48p.pdf", "member_id": "matt_smith",
        "canonical_full_name": "Matt Smith", "electorate_or_state": "Leichhardt", "source": "aph_48"}
    assert list(rows) == sorted(rows)
    aliases = _read(ov / "member_aliases.csv")
    assert {"name_variant": "Matt Smith", "electorate_or_state": "Leichhardt", "member_id": "matt_smith",
            "canonical_full_name": "Matt Smith", "source": "aph_48"} in aliases
    # second run: nothing to do, nothing changes
    before = (ov / "pdf_members.csv").read_text(), (ov / "member_aliases.csv").read_text()
    assert MB.resolve("house", 48, root=tmp_path, out=io.StringIO())["already"] == 3
    assert ((ov / "pdf_members.csv").read_text(), (ov / "member_aliases.csv").read_text()) == before


def test_hand_alias_makes_returning(tmp_path):
    ov = fake_repo(tmp_path, [["Robert Katter", "Kennedy", "bob_katter", "Bob Katter", "aph_48"]])
    counts = MB.resolve("house", 48, root=tmp_path, out=io.StringIO())
    assert counts["returning"] == 2 and counts["new"] == 1
    rows = {r["pdf_path"]: r for r in _read(ov / "pdf_members.csv")}
    assert rows["pdfs/48/katterr_48p.pdf"]["member_id"] == "bob_katter"
    assert rows["pdfs/48/katterr_48p.pdf"]["canonical_full_name"] == "Bob Katter"


def test_slug_collision_writes_nothing(tmp_path):
    """An unresolved name whose slug is already someone's member_id is reported, not merged."""
    ov = fake_repo(tmp_path)
    _write(ov / "pdf_members.csv", MB.PDF_MEMBERS_HEADER,
           [["pdfs/44/smithm_44p.pdf", "matt_smith", "Matthew Smith", "Hume", "v1"]])
    _write(ov / "member_aliases.csv", MB.ALIASES_HEADER,
           [["Matthew Smith", "Hume", "matt_smith", "Matthew Smith", "canonical"]])
    _write(tmp_path / "pdfs" / "manifest.csv", MAN_HEADER, [
        ["house", "48", "Matt Smith", "Leichhardt", "", "", "pdfs/48/smithm_48p.pdf", "x", "1", ""]])
    before = (ov / "pdf_members.csv").read_text(), (ov / "member_aliases.csv").read_text()
    out = io.StringIO()
    assert MB.resolve("house", 48, root=tmp_path, out=out)["collisions"] == 1
    assert "COLLISION pdfs/48/smithm_48p.pdf" in out.getvalue()
    assert ((ov / "pdf_members.csv").read_text(), (ov / "member_aliases.csv").read_text()) == before


def test_real_48th_members():
    """Every pdfs/48 PDF has exactly one pdf_members row, and no new 48th member_id is a
    43rd-47th person under another id (same normalised name)."""
    rows = _read(REPO / "data" / "overrides" / "pdf_members.csv")
    man48 = sorted(r["pdf_path"] for r in _read(REPO / "pdfs" / "manifest.csv") if r["parliament"] == "48")
    r48 = [r for r in rows if r["pdf_path"].startswith("pdfs/48/")]
    assert sorted(r["pdf_path"] for r in r48) == man48 and len(man48) == 151
    assert len({r["member_id"] for r in r48}) == 151 and all(r["member_id"] for r in r48)
    ov = Overrides(REPO / "data" / "overrides")
    earlier_by_name = defaultdict(set)
    for r in rows:
        if r["member_id"] and not r["pdf_path"].startswith("pdfs/48/"):
            earlier_by_name[norm_person_name(r["canonical_full_name"])].add(r["member_id"])
    for r in r48:
        same = earlier_by_name.get(norm_person_name(r["canonical_full_name"]), set())
        assert same <= {r["member_id"]}, (r["pdf_path"], same)
    # returning MPs with a different printed name resolve to their old id (eyeballed in T3.3b)
    by_path = {r["pdf_path"]: r["member_id"] for r in r48}
    assert by_path["pdfs/48/katterr_48p.pdf"] == "bob_katter"
    assert by_path["pdfs/48/wilsonj_48p.pdf"] == "josh_wilson"
    assert by_path["pdfs/48/frencht_48p.pdf"] == "tom_french"
    assert ov.resolve_member("pdfs/48/katterr_48p.pdf", "x", "")[0] == "bob_katter"
