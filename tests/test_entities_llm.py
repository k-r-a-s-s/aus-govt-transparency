"""ADR-6 step 5, the long-tail LLM stage (T2.6): mocked HTTP only, no network (ADR-11)."""
import argparse
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

import httpx
import pytest

from disclosures import entities as E
from disclosures.cli import main
from disclosures.normalise import normalise_entity
from disclosures.entities import (LLMCacheMiss, block_key, check_groups, llm_blocks, llm_plan,
                                  make_llm_runner, read_llm_cache, run_entities)

from test_entities import dump, item_entities, make_data, make_db

REPO = Path(__file__).resolve().parent.parent

# every alias has >= 2 items except "solo pty ltd"
ITEMS = [(f"i{n:02d}", raw) for n, raw in enumerate([
    "Rotary Club of Ballarat", "Rotary Club of Ballarat Inc", "Rotary Club Ballarat",
    "Rotary Club Ballarat", "Smith Family Trust", "Smith Family Trust",
    "Acme Widgets Pty Ltd", "ACME WIDGETS", "Solo Pty Ltd",
])]

BLOCK_RE = re.compile(r"^BLOCK (b\d+)$")
NAME_RE = re.compile(r'^- "([^"]+)":')


def parse_blocks(prompt: str):
    blocks, cur = {}, None
    for line in prompt.splitlines():
        if m := BLOCK_RE.match(line):
            cur = m.group(1)
            blocks[cur] = []
        elif cur and (m := NAME_RE.match(line)):
            blocks[cur].append(m.group(1))
    return blocks


def merge_all(blocks):
    """A mock LLM: every block becomes one group named after its first name."""
    return {"blocks": [{"block_id": bid, "groups": [{
        "members": names, "canonical_name": names[0].title(), "entity_type": "other",
        "confidence": "medium"}]} for bid, names in blocks.items()]}


class Server:
    def __init__(self, reply=merge_all):
        self.reply = reply
        self.bodies = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.bodies.append(body)
        blocks = parse_blocks(body["messages"][0]["content"][0]["text"])
        data = self.reply(blocks)
        if isinstance(data, int):
            return httpx.Response(data, json={"error": {"code": data, "message": "x"}})
        return httpx.Response(200, json={
            "provider": "Google AI Studio",
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(data)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.001}})


def args(**kw):
    a = argparse.Namespace(model=E.LLM_MODEL, provider_order=E.LLM_PROVIDER_ORDER,
                           ignore_providers=E.LLM_IGNORE_PROVIDERS, workers=2, llm_limit=None)
    vars(a).update(kw)
    return a


def runner(server, **kw):
    http = httpx.Client(transport=httpx.MockTransport(server))
    r = make_llm_runner(args(**kw), http=http, env={"OPENROUTER_KEY": "sk-test"})
    r.sleep = lambda s: None
    return r


def setup(tmp_path, items=ITEMS):
    return make_db(tmp_path / "v2.db", items), make_data(tmp_path, generic=())


def test_blocks_first_token_fuzzy_and_min_items():
    counts = {"rotary club of ballarat": 2, "rotary club ballarat": 2, "rotary club of bendigo": 3,
              "rotary": 1, "smith family trust": 2, "acme widgets": 2, "acme": 2}
    blocks = llm_blocks(list(counts), counts)
    assert ["rotary"] not in blocks and all("rotary" not in b for b in blocks)  # 1 item
    assert ["rotary club ballarat", "rotary club of ballarat"] in blocks
    assert ["acme", "acme widgets"] in blocks  # token_set: a subset scores 100
    assert ["smith family trust"] in blocks  # a 1-name block: typed, never merged
    assert sum(len(b) for b in blocks) == 6
    assert blocks == sorted(blocks) and all(b == sorted(b) for b in blocks)


def test_block_key_sorted_and_versioned():
    assert block_key(["b", "a"]) == block_key(["a", "b"])
    assert block_key(["a", "b"]) != block_key(["a", "b"], "entities-llm-v0")


def test_check_groups_requires_a_partition():
    ok = [{"members": ["a"], "canonical_name": "A", "entity_type": "other", "confidence": "high"},
          {"members": ["b"], "canonical_name": "B", "entity_type": "person", "confidence": "low"}]
    assert [g["members"] for g in check_groups(["a", "b"], ok)] == [["a"], ["b"]]
    for bad in (ok[:1], ok + [dict(ok[0])], [dict(ok[0], entity_type="company"), ok[1]],
                [dict(ok[0], canonical_name=" "), ok[1]], None, []):
        with pytest.raises(ValueError):
            check_groups(["a", "b"], bad)


def test_request_shape_and_results(tmp_path):
    db, data = setup(tmp_path)
    server = Server()
    s = run_entities(db, data, offline=False, llm=runner(server))
    assert len(server.bodies) == 1  # 3 blocks, 5 aliases: one packed request
    body = server.bodies[0]
    assert body["model"] == "google/gemini-3.8-flash"
    assert body["provider"] == {"require_parameters": True, "order": ["google-ai-studio/flex"],
                                "allow_fallbacks": False, "ignore": ["azure"]}
    rf = body["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["schema"]["additionalProperties"] is False
    assert body["usage"] == {"include": True} and "plugins" not in body
    content = body["messages"][0]["content"]
    assert len(content) == 1 and content[0]["type"] == "text"
    assert '"Rotary Club of Ballarat Inc" (1)' in content[0]["text"]  # raw spellings shown
    assert s["aliases"]["llm"] == 4 and s["aliases"]["singleton"] == 1
    ie = item_entities(db)
    assert len({ie[f"i{n:02d}"] for n in range(4)}) == 1  # the Rotary block merged
    con = sqlite3.connect(db)
    assert con.execute("select method, confidence from entity_aliases where alias_normalised="
                       "'smith family trust'").fetchone() == ("llm", "medium")
    cache = read_llm_cache(data)
    assert len(cache) == 3
    for k, rec in cache.items():
        assert k == block_key(rec["members"]) and rec["prompt_version"] == E.LLM_PROMPT_VERSION
    lines = (data / E.LLM_CACHE_FILE).read_text().splitlines()
    assert [json.loads(l)["key"] for l in lines] == sorted(cache)  # rewritten sorted


def test_cache_hit_makes_no_http_call(tmp_path):
    db, data = setup(tmp_path)
    run_entities(db, data, offline=False, llm=runner(Server()))
    first = dump(db)

    def no_calls(blocks):
        raise AssertionError("HTTP call on a cached block")

    server = Server(no_calls)
    run_entities(db, data, offline=False, llm=runner(server))
    assert server.bodies == [] and dump(db) == first
    run_entities(db, data, offline=True)  # and offline reads the same cache
    assert dump(db) == first


def test_offline_missing_block_exits_1_and_writes_nothing(tmp_path, capsys):
    db, data = setup(tmp_path)
    before = dump(db)
    rc = main(["entities", "--db", str(db), "--data", str(data), "--offline"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "3 long-tail block(s) uncached" in err and "rotary club ballarat | rotary club of ballarat" in err
    assert dump(db) == before
    assert not (data / E.LLM_CACHE_FILE).exists()


def test_bad_block_retried_alone_then_left_uncached(tmp_path):
    db, data = setup(tmp_path)

    def drop_smith(blocks):
        out = merge_all(blocks)
        for b in out["blocks"]:
            b["groups"] = [g for g in b["groups"] if g["members"] != ["smith family trust"]]
        return out

    server = Server(drop_smith)
    with pytest.raises(LLMCacheMiss) as exc:
        run_entities(db, data, offline=False, llm=runner(server))
    assert exc.value.blocks == [["smith family trust"]]
    assert len(server.bodies) == 2  # the pack, then the bad block alone once
    assert len(read_llm_cache(data)) == 2  # the good blocks were kept
    # a later run only asks for the missing block
    server2 = Server()
    run_entities(db, data, offline=False, llm=runner(server2))
    assert len(server2.bodies) == 1 and list(parse_blocks(
        server2.bodies[0]["messages"][0]["content"][0]["text"]).values()) == [["smith family trust"]]


def test_http_error_and_request_limit(tmp_path):
    db, data = setup(tmp_path)
    with pytest.raises(LLMCacheMiss):
        run_entities(db, data, offline=False, llm=runner(Server(lambda b: 400)))
    assert read_llm_cache(data) == {}
    server = Server()
    r = runner(server, llm_limit=1)
    r.pack_size = 2  # 3 packs, only 1 sent
    with pytest.raises(LLMCacheMiss) as exc:
        run_entities(db, data, offline=False, llm=r)
    assert len(server.bodies) == 1 and len(exc.value.blocks) == 2


def test_runner_needs_key_and_rejects_banned_gemini():
    with pytest.raises(ValueError, match="no OpenRouter key"):
        make_llm_runner(args(), env={})
    with pytest.raises(ValueError, match="banned"):
        make_llm_runner(args(model="google/gemini-2.5-flash"), env={"OPENROUTER_KEY": "k"})


def test_dry_run_counts_without_calls(tmp_path, capsys):
    db, data = setup(tmp_path)
    plan = llm_plan(db, data)
    assert plan == {**plan, "blocks": 3, "multi": 1, "aliases": 4, "items": 8, "uncached": 3,
                    "requests": 1}
    assert main(["entities", "--db", str(db), "--data", str(data), "--llm-dry-run"]) == 0
    assert "3 uncached -> 1 requests" in capsys.readouterr().out
    assert dump(db)["entities"] == []


def test_real_llm_cache_is_well_formed():
    path = REPO / "data" / "entities" / E.LLM_CACHE_FILE
    if not path.exists():
        pytest.skip("no committed long-tail cache yet")
    lines = path.read_text(encoding="utf-8").splitlines()
    recs = [json.loads(l) for l in lines]
    assert [r["key"] for r in recs] == sorted({r["key"] for r in recs})  # sorted, unique
    for r in recs:
        assert r["key"] == block_key(r["members"], r["prompt_version"])
        assert check_groups(r["members"], r["groups"]) == r["groups"]


def test_real_db_uses_llm_and_resolves_everything():
    db = REPO / "disclosures_v2.db"
    if not db.exists() or not (REPO / "data" / "entities" / E.LLM_CACHE_FILE).exists():
        pytest.skip("needs the built DB and the long-tail cache")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    methods = dict(con.execute("select method, count(*) from entity_aliases group by 1"))
    if not methods:
        pytest.skip("entities not run on this DB")
    assert methods.get("llm", 0) > 0
    # ADR-6: once the LLM stage has run, singleton is for 1-item aliases only
    counts = Counter(normalise_entity(r) for (r,) in con.execute(
        "select entity_name_raw from items where entity_name_raw is not null"))
    singles = [a for (a,) in con.execute(
        "select alias_normalised from entity_aliases where method = 'singleton'")]
    assert singles and all(counts[a] == 1 for a in singles)


def test_listed_company_needs_an_asx_code(tmp_path):
    """AC-3.4: an LLM listed_company takes the code its canonical name (or a member) matches in
    the snapshot, joining any entity that already has that code; with no match it's other."""
    from test_entities import make_reference

    items = [("x1", "BHP Billiton Ltd", 4), ("x2", "BHP Billiton Ltd", 4),
             ("x3", "Accor SA", 12), ("x4", "Accor SA", 12),
             ("x5", "Commonwealth Bank of Australia", 8), ("x6", "Commonwealth Bank of Australia", 8),
             ("x7", "CBA", 8)]
    con = sqlite3.connect(make_db(tmp_path / "v2.db", []))
    con.executemany(
        "insert into items (item_id, pdf_sha256, member_id, chamber, parliament, section, "
        "category, owner, entity_name_raw, description, is_alteration, change_type, "
        "date_precision, page, confidence) values (?, 'sha', 'm', 'house', 47, ?, "
        "'x', 'self', ?, 'd', 0, 'initial', 'unknown', 1, 'high')",
        [(i, sec, raw) for i, raw, sec in items])
    con.commit()
    con.close()
    db = tmp_path / "v2.db"
    data = make_data(tmp_path, generic=(), aliases_csv=(
        "alias,canonical_name,entity_type,asx_code,review_flag,note\n"
        "cba,Commonwealth Bank,bank_or_financial,CBA,,\n"))
    names = {"bhp billiton": "BHP Group", "accor sa": "Accor",
             "commonwealth bank of australia": "CommBank"}

    def listed(blocks):
        return {"blocks": [{"block_id": bid, "groups": [{
            "members": ns, "canonical_name": names[ns[0]], "entity_type": "listed_company",
            "confidence": "high"}]} for bid, ns in blocks.items()]}

    run_entities(db, data, offline=False, llm=runner(Server(listed)),
                 reference_dir=make_reference(tmp_path))
    d = dump(db)
    ents = {eid: rest for eid, *rest in d["entities"]}
    ie = item_entities(db)
    assert ents[ie["x1"]] == ["BHP Group", "listed_company", "BHP"]  # canonical name matched
    assert ents[ie["x3"]] == ["Accor", "other", None]  # not on the ASX
    assert ie["x5"] == "commonwealth_bank"  # member matched CBA: joins the curated entity
    assert ents["commonwealth_bank"] == ["Commonwealth Bank", "bank_or_financial", "CBA"]
    # the cache keeps the LLM's own answer; the rule is applied when reading it
    assert {g["entity_type"] for r in read_llm_cache(data).values() for g in r["groups"]} == {
        "listed_company"}
