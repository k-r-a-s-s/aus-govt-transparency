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
    man48 = sorted(r["pdf_path"] for r in _read(REPO / "pdfs" / "manifest.csv")
                   if r["chamber"] == "house" and r["parliament"] == "48")
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


WIKI = """== Leadership ==
| {{sortname|Milton|Dick}} || [[Division of Oxley|Oxley]] || QLD
== Members ==
{| class="sortable wikitable"
! Member
|-
|[[File:x.jpg]]
|| '''{{sortname|Bob|Katter}}'''
| {{Australian party style|Katter's Australian Party}} |&nbsp; || colspan=2 | {{Australian politics/name|Katter's Australian Party}}|| [[Division of Kennedy|Kennedy]] || Qld || 1993–current ||
|-
|| '''{{sortname|Tony|Smith|dab=politician}}'''
| {{Australian party style|Liberal}} |&nbsp;
| colspan="2" |{{Australian politics/name|Liberal}}
|[[Division of Casey|Casey]]
|VIC
|2001–current
|-
|| '''{{sortname|Matt|Smith}}'''
| {{Australian party style|Liberal}}|&nbsp; || colspan=2 | {{Australian politics/name|Liberal}}{{efn|name=LIB}}|| [[Division of Leichhardt|Leichhardt]] || QLD || 2025–current ||
|}
==Current party standings==
"""
LATER = WIKI.replace("{{sortname|Matt|Smith}}", "{{sortname|Ann|Byelection}}").replace(
    "{{Australian politics/name|Katter's Australian Party}}", "[[Pauline Hanson's One Nation|One Nation]]")


def test_parse_wiki_members():
    rows = MB.parse_wiki_members(WIKI)
    assert rows == [
        {"name": "Bob Katter", "party": "Katter's Australian Party", "electorate": "Kennedy", "state": "QLD"},
        {"name": "Tony Smith", "party": "Liberal", "electorate": "Casey", "state": "VIC"},
        {"name": "Matt Smith", "party": "Liberal", "electorate": "Leichhardt", "state": "QLD"}]
    assert MB.parse_wiki_members(LATER)[0]["party"] == "One Nation"  # [[...|X]] party link


def test_party_terms_from_wiki(tmp_path):
    ov = fake_repo(tmp_path, [["Robert Katter", "Kennedy", "bob_katter", "Bob Katter", "aph_48"]])
    _write(ov / "party_mapping.csv", ["variant", "canonical_party"],
           [["Liberal", "Liberal Party of Australia"], ["One Nation", "Pauline Hanson's One Nation"]])
    _write(ov / "political_blocs.csv", ["party", "bloc"],
           [["Liberal Party of Australia", "Coalition"], ["Liberal National Party", "Coalition"]])
    _write(ov / "party_terms.csv", MB.PARTY_HEADER,
           [["tony_smith", "house", "47", "Liberal Party of Australia", "Coalition", "wikipedia_47"]])
    _write(ov / "unknown_party.csv", MB.UNKNOWN_HEADER, [])
    MB.resolve("house", 48, root=tmp_path, out=io.StringIO())
    _write(tmp_path / "pdfs" / "manifest.csv", MAN_HEADER, [])
    out = io.StringIO()
    # the start-of-term revision wins over the later one (Katter keeps KAP, not One Nation)
    counts = MB.party_terms("house", 48, [WIKI, LATER], root=tmp_path, out=out)
    assert counts == {"added": 3, "unknown": 0, "already": 0}
    rows = [list(r.values()) for r in _read(ov / "party_terms.csv")]
    assert rows == [
        ["bob_katter", "house", "48", "Katter's Australian Party", "Crossbench", "wikipedia_48"],
        ["matt_smith", "house", "48", "Liberal National Party", "Coalition", "wikipedia_48"],  # QLD
        ["tony_smith", "house", "47", "Liberal Party of Australia", "Coalition", "wikipedia_47"],
        ["tony_smith", "house", "48", "Liberal Party of Australia", "Coalition", "wikipedia_48"]]
    assert MB.party_terms("house", 48, [WIKI], root=tmp_path, out=io.StringIO())["already"] == 3
    # a member no revision lists goes to unknown_party.csv
    (ov / "party_terms.csv").write_text(",".join(MB.PARTY_HEADER) + "\n")
    counts = MB.party_terms("house", 48, [LATER], root=tmp_path, out=out)
    assert counts["unknown"] == 1 and "UNKNOWN matt_smith" in out.getvalue()
    assert _read(ov / "unknown_party.csv")[0]["member_id"] == "matt_smith"


def test_paths_parliament_and_chamber():
    assert MB._parliament("pdfs/48/dickm_48p.pdf") == 48
    assert MB._parliament("pdfs/senate/48/cashm_48s.json") == 48
    assert MB._chamber("pdfs/48/dickm_48p.pdf") == "house"
    assert MB._chamber("pdfs/senate/48/cashm_48s.json") == "senate"


def _senate_repo(tmp_path):
    """fake_repo + two Senate payloads: an ex-MP (Tony Smith, by name alone, since his alias
    carries a House seat) and a new Queensland Liberal senator."""
    import json

    ov = fake_repo(tmp_path)
    man = _read(tmp_path / "pdfs" / "manifest.csv")
    payloads = {"smitht_48s.json": ("Tony Smith", "Victoria", "Liberal Party of Australia"),
                "nobodyn_48s.json": ("Nancy Nobody", "Queensland", "The Nationals")}
    for fn, (name, state, party) in payloads.items():
        path = tmp_path / "pdfs" / "senate" / "48" / fn
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"senatorInterestStatement": {
            "senatorName": name, "electorateState": state, "senatorParty": party}}))
        man.append({"chamber": "senate", "parliament": "48", "member_name": name,
                    "electorate_or_state": state, "source_url": "", "listed_date": "",
                    "pdf_path": f"pdfs/senate/48/{fn}", "pdf_sha256": "x", "page_count": "1",
                    "fetched_at": ""})
    _write(tmp_path / "pdfs" / "manifest.csv", MAN_HEADER, [list(r.values()) for r in man])
    _write(ov / "party_mapping.csv", ["variant", "canonical_party"],
           [["The Nationals", "National Party of Australia"]])
    _write(ov / "political_blocs.csv", ["party", "bloc"],
           [["Liberal Party of Australia", "Coalition"], ["Liberal National Party", "Coalition"]])
    _write(ov / "party_terms.csv", MB.PARTY_HEADER,
           [["tony_smith", "house", "47", "Liberal Party of Australia", "Coalition", "wikipedia_47"]])
    _write(ov / "unknown_party.csv", MB.UNKNOWN_HEADER, [])
    return ov


def test_senate_members_and_party_terms(tmp_path):
    ov = _senate_repo(tmp_path)
    out = io.StringIO()
    counts = MB.resolve("senate", 48, root=tmp_path, out=out)
    assert counts == {"returning": 1, "new": 1, "already": 0, "collisions": 0}
    assert "CROSS-CHAMBER Tony Smith (Victoria) -> tony_smith (House 47)" in out.getvalue()
    rows = {r["pdf_path"]: r for r in _read(ov / "pdf_members.csv")}
    assert rows["pdfs/senate/48/smitht_48s.json"]["member_id"] == "tony_smith"
    assert rows["pdfs/senate/48/nobodyn_48s.json"]["member_id"] == "nancy_nobody"
    assert {r["source"] for p, r in rows.items() if "/senate/" in p} == {"aph_senate_48"}
    assert ["Nancy Nobody", "Queensland", "nancy_nobody", "Nancy Nobody", "aph_senate_48"] in [
        list(r.values()) for r in _read(ov / "member_aliases.csv")]
    counts = MB.senate_party_terms(48, root=tmp_path, out=io.StringIO())
    assert counts == {"added": 2, "unknown": 0, "already": 0}
    senate = [list(r.values()) for r in _read(ov / "party_terms.csv") if r["chamber"] == "senate"]
    assert senate == [
        # a Queensland National is LNP (v1's convention, as for the House)
        ["nancy_nobody", "senate", "48", "Liberal National Party", "Coalition", "aph_senate_api"],
        ["tony_smith", "senate", "48", "Liberal Party of Australia", "Coalition", "aph_senate_api"]]
    assert MB.senate_party_terms(48, root=tmp_path, out=io.StringIO())["already"] == 2
    # House party terms ignore the Senate rows of the same parliament
    assert MB.party_terms("house", 48, [WIKI], root=tmp_path, out=io.StringIO())["added"] == 0


def test_real_48th_senate_members():
    """Every Senate 48th source document has a pdf_members row and a senate party term; the four
    ex-MPs keep their House member_id (eyeballed in T3.7)."""
    rows = _read(REPO / "data" / "overrides" / "pdf_members.csv")
    man = sorted(r["pdf_path"] for r in _read(REPO / "pdfs" / "manifest.csv")
                 if r["chamber"] == "senate" and r["parliament"] == "48")
    sen = {r["pdf_path"]: r["member_id"] for r in rows if r["pdf_path"].startswith("pdfs/senate/48/")}
    assert sorted(sen) == man and len(man) == 76 and len(set(sen.values())) == 76
    for path, mid in [("anandarajahm_48s.json", "michelle_ananda_rajah"),
                      ("hendersons_48s.json", "sarah_henderson"),
                      ("oneilld_48s.json", "deborah_o_neill"),
                      ("sharmad_48s.json", "dave_sharma")]:
        assert sen[f"pdfs/senate/48/{path}"] == mid
    ov = Overrides(REPO / "data" / "overrides")
    for mid in sen.values():
        pt = ov.party_terms[(mid, "senate", 48)]
        assert pt["source"] == "aph_senate_api" and pt["political_bloc"] in {
            "Coalition", "Labor", "Crossbench"}
