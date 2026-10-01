import os
import subprocess
import sys
from pathlib import Path

from conftest import write_json

from disclosures.cli import main
from disclosures.validate import validate_file, validate_paths

REPO = Path(__file__).resolve().parent.parent


def _cli(*args, cwd):
    env = {**os.environ, "PYTHONPATH": str(REPO)}
    return subprocess.run([sys.executable, "-m", "disclosures", "validate", *args],
                          cwd=cwd, env=env, capture_output=True, text=True)


def test_valid_file_passes(fake_repo, capsys):
    root, doc = fake_repo
    f = write_json(root / "extractions/gold/house/45/fixture_45p.json", doc)
    assert validate_file(f) == []
    assert main(["validate", str(f)]) == 0
    assert "1 valid, 0 invalid" in capsys.readouterr().out


def test_missing_page_rejected_with_file_and_reason(fake_repo):
    root, doc = fake_repo
    doc["pages_covered"] = [1, 3]
    f = write_json(root / "ex/missing_page.json", doc)
    r = _cli(str(f), cwd=root)
    assert r.returncode == 1
    assert f"INVALID {f}" in r.stdout
    assert "missing pages [2]" in r.stdout
    assert "0 valid, 1 invalid" in r.stdout


def test_sha_mismatch_rejected_with_file_and_reason(fake_repo):
    root, doc = fake_repo
    doc["pdf_sha256"] = "f" * 64
    f = write_json(root / "ex/bad_sha.json", doc)
    r = _cli(str(f), cwd=root)
    assert r.returncode == 1
    assert f"INVALID {f}" in r.stdout and "pdf_sha256 mismatch" in r.stdout


def test_directory_mixed_results(fake_repo, capsys):
    root, doc = fake_repo
    write_json(root / "ex/a/good.json", doc)
    bad = dict(doc, page_count=4, pages_covered=[1, 2, 3, 4])
    write_json(root / "ex/b/bad_pages.json", bad)
    write_json(root / "ex/selection.json", {"seed": 1})  # ignored when walking a dir
    res = validate_paths(["ex"])
    assert res["valid"] == [str(Path("ex/a/good.json"))]
    (bad_errs,) = res["invalid"].values()
    assert any("actual PDF page count 3" in e for e in bad_errs)
    assert main(["validate", "ex"]) == 1
    assert "1 valid, 1 invalid" in capsys.readouterr().out


def test_item_page_beyond_page_count(fake_repo):
    root, doc = fake_repo
    doc["items"][0]["page"] = 9
    f = write_json(root / "ex/p.json", doc)
    assert any("items[0].page 9 > page_count 3" in e for e in validate_file(f))


def test_schema_error_and_bad_json_reported(fake_repo):
    root, doc = fake_repo
    doc["items"][0]["owner"] = "partner"
    f = write_json(root / "ex/s.json", doc)
    assert any(e.startswith("schema: items.0.owner") for e in validate_file(f))
    g = root / "ex/broken.json"
    g.write_text("{not json")
    assert validate_file(g)[0].startswith("not valid JSON")


def test_missing_pdf(fake_repo):
    root, doc = fake_repo
    doc["pdf_path"] = "pdfs/45/nope.pdf"
    f = write_json(root / "ex/n.json", doc)
    assert "pdf_path not found: pdfs/45/nope.pdf" in validate_file(f)


# --- pdf_path must stay inside the repo root ---------------------------------------------

def test_pdf_path_traversal_rejected(fake_repo):
    root, doc = fake_repo
    # a real PDF outside the repo root, reachable via ..
    outside = root.parent / "outside.pdf"
    outside.write_bytes((root / doc["pdf_path"]).read_bytes())
    for bad in ("../outside.pdf", "pdfs/../../outside.pdf", "pdfs/45/../x.pdf"):
        doc["pdf_path"] = bad
        f = write_json(root / "ex/t.json", doc)
        errs = validate_file(f)
        assert any("pdf_path" in e and ("'..'" in e or "outside" in e) for e in errs), (bad, errs)


def test_pdf_path_absolute_rejected(fake_repo):
    root, doc = fake_repo
    doc["pdf_path"] = str((root / doc["pdf_path"]).resolve())
    f = write_json(root / "ex/abs.json", doc)
    assert any("must be repo-relative" in e for e in validate_file(f))


def test_pdf_path_symlink_escaping_root_rejected(fake_repo):
    root, doc = fake_repo
    outside_dir = root.parent / "elsewhere"
    outside_dir.mkdir(exist_ok=True)
    (outside_dir / "x.pdf").write_bytes((root / doc["pdf_path"]).read_bytes())
    (root / "linked").symlink_to(outside_dir)
    doc["pdf_path"] = "linked/x.pdf"
    f = write_json(root / "ex/sym.json", doc)
    assert any("resolves outside the repo root" in e for e in validate_file(f))


# --- lodged_date null <=> date_precision unknown -----------------------------------------

def test_null_date_requires_unknown_precision(fake_repo, capsys):
    root, doc = fake_repo
    doc["items"][0]["lodged_date"] = None
    doc["items"][0]["date_precision"] = "day"
    f = write_json(root / "ex/d1.json", doc)
    assert "items[0]: lodged_date null but date_precision 'day'" in validate_file(f)
    assert main(["validate", str(f)]) == 1
    assert f"INVALID {f}: items[0]: lodged_date null but date_precision 'day'" in capsys.readouterr().out


def test_unknown_precision_requires_null_date(fake_repo):
    root, doc = fake_repo
    doc["items"][0]["lodged_date"] = "2019-07-01"
    doc["items"][0]["date_precision"] = "unknown"
    f = write_json(root / "ex/d2.json", doc)
    assert "items[0]: lodged_date 2019-07-01 but date_precision 'unknown'" in validate_file(f)


def test_consistent_dates_accepted(fake_repo):
    root, doc = fake_repo
    doc["items"][0]["lodged_date"] = None
    doc["items"][0]["date_precision"] = "unknown"
    f = write_json(root / "ex/d3.json", doc)
    assert validate_file(f) == []
    doc["items"][0]["lodged_date"] = "2019-07-01"
    doc["items"][0]["date_precision"] = "month"
    f = write_json(root / "ex/d4.json", doc)
    assert validate_file(f) == []
