"""AC-B1: the real build's file inventory (skips when site/disclosures_v2.db is absent)."""
from __future__ import annotations

from web_support import REAL_DB, load_json, needs_real, ro

from disclosures.web.check import check_site

MiB = 1024 * 1024


@needs_real
def test_real_inventory(real_site):
    con = ro(REAL_DB)
    members = [r[0] for r in con.execute("select member_id from members order by 1")]
    entities = [r[0] for r in con.execute(
        "select entity_id from items where entity_id is not null group by 1 "
        "having count(*) >= 2 order by 1")]
    regs = con.execute("select distinct chamber, parliament from items order by 1, 2").fetchall()
    con.close()
    assert len(members) == 408
    for rel in ("index.html", "members/index.html", "entities/index.html", "about/index.html",
                "data/index.html", "explore/index.html", "404.html", "robots.txt",
                "sitemap.xml", "changes.xml", "_headers", "web-manifest.json",
                "data/items.json", "data/members.json", "data/entities.json",
                "data/documents.json", "data/search.json", "data/summary.json",
                "data/schema.json"):
        assert (real_site / rel).is_file(), rel
    member_pages = sorted(p.parent.name for p in real_site.glob("members/*/index.html"))
    assert member_pages == members
    entity_pages = sorted(p.parent.name for p in real_site.glob("entities/*/index.html"))
    assert entity_pages == entities and len(entities) == 4448
    sections = sorted(int(p.parent.name) for p in real_site.glob("sections/*/index.html"))
    assert sections == list(range(1, 15))
    parls = sorted(p.parent.name for p in real_site.glob("parliaments/*/index.html"))
    assert parls == sorted(f"{c}-{p}" for c, p in regs) and len(parls) == 7

    files = [p for p in real_site.rglob("*") if p.is_file()]
    assert len(files) <= 12_000
    total = sum(p.stat().st_size for p in files)
    assert total <= 300 * MiB
    html = [p for p in files if p.suffix == ".html"]
    assert max(p.stat().st_size for p in html) <= 2 * MiB
    m = load_json(real_site / "web-manifest.json")
    assert m["counts"]["pages"] == len(html)


@needs_real
def test_real_site_passes_check(real_site):
    fails, notes = check_site(real_site, REAL_DB)
    assert fails == []


def test_inventory_rules_are_in_check():
    from disclosures.web import check as C

    assert {"member-page-missing", "entity-page-missing", "sitemap-missing-page",
            "canonical-missing"} <= set(C.RULES)
