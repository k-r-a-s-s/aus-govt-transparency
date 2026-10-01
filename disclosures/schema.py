"""Extraction contract (ADR-2): Pydantic v2 models and the generated JSON Schema.

Models are strict (no type coercion: "5" is not an int, "true" is not a bool), so the
validator agrees with the committed JSON Schema. Regenerate the committed schema with:

    python -m disclosures.schema --write
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Annotated, List, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

SCHEMA_VERSION = "2.0"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "extraction.schema.json"

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def _check_calendar_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    try:
        _dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"not a real calendar date: {value!r}") from exc
    return value


def _check_datetime(value: str) -> str:
    try:
        _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"not an ISO 8601 datetime: {value!r}") from exc
    return value


IsoDate = Annotated[str, Field(pattern=DATE_PATTERN), AfterValidator(_check_calendar_date)]
IsoDateTime = Annotated[str, AfterValidator(_check_datetime)]

Owner = Literal["self", "spouse", "dependent_child", "unknown"]
ChangeType = Literal["initial", "added", "removed", "varied", "unknown"]
DatePrecision = Literal["day", "month", "year", "unknown"]
Confidence = Literal["high", "medium", "low"]


class Item(BaseModel):
    """One disclosed interest (one row / one company in a cell)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    section: int = Field(ge=1, le=14, description="Official section number 1-14.")
    subsection: Optional[str] = Field(description='e.g. "2(i)", "2(ii)"; null if none.')
    owner: Owner
    entity_name: Optional[str] = Field(description="Company/bank/organisation/person/trust named, as printed.")
    description: str = Field(description="Verbatim-ish text of this item only.")
    location: Optional[str] = Field(description="Section 3 (real estate) location.")
    purpose: Optional[str] = Field(description="Section 3 (real estate) purpose.")
    is_alteration: bool
    change_type: ChangeType
    lodged_date: Optional[IsoDate]
    date_precision: DatePrecision
    page: int = Field(ge=1, description="1-based page of the source PDF.")
    confidence: Confidence


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class Extraction(BaseModel):
    """One extraction file = one source PDF."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["2.0"]
    source_id: str = Field(min_length=1, description="e.g. workflow-claude, gemini-api, gold.")
    model: str
    extracted_at: IsoDateTime
    pdf_path: str = Field(min_length=1, description="Repo-relative path to the PDF.")
    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int = Field(ge=1)
    pages_covered: List[Annotated[int, Field(ge=1)]]
    chamber: Literal["house", "senate"]
    parliament: int = Field(ge=43, le=48)
    member_name_as_printed: str
    electorate_or_state: str
    statement_date: Optional[IsoDate]
    items: List[Item]
    extraction_notes: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[IsoDate] = None
    usage: Optional[Usage] = None


def schema_json() -> str:
    """The canonical serialised JSON Schema (what is committed)."""
    return json.dumps(Extraction.model_json_schema(), indent=2, sort_keys=True) + "\n"


def write_schema(path: Path = SCHEMA_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(schema_json(), encoding="utf-8")
    return path


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m disclosures.schema")
    parser.add_argument("--write", action="store_true", help=f"write {SCHEMA_PATH}")
    parser.add_argument("--check", action="store_true", help="exit 1 if the committed schema is stale")
    args = parser.parse_args(argv)
    if args.write:
        print(f"wrote {write_schema()}")
        return 0
    if args.check:
        ok = SCHEMA_PATH.exists() and SCHEMA_PATH.read_text(encoding="utf-8") == schema_json()
        print("schema up to date" if ok else "schema STALE: run python -m disclosures.schema --write")
        return 0 if ok else 1
    sys.stdout.write(schema_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
