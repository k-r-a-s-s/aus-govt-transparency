import copy
import hashlib
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def template() -> dict:
    """A schema-valid extraction document (pdf_path/sha not yet real)."""
    return copy.deepcopy(json.loads((FIXTURES / "extraction_template.json").read_text()))


@pytest.fixture
def fake_repo(tmp_path, monkeypatch, template):
    """A tmp repo root (cwd) holding a real 3-page PDF at the template's pdf_path.

    Returns (root, doc) where doc is a fully valid extraction for that PDF.
    """
    import pymupdf

    pdf_rel = Path(template["pdf_path"])
    pdf = tmp_path / pdf_rel
    pdf.parent.mkdir(parents=True)
    d = pymupdf.open()
    for i in range(template["page_count"]):
        page = d.new_page()
        page.insert_text((72, 72), f"Fixture page {i + 1}")
    d.save(pdf)
    d.close()
    doc = copy.deepcopy(template)
    doc["pdf_sha256"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
    monkeypatch.chdir(tmp_path)
    return tmp_path, doc


def write_json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))
    return path
