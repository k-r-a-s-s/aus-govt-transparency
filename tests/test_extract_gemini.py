"""Gemini extractor (ADR-5) with a fake client: no network, no API (ADR-11)."""
import argparse
import io
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest
from google.genai import errors, types

from disclosures import extract_gemini as eg
from disclosures.cli import main
from disclosures.gemini_model import DEFAULT_GEMINI_MODEL, resolve_api_key, resolve_gemini_model
from disclosures.schema import Item
from disclosures.validate import validate_file

REPO = Path(__file__).resolve().parent.parent
RANGE_RE = re.compile(r"pages (\d+)–(\d+) of a (\d+)-page PDF")


# --------------------------------------------------------------------------- helpers

def make_pdf(root: Path, rel: str, pages: int) -> str:
    pdf = root / rel
    pdf.parent.mkdir(parents=True, exist_ok=True)
    d = pymupdf.open()
    for i in range(pages):
        d.new_page().insert_text((72, 72), f"Source page {i + 1}")
    d.save(pdf)
    d.close()
    return rel


def item(page, entity="BHP Group Limited", section=1, owner="self", description=None, **kw):
    it = {"section": section, "subsection": None, "owner": owner, "entity_name": entity,
          "description": description or entity or "x", "location": None, "purpose": None,
          "is_alteration": False, "change_type": "initial", "lodged_date": "2016-08-30",
          "date_precision": "day", "page": page, "confidence": "high"}
    it.update(kw)
    return it


def response(data=None, *, text=None, finish="STOP", tin=100, tout=50, thoughts=None):
    return SimpleNamespace(
        text=text if text is not None else json.dumps(data),
        candidates=[SimpleNamespace(finish_reason=getattr(types.FinishReason, finish))],
        usage_metadata=SimpleNamespace(prompt_token_count=tin, candidates_token_count=tout,
                                       thoughts_token_count=thoughts))


def chunk_doc(items, name="", electorate="", date=None, notes=""):
    return {"member_name_as_printed": name, "electorate_or_state": electorate,
            "statement_date": date, "extraction_notes": notes, "items": items}


class FakeModels:
    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    def generate_content(self, *, model, contents, config):
        part, text = contents
        m = RANGE_RE.search(text)
        assert m, "chunk preamble missing"
        start, end, total = map(int, m.groups())
        if part.inline_data is not None:
            with pymupdf.open(stream=part.inline_data.data, filetype="pdf") as d:
                assert d.page_count == end - start + 1
        assert config.response_json_schema == eg.response_schema()
        assert config.temperature == 0 and config.response_mime_type == "application/json"
        self.calls.append((model, start, end, total))
        r = self.responder(start, end, len(self.calls))
        if isinstance(r, Exception):
            raise r
        return r


class FakeFiles:
    def __init__(self):
        self.uploaded, self.deleted = [], []

    def upload(self, *, file, config):
        data = file.read() if isinstance(file, io.BytesIO) else Path(file).read_bytes()
        f = SimpleNamespace(name=f"files/{len(self.uploaded)}", uri=f"https://x/{len(self.uploaded)}",
                            mime_type=config.mime_type, data=data)
        self.uploaded.append(f)
        return f

    def delete(self, *, name):
        self.deleted.append(name)


class FakeClient:
    def __init__(self, responder):
        self.models = FakeModels(responder)
        self.files = FakeFiles()


def run(paths, client, **kw):
    out = io.StringIO()
    kw.setdefault("sleep", lambda s: None)
    kw.setdefault("now", lambda: "2026-10-01T00:00:00+00:00")
    res = eg.extract_pdfs(paths, client=client, model="gemini-3.8-flash", out=out, **kw)
    return res, out.getvalue()


def one_item_per_page(start, end, relative=False):
    return chunk_doc([item(p - start + 1 if relative else p, entity=f"Company {p}") for p in range(start, end + 1)],
                     name="Jane Fixture" if start == 1 else "", electorate="Testville" if start == 1 else "",
                     date="2016-08-30" if start == 1 else None)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


OUT = Path("extractions/gemini-api/house/45/big_45p.json")


# --------------------------------------------------------------------------- page offsets

@pytest.mark.parametrize("relative", [False, True])
def test_chunk_offsets_give_absolute_pages(repo, relative):
    rel = make_pdf(repo, "pdfs/45/big_45p.pdf", 45)
    client = FakeClient(lambda s, e, n: response(one_item_per_page(s, e, relative=relative)))
    res, log = run([rel], client)
    assert res.exit_code == 0, log
    assert [(c[1], c[2]) for c in client.models.calls] == [(1, 20), (21, 40), (41, 45)]
    doc = json.loads((repo / OUT).read_text())
    assert [it["page"] for it in doc["items"]] == list(range(1, 46))
    assert [it["entity_name"] for it in doc["items"]] == [f"Company {p}" for p in range(1, 46)]
    assert doc["pages_covered"] == list(range(1, 46)) and doc["page_count"] == 45
    assert (doc["source_id"], doc["model"], doc["chamber"], doc["parliament"]) == \
        ("gemini-api", "gemini-3.8-flash", "house", 45)
    assert doc["member_name_as_printed"] == "Jane Fixture" and doc["statement_date"] == "2016-08-30"
    assert validate_file(repo / OUT) == []
    assert "1 ok, 0 failed" in log


def test_relative_rule_is_unambiguous_for_every_chunk():
    """Every chunk that starts after page 1 starts after its own length (docstring claim)."""
    def ranges(s, e):
        yield s, e
        if s < e:
            mid = (s + e) // 2
            yield from ranges(s, mid)
            yield from ranges(mid + 1, e)

    for pc in range(1, 90):
        for cp in (1, 3, 20):
            for s0, e0 in eg.chunk_ranges(pc, cp):
                for s, e in ranges(s0, e0):
                    assert s == 1 or s > e - s + 1, (pc, cp, s, e)


def test_page_outside_chunk_fails_pdf(repo):
    rel = make_pdf(repo, "pdfs/45/big_45p.pdf", 45)
    # chunk 21-40 returns page 45: neither all-relative nor inside the chunk
    client = FakeClient(lambda s, e, n: response(chunk_doc([item(45 if s == 21 else s)])))
    res, log = run([rel], client)
    assert res.exit_code == 1 and not (repo / OUT).exists()
    assert "outside the chunk: [45]" in res.failed[rel]


# --------------------------------------------------------------------------- MAX_TOKENS re-split

def test_max_tokens_resplits_in_halves_and_merges(repo):
    rel = make_pdf(repo, "pdfs/45/big_45p.pdf", 45)

    def responder(s, e, n):
        if e - s + 1 > 5:  # anything over 5 pages "truncates"
            return response(text='{"items": [', finish="MAX_TOKENS", tin=10, tout=65536)
        return response(one_item_per_page(s, e), tin=10, tout=5)

    client = FakeClient(responder)
    res, log = run([rel], client)
    assert res.exit_code == 0, log
    calls = [(c[1], c[2]) for c in client.models.calls]
    assert calls[:3] == [(1, 20), (1, 10), (1, 5)]
    assert (6, 10) in calls and (11, 15) in calls and (41, 45) in calls
    doc = json.loads((repo / OUT).read_text())
    assert [it["page"] for it in doc["items"]] == list(range(1, 46))
    assert validate_file(repo / OUT) == []
    # usage sums every call, the truncated ones included
    n_trunc = sum(1 for s, e in calls if e - s + 1 > 5)
    n_ok = len(calls) - n_trunc
    assert doc["usage"] == {"input_tokens": 10 * len(calls), "output_tokens": 65536 * n_trunc + 5 * n_ok}


def test_invalid_json_also_resplits(repo):
    rel = make_pdf(repo, "pdfs/45/small_45p.pdf", 2)
    client = FakeClient(lambda s, e, n: response(text="not json") if s != e else response(one_item_per_page(s, e)))
    res, _ = run([rel], client)
    assert res.exit_code == 0
    assert [(c[1], c[2]) for c in client.models.calls] == [(1, 2), (1, 1), (2, 2)]


def test_failure_at_one_page_chunk_writes_nothing_and_exits_nonzero(repo, capsys):
    bad = make_pdf(repo, "pdfs/45/bad_45p.pdf", 3)
    good = make_pdf(repo, "pdfs/46/good_46p.pdf", 2)

    def responder(s, e, n):  # the PDF is identified by the page count in the preamble
        total = client.models.calls[-1][3]
        if total == 3 and s <= 2 <= e:
            return response(text="{", finish="MAX_TOKENS")
        return response(one_item_per_page(s, e))

    client = FakeClient(responder)
    res, log = run([bad, good], client)
    assert res.exit_code == 1
    assert not (repo / "extractions/gemini-api/house/45/bad_45p.json").exists()
    assert not list((repo / "extractions/gemini-api/house").glob("45/*"))
    assert (repo / "extractions/gemini-api/house/46/good_46p.json").exists()  # others still processed
    assert "1 ok, 1 failed" in log
    assert "Failed PDFs:" in log and f"  {bad}: page 2: finish_reason MAX_TOKENS even as a 1-page chunk" in log
    assert (2, 2) in [(c[1], c[2]) for c in client.models.calls if c[3] == 3]


def test_cli_exit_code_nonzero_on_failure(repo, capsys):
    rel = make_pdf(repo, "pdfs/45/one_45p.pdf", 1)
    client = FakeClient(lambda s, e, n: response(text="{", finish="MAX_TOKENS"))
    args = argparse.Namespace(source="gemini", model=None, out_root=eg.DEFAULT_OUT_ROOT, chunk_pages=20,
                              max_retries=0, force=False, batch=False, pdfs=[rel])
    assert eg.run(args, client=client, env={}) == 1
    out = capsys.readouterr().out
    assert "0 ok, 1 failed" in out and rel in out
    assert not (repo / "extractions").exists() or not list((repo / "extractions").rglob("*.json"))


def test_safety_finish_reason_fails_without_resplit(repo):
    rel = make_pdf(repo, "pdfs/45/s_45p.pdf", 4)
    client = FakeClient(lambda s, e, n: response(chunk_doc([]), finish="SAFETY"))
    res, _ = run([rel], client)
    assert res.exit_code == 1 and "finish_reason SAFETY" in res.failed[rel]
    assert len(client.models.calls) == 1


# --------------------------------------------------------------------------- merge / dedup

def test_merge_dedups_across_chunk_boundaries():
    dup = item(20, entity="Westpac", section=6)
    a = eg.ChunkResult(1, 20, chunk_doc([item(1), dup], name="Jane", notes="p3 faint"))
    b = eg.ChunkResult(21, 40, chunk_doc([dict(dup), item(21, entity="NAB")], electorate="Testville",
                                         date="2016-08-30", notes="  "))
    m = eg.merge_chunks([b, a])  # order of arrival does not matter
    assert [(it["page"], it["entity_name"]) for it in m["items"]] == \
        [(1, "BHP Group Limited"), (20, "Westpac"), (21, "NAB")]
    assert (m["member_name_as_printed"], m["electorate_or_state"], m["statement_date"]) == \
        ("Jane", "Testville", "2016-08-30")
    assert m["extraction_notes"] == "pages 1-20: p3 faint"


def test_dedup_drops_exact_repeats_but_keeps_distinct_items_sharing_adr5_key(repo):
    rel = make_pdf(repo, "pdfs/45/d_45p.pdf", 2)
    loan_a = item(1, entity="Westpac", section=6, description="Westpac home loan")
    loan_b = item(1, entity="Westpac", section=6, description="Westpac investment loan")
    client = FakeClient(lambda s, e, n: response(chunk_doc([loan_a, dict(loan_a), loan_b, item(2)])))
    res, _ = run([rel], client)
    doc = json.loads((repo / "extractions/gemini-api/house/45/d_45p.json").read_text())
    assert [it["description"] for it in doc["items"]] == \
        ["Westpac home loan", "Westpac investment loan", "BHP Group Limited"]


def test_extra_item_keys_dropped_and_usage_includes_thoughts(repo):
    rel = make_pdf(repo, "pdfs/45/u_45p.pdf", 1)
    it = dict(item(1), bogus="x")
    client = FakeClient(lambda s, e, n: response(chunk_doc([it]), tin=7, tout=3, thoughts=11))
    res, _ = run([rel], client)
    doc = json.loads((repo / "extractions/gemini-api/house/45/u_45p.json").read_text())
    assert "bogus" not in doc["items"][0]
    assert doc["usage"] == {"input_tokens": 7, "output_tokens": 14}


def test_usage_summed_over_chunks_and_cost(repo):
    rel = make_pdf(repo, "pdfs/45/big_45p.pdf", 45)
    client = FakeClient(lambda s, e, n: response(one_item_per_page(s, e), tin=1000, tout=500))
    res, log = run([rel], client)
    doc = json.loads((repo / OUT).read_text())
    assert doc["usage"] == {"input_tokens": 3000, "output_tokens": 1500}
    assert res.usage.input_tokens == 3000 and res.usage.calls == 3
    assert eg.estimate_cost_usd(1_000_000, 1_000_000) == pytest.approx(4.5)
    assert "tokens 3000 in / 1500 out over 3 calls" in log and "2026-12-31" in log


# --------------------------------------------------------------------------- retries

def _api_error(code):
    cls = errors.ServerError if code >= 500 else errors.ClientError
    return cls(code, {"error": {"code": code, "message": "m", "status": "S"}})


def test_retry_on_429_then_success_without_real_sleep(repo):
    rel = make_pdf(repo, "pdfs/45/r_45p.pdf", 1)
    slept = []
    script = [_api_error(429), _api_error(503)]
    client = FakeClient(lambda s, e, n: script.pop(0) if script else response(one_item_per_page(s, e)))
    res, _ = run([rel], client, sleep=slept.append)
    assert res.exit_code == 0 and len(client.models.calls) == 3
    assert len(slept) == 2 and slept[1] > slept[0] - 1  # exponential (with <1 s jitter)


def test_402_not_retried(repo):
    rel = make_pdf(repo, "pdfs/45/p_45p.pdf", 1)
    slept = []
    client = FakeClient(lambda s, e, n: _api_error(402))
    res, log = run([rel], client, sleep=slept.append)
    assert res.exit_code == 1 and len(client.models.calls) == 1 and slept == []
    assert "API error 402" in res.failed[rel]
    assert not (repo / "extractions/gemini-api/house/45/p_45p.json").exists()


def test_retries_exhausted(repo):
    rel = make_pdf(repo, "pdfs/45/x_45p.pdf", 1)
    client = FakeClient(lambda s, e, n: _api_error(500))
    res, _ = run([rel], client, max_retries=2)
    assert res.exit_code == 1 and len(client.models.calls) == 3


# --------------------------------------------------------------------------- files API, idempotence, output

def test_large_chunk_uses_files_api_and_deletes(repo):
    rel = make_pdf(repo, "pdfs/45/f_45p.pdf", 2)

    def responder(s, e, n):
        return response(one_item_per_page(s, e))

    client = FakeClient(responder)
    res, _ = run([rel], client, files_threshold=0)
    assert res.exit_code == 0
    assert len(client.files.uploaded) == 1 and client.files.deleted == ["files/0"]


def test_skip_existing_valid_unless_force(repo):
    rel = make_pdf(repo, "pdfs/45/i_45p.pdf", 1)
    client = FakeClient(lambda s, e, n: response(one_item_per_page(s, e)))
    run([rel], client)
    res, log = run([rel], client)
    assert res.skipped == [rel] and len(client.models.calls) == 1 and "0 ok, 0 failed, 1 skipped" in log
    res, _ = run([rel], client, force=True)
    assert res.ok == [rel] and len(client.models.calls) == 2


def test_invalid_output_not_left_on_disk(repo):
    rel = make_pdf(repo, "pdfs/45/v_45p.pdf", 1)
    bad = item(1, lodged_date="2016-08-15", date_precision="month")  # fails the validator guard
    client = FakeClient(lambda s, e, n: response(chunk_doc([bad])))
    res, _ = run([rel], client)
    assert res.exit_code == 1 and "failed validation" in res.failed[rel]
    assert list((repo / "extractions").rglob("*")) == [p for p in (repo / "extractions").rglob("*") if p.is_dir()]


def test_senate_path_and_bad_path(repo):
    sen = make_pdf(repo, "pdfs/senate/48/s.pdf", 1)
    odd = make_pdf(repo, "other/x.pdf", 1)
    client = FakeClient(lambda s, e, n: response(one_item_per_page(s, e)))
    res, _ = run([sen, odd, "pdfs/45/missing.pdf"], client)
    assert res.ok == [sen] and (repo / "extractions/gemini-api/senate/48/s.json").exists()
    assert "cannot infer chamber/parliament" in res.failed[odd]
    assert "PDF not found" in res.failed["pdfs/45/missing.pdf"]


def test_unparseable_statement_date_nulled(repo):
    rel = make_pdf(repo, "pdfs/45/sd_45p.pdf", 1)
    client = FakeClient(lambda s, e, n: response(chunk_doc([item(1)], date="2016-02-30")))
    res, _ = run([rel], client)
    doc = json.loads((repo / "extractions/gemini-api/house/45/sd_45p.json").read_text())
    assert doc["statement_date"] is None and "unparseable" in doc["extraction_notes"]


def test_batch_not_implemented(repo):
    with pytest.raises(NotImplementedError, match="--batch"):
        eg.extract_pdfs([], client=None, model="gemini-3.8-flash", batch=True)
    assert main(["extract", "--source", "gemini", "--batch", "pdfs/45/x.pdf"]) == 2


# --------------------------------------------------------------------------- response schema

def test_response_schema_item_fields_match_pydantic_item():
    s = eg.response_schema()
    props = s["properties"]["items"]["items"]["properties"]
    assert list(props) == list(Item.model_fields)
    assert s["properties"]["items"]["items"]["required"] == list(Item.model_fields)
    assert set(s["required"]) == {"member_name_as_printed", "electorate_or_state", "statement_date",
                                  "extraction_notes", "items"}
    blob = json.dumps(s)
    for banned in ('"$ref"', '"pattern"', '"format"', '"$defs"', '"anyOf"'):
        assert banned not in blob


# --------------------------------------------------------------------------- model resolver (AC-2.2a)

BANNED = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-pro"]


@pytest.mark.parametrize("model", BANNED)
def test_resolver_rejects_banned_from_arg(model):
    with pytest.raises(ValueError, match=re.escape(model) + r".*argument"):
        resolve_gemini_model(model, env={})
    with pytest.raises(ValueError):
        resolve_gemini_model("models/" + model, env={})


@pytest.mark.parametrize("model", BANNED)
def test_resolver_rejects_banned_from_env(model):
    with pytest.raises(ValueError, match=re.escape(model) + r".*GEMINI_MODEL"):
        resolve_gemini_model(None, env={"GEMINI_MODEL": model})


def test_resolver_accepts_3x_and_default():
    assert resolve_gemini_model("gemini-3.8-flash", env={}) == "gemini-3.8-flash"
    assert resolve_gemini_model("models/gemini-3.8-flash", env={}) == "gemini-3.8-flash"
    assert resolve_gemini_model(None, env={"GEMINI_MODEL": "gemini-3.7-flash"}) == "gemini-3.7-flash"
    assert resolve_gemini_model("gemini-3.8-flash", env={"GEMINI_MODEL": "gemini-2.0-flash"}) == "gemini-3.8-flash"
    assert resolve_gemini_model(None, env={}) == DEFAULT_GEMINI_MODEL == "gemini-3.8-flash"
    assert resolve_gemini_model(None, env={"GEMINI_MODEL": "  "}) == "gemini-3.8-flash"


def test_cli_rejects_banned_model_and_missing_key(repo, capsys):
    args = argparse.Namespace(source="gemini", model="gemini-2.5-flash", out_root="x", chunk_pages=20,
                              max_retries=0, force=False, batch=False, pdfs=["pdfs/45/a.pdf"])
    assert eg.run(args, env={}) == 2
    assert "banned" in capsys.readouterr().err
    args.model = None
    assert eg.run(args, env={}) == 2
    err = capsys.readouterr().err
    assert "no API key" in err and "Traceback" not in err
    assert resolve_api_key({"GEMINI_API_KEY": "k2"}) == "k2"
    assert resolve_api_key({"GOOGLE_API_KEY": "k1", "GEMINI_API_KEY": "k2"}) == "k1"


def test_no_banned_model_ids_in_package():
    r = subprocess.run(["git", "grep", "--untracked", "-nE", r"gemini-(1|2)\.[0-9]", "--", "disclosures/"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 1 and r.stdout == "", r.stdout


def test_extract_is_not_a_stub():
    from disclosures.cli import STUBS

    assert "extract" not in STUBS
