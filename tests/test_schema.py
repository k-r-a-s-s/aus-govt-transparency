import json

import jsonschema
import pytest
from pydantic import ValidationError

from disclosures.schema import SCHEMA_PATH, Extraction, Item, schema_json


def test_committed_schema_matches_models_byte_for_byte():
    assert SCHEMA_PATH.exists(), "run: python -m disclosures.schema --write"
    assert SCHEMA_PATH.read_text(encoding="utf-8") == schema_json()


def test_template_valid_under_pydantic_and_jsonschema(template):
    Extraction.model_validate(template)
    jsonschema.validate(template, json.loads(SCHEMA_PATH.read_text()))


def test_extra_fields_forbidden(template):
    template["category"] = "shares"
    with pytest.raises(ValidationError):
        Extraction.model_validate(template)
    t2 = json.loads(json.dumps(template))
    del t2["category"]
    t2["items"][0]["interest_type"] = "held"
    with pytest.raises(ValidationError):
        Extraction.model_validate(t2)


@pytest.mark.parametrize("bad", ["2017-02-30", "2017-13-01", "01/02/2017", "2017-2-1"])
def test_dates_must_be_real_iso_dates(template, bad):
    template["items"][0]["lodged_date"] = bad
    with pytest.raises(ValidationError):
        Extraction.model_validate(template)


@pytest.mark.parametrize(
    "field,value",
    [("section", 0), ("section", 15), ("owner", "partner"), ("change_type", "held"),
     ("page", 0), ("confidence", "certain"), ("date_precision", "week")],
)
def test_item_enums_and_ranges(template, field, value):
    item = template["items"][0]
    item[field] = value
    with pytest.raises(ValidationError):
        Item.model_validate(item)


@pytest.mark.parametrize(
    "field,value",
    [("parliament", 42), ("parliament", 49), ("chamber", "lords"), ("page_count", 0),
     ("schema_version", "1.0"), ("pdf_sha256", "abc")],
)
def test_document_enums_and_ranges(template, field, value):
    template[field] = value
    with pytest.raises(ValidationError):
        Extraction.model_validate(template)


def test_optional_review_and_usage_fields(template):
    template["reviewed_by"] = "kevin"
    template["reviewed_at"] = "2026-10-01"
    template["usage"] = {"input_tokens": 10, "output_tokens": 5}
    doc = Extraction.model_validate(template)
    assert doc.reviewed_by == "kevin" and doc.usage.input_tokens == 10
    assert Extraction.model_validate({k: v for k, v in template.items()
                                      if k not in ("reviewed_by", "reviewed_at", "usage")}).reviewed_by is None


def test_item_nullable_fields_are_required_keys(template):
    del template["items"][0]["subsection"]
    with pytest.raises(ValidationError):
        Extraction.model_validate(template)


# --- strict types: the validator must agree with the committed JSON Schema --------------

@pytest.mark.parametrize(
    "field,value",
    [("section", "5"), ("page", "2"), ("is_alteration", "true"), ("is_alteration", 1),
     ("section", True), ("description", 5)],
)
def test_item_wrong_json_types_rejected_by_pydantic_and_jsonschema(template, field, value):
    template["items"][0][field] = value
    with pytest.raises(ValidationError):
        Extraction.model_validate(template)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(template, json.loads(SCHEMA_PATH.read_text()))


def test_float_page_rejected_by_pydantic(template):
    # JSON Schema counts 2.0 as an integer; the strict validator is stricter still (fine).
    template["items"][0]["page"] = 2.0
    with pytest.raises(ValidationError):
        Extraction.model_validate(template)


@pytest.mark.parametrize("field,value", [("page_count", "3"), ("parliament", "45"),
                                         ("pages_covered", ["1", "2", "3"])])
def test_document_wrong_json_types_rejected(template, field, value):
    template[field] = value
    with pytest.raises(ValidationError):
        Extraction.model_validate(template)


def test_proper_types_accepted(template):
    item = template["items"][0]
    item.update(section=5, page=2, is_alteration=True, change_type="added")
    doc = Extraction.model_validate(template)
    assert doc.items[0].section == 5 and doc.items[0].is_alteration is True
    jsonschema.validate(template, json.loads(SCHEMA_PATH.read_text()))
