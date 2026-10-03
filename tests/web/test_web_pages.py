"""Page content against SQL on the mini fixture: AC-B2 (member pages), AC-B3 (entity pages),
AC-B4 (overview and summary.json), AC-B7 (footer, preview vs production), plus the index,
section, parliament, explore (AC-C5 no-JS content), data and about pages."""
from __future__ import annotations

from collections import Counter, defaultdict

import pytest
from html_tree import parse_file
from web_support import MINI_DB, MINI_MANIFEST, load_json, ro

from disclosures.export import COLUMNS, REPO_URL, manifest_urls
from disclosures.normalise import normalise_entity
from disclosures.web import urls as U
from disclosures.web.build import build
from disclosures.web.pages import CHANGE, METHOD_WORDS, OWNER, ordinal

CONFIDENCE_FLAGGED = ("medium", "low")


@pytest.fixture(scope="module")
def con():
    c = ro(MINI_DB)
    yield c
    c.close()


@pytest.fixture(scope="module")
def page_entities(con):
    return {r[0] for r in con.execute(
        "select entity_id from items where entity_id is not null group by 1 "
        "having count(*) >= 2")}


@pytest.fixture(scope="module")
def doc_urls():
    return manifest_urls(MINI_MANIFEST)


def reg(chamber, parliament):
    return f"{'House' if chamber == 'house' else 'Senate'} {ordinal(parliament)}"


def html_pages(site):
    return sorted(p for p in site.rglob("*.html"))


# --- AC-B2 ------------------------------------------------------------------------------------

def member_ids(con):
    return [r[0] for r in con.execute("select member_id from members order by 1")]


def test_member_pages_exist_for_every_member(mini_site, con):
    for mid in member_ids(con):
        assert (mini_site / "members" / mid / "index.html").is_file(), mid


@pytest.mark.parametrize("mid", [r[0] for r in ro(MINI_DB).execute(
    "select member_id from members order by 1")])
def test_member_page_content(mini_site, con, page_entities, doc_urls, mid):
    doc = parse_file(mini_site / "members" / mid / "index.html")
    name, chamber = con.execute("select full_name, chamber from members where member_id = ?",
                                (mid,)).fetchone()
    assert doc.find("h1").text == name
    eyebrow = doc.find("p", "eyebrow").text
    assert ("Senator" if chamber == "senate" else "House of Representatives") in eyebrow

    # terms: parliament, party, bloc, electorate/state
    terms = con.execute("select chamber, parliament, electorate_or_state, party, political_bloc "
                        "from member_terms where member_id = ? order by chamber, parliament",
                        (mid,)).fetchall()
    rows = doc.find("table", "terms").rows()
    assert len(rows) == len(terms)
    for tr, (ch, p, elec, party, bloc) in zip(rows, terms):
        cells = [c.text for c in tr.cells()]
        assert cells[0] == reg(ch, p)
        assert cells[1] == elec and cells[2] == party and cells[3] == bloc

    # statements: one row per document, page count, source link
    docs = con.execute("select pdf_sha256, page_count from documents where member_id = ?",
                       (mid,)).fetchall()
    st_rows = {tr.attrs["data-document"]: tr for tr in doc.find("table", "statements").rows()}
    assert set(st_rows) == {sha for sha, _ in docs}
    for sha, pages in docs:
        tr = st_rows[sha]
        assert tr.cells()[2].text == str(pages)
        href = tr.find("a", "source").attrs["href"]
        url = doc_urls[sha]
        want = U.SENATE_REGISTER_INDEX if U.classify(url) == U.SENATE_JSON else url
        assert href == want

    # every item, with its fields
    items = con.execute(
        "select item_id, owner, entity_id, description, change_type, lodged_date, "
        "date_precision, confidence, page, pdf_sha256, section, category from items "
        "where member_id = ?", (mid,)).fetchall()
    assert doc.by_id("item-count").text == f"{len(items):,}"
    item_rows = {}
    for table in doc.find_all("table", "items"):
        caption = table.find("caption").text
        for tr in table.rows():
            item_rows[tr.attrs["data-item"]] = (caption, tr)
    assert len(item_rows) == len(items)
    assert set(item_rows) == {r[0] for r in items}
    for (iid, owner, eid, desc, change, lodged, prec, conf, page, sha, section,
         category) in items:
        caption, tr = item_rows[iid]
        cells = tr.cells()
        assert caption.startswith(f"{category}:"), (iid, caption)
        assert cells[0].text == reg(*con.execute(
            "select chamber, parliament from items where item_id = ?", (iid,)).fetchone())
        assert cells[1].text == OWNER[owner]
        links = cells[2].find_all("a")
        if eid in page_entities:
            assert [a.attrs["href"] for a in links] == [f"/entities/{eid}/"]
        else:
            assert links == []
        assert cells[3].text.startswith(" ".join(desc.split()))
        badge = cells[3].find_all("span", "badge")
        if conf in CONFIDENCE_FLAGGED:
            assert [b.classes for b in badge] == [["badge", f"badge-{conf}"]]
            assert conf in badge[0].text
        else:
            assert badge == []
        assert cells[4].text == CHANGE[change]
        want_lodged = "not stated" if not lodged else (lodged[:7] if prec == "month" else lodged)
        assert cells[5].text == want_lodged
        a = cells[6].find("a", "source")
        href, text = U.source_link(doc_urls[sha], page)
        assert (a.attrs["href"], a.text) == (href, text)
        cls = U.classify(doc_urls[sha])
        if cls in (U.HOUSE_PDF, U.HOUSE_API):
            assert href.endswith(f"#page={page}")
        elif cls == U.HOUSE_REDIRECT:
            assert href == doc_urls[sha] and text == f"page {page} of the PDF"
        else:
            assert href == U.SENATE_REGISTER_INDEX and text == U.SENATE_LINK_TEXT

    # items.json link, alterations list
    assert doc.find("a", href=f"/members/{mid}/items.json")
    n_alt = sum(1 for r in con.execute("select 1 from items where member_id = ? and "
                                       "is_alteration = 1", (mid,)))
    alts = doc.find_all("ul", "alterations")
    assert (len(alts[0].find_all("li")) if alts else 0) == n_alt


def test_url_classes_covered_by_fixture(doc_urls):
    """The mini fixture exercises every ADR-W5 link class in the member page test above."""
    assert {U.classify(u) for u in doc_urls.values()} == set(U.URL_CLASSES)


def test_change_not_stated_label():
    assert CHANGE["unknown"] == "change not stated"


# --- AC-B3 ------------------------------------------------------------------------------------

@pytest.mark.parametrize("eid", [r[0] for r in ro(MINI_DB).execute(
    "select entity_id from items where entity_id is not null group by 1 having count(*) >= 2 "
    "order by 1")])
def test_entity_page_content(mini_site, con, eid):
    doc = parse_file(mini_site / "entities" / eid / "index.html")
    name, typ, asx = con.execute("select canonical_name, entity_type, asx_code from entities "
                                 "where entity_id = ?", (eid,)).fetchone()
    assert doc.find("h1").text == name
    assert doc.by_id("entity-type").text == (typ or "untyped").replace("_", " ")
    if asx:
        assert doc.by_id("entity-asx").text == asx
    else:
        with pytest.raises(LookupError):
            doc.by_id("entity-asx")
    methods = {r[0] for r in con.execute(
        "select method from entity_aliases where entity_id = ?", (eid,))}
    method_text = doc.by_id("entity-method").text
    for m in methods:
        assert METHOD_WORDS[m] in method_text

    raw = {r[0] for r in con.execute("select distinct entity_name_raw from items where "
                                     "entity_id = ? and entity_name_raw is not null", (eid,))}
    shown = {tr.cells()[0].text for tr in doc.find("table", "variants").rows()}
    assert shown == {" ".join(r.split()) for r in raw}
    aliases = {r[0] for r in con.execute("select alias_normalised from entity_aliases where "
                                         "entity_id = ?", (eid,))}
    alias_list = doc.find_all("ul", "aliases")
    assert {c.text for c in (alias_list[0].find_all("code") if alias_list else [])} == \
        {" ".join(a.split()) for a in aliases}

    by_reg = con.execute("select chamber, parliament, count(distinct member_id) from items "
                         "where entity_id = ? group by 1, 2 order by 1, 2", (eid,)).fetchall()
    rows = doc.find("table", "members-by-parliament").rows()
    assert [(tr.cells()[0].text, tr.cells()[-1].text) for tr in rows] == \
        [(reg(c, p), f"{n:,}") for c, p, n in by_reg]
    n_members = con.execute("select count(distinct member_id) from items where entity_id = ?",
                            (eid,)).fetchone()[0]
    assert doc.by_id("entity-members").text == f"{n_members:,}"
    assert len(doc.find("table", "entity-members").rows()) == n_members

    ids = {r[0] for r in con.execute("select item_id from items where entity_id = ?", (eid,))}
    assert doc.by_id("entity-items").text == f"{len(ids):,}"
    got = [tr.attrs["data-item"] for t in doc.find_all("table", "items") for tr in t.rows()]
    assert len(got) == len(ids) and set(got) == ids
    assert doc.find("a", href=f"/entities/{eid}/items.json")


def test_no_page_for_singleton_entities(mini_site, con):
    singles = [r[0] for r in con.execute(
        "select entity_id from items where entity_id is not null group by 1 "
        "having count(*) = 1")]
    assert singles
    for eid in singles:
        assert not (mini_site / "entities" / eid).exists()


# --- AC-B4 ------------------------------------------------------------------------------------

def sql_summary(con):
    blocs = {(m, c, p): b for m, c, p, b in con.execute(
        "select member_id, chamber, parliament, political_bloc from member_terms")}
    sb, po, items_reg, alt_reg = Counter(), Counter(), Counter(), Counter()
    for mid, ch, p, sec, owner, is_alt in con.execute(
            "select member_id, chamber, parliament, section, owner, is_alteration from items"):
        sb[(sec, blocs.get((mid, ch, p)) or "Unknown")] += 1
        po[(ch, p, owner)] += 1
        items_reg[(ch, p)] += 1
        alt_reg[(ch, p)] += is_alt
    top = con.execute(
        "select e.entity_id, e.canonical_name, count(distinct i.member_id) m, count(*) n "
        "from items i join entities e on e.entity_id = i.entity_id group by 1 "
        "order by m desc, n desc, e.entity_id limit 15").fetchall()
    return {
        "items": con.execute("select count(*) from items").fetchone()[0],
        "members": con.execute("select count(*) from members").fetchone()[0],
        "statements": con.execute("select count(*) from documents").fetchone()[0],
        "entities": con.execute("select count(*) from entities").fetchone()[0],
        "section_bloc": dict(sb), "parliament_owner": dict(po),
        "top": [(e, n_, m, n) for e, n_, m, n in top],
        "alterations": {k: (n, alt_reg[k]) for k, n in items_reg.items()},
    }


def test_summary_json_equals_sql(mini_site, con):
    s = load_json(mini_site / "data" / "summary.json")
    q = sql_summary(con)
    assert (s["items"], s["members"], s["statements"], s["entities"]) == \
        (q["items"], q["members"], q["statements"], q["entities"])
    assert {(r["section"], r["bloc"]): r["items"] for r in s["items_by_section_bloc"]} == \
        q["section_bloc"]
    assert [(e["id"], e["name"], e["members"], e["items"])
            for e in s["top_entities_by_members"]] == q["top"]
    assert {(r["chamber"], r["parliament"], r["owner"]): r["items"]
            for r in s["items_by_parliament_owner"]} == q["parliament_owner"]
    assert {(r["chamber"], r["parliament"]): (r["items"], r["alterations"])
            for r in s["alterations_by_parliament"]} == q["alterations"]
    for r in s["alterations_by_parliament"]:
        assert r["share"] == round(r["alterations"] / r["items"], 4)


def test_overview_prints_summary_numbers(mini_site, con):
    s = load_json(mini_site / "data" / "summary.json")
    q = sql_summary(con)
    doc = parse_file(mini_site / "index.html")
    head = {dd.attrs["data-key"]: dd.text for dd in doc.by_id("headline").find_all("dd")}
    assert head == {"items": f"{q['items']:,}", "members": f"{q['members']:,}",
                    "statements": f"{q['statements']:,}", "parliaments": str(s["parliaments"]),
                    "entities": f"{q['entities']:,}", "data_date": s["data_date"]}

    table = doc.find("table", "section-bloc")
    blocs = [th.text for th in table.find("thead").find_all("th")][1:-1]
    for tr in table.rows():
        cells = [c.text for c in tr.cells()]
        sec = int(cells[0].split(".")[0])
        for b, v in zip(blocs, cells[1:-1]):
            assert v == f"{q['section_bloc'].get((sec, b), 0):,}", (sec, b)
        assert cells[-1] == f"{sum(n for (x, _), n in q['section_bloc'].items() if x == sec):,}"

    top = [[c.text for c in tr.cells()] for tr in doc.find("table", "top-entities").rows()]
    assert top == [[name, f"{m:,}", f"{n:,}"] for _, name, m, n in q["top"]]

    owners = {"Self": "self", "Spouse or partner": "spouse", "Dependent child":
              "dependent_child", "Owner not stated": "unknown"}
    table = doc.find("table", "parliament-owner")
    labels = [th.text for th in table.find("thead").find_all("th")][1:-1]
    for tr in table.rows():
        cells = [c.text for c in tr.cells()]
        ch, p = cells[0].split()
        key = ("house" if ch == "House" else "senate", int(p[:-2]))
        for label, v in zip(labels, cells[1:-1]):
            assert v == f"{q['parliament_owner'].get((*key, owners[label]), 0):,}"

    alt = [[c.text for c in tr.cells()] for tr in doc.find("table", "alterations-share").rows()]
    want = [[reg(*k), f"{n:,}", f"{a:,}", f"{100 * round(a / n, 4):.1f}%"]
            for k, (n, a) in sorted(q["alterations"].items())]
    assert alt == want


# --- AC-B7 ------------------------------------------------------------------------------------

def _footer_checks(site, version, data_date):
    for p in html_pages(site):
        doc = parse_file(p)
        foot = doc.find("footer", "site-footer")
        t = foot.text
        for needle in ("CC BY 4.0", "Parliament of Australia", version, data_date,
                       "Transcribed from the Parliament of Australia registers. Check the "
                       "source before relying on any item."):
            assert needle in t, (p, needle)
        assert foot.find("a", href=REPO_URL), p


def test_footer_and_preview_labels(mini_site, con):
    loaded = con.execute("select value from meta where key = 'loaded_at'").fetchone()[0]
    _footer_checks(mini_site, f"v2.{loaded[:10]}", loaded[:10])
    for p in html_pages(mini_site):
        doc = parse_file(p)
        robots = [m.attrs["content"] for m in doc.find_all("meta", name="robots")]
        assert robots == ["noindex,nofollow"], p
        assert "Preview build, not the published dataset" in doc.find("p", "preview-banner").text


def test_production_has_no_noindex_or_banner(tmp_path, con):
    out = tmp_path / "prod"
    build(MINI_DB, MINI_MANIFEST, out, mode="production")
    loaded = con.execute("select value from meta where key = 'loaded_at'").fetchone()[0]
    _footer_checks(out, f"v2.{loaded[:10]}", loaded[:10])
    for p in html_pages(out):
        text = p.read_text()
        assert "noindex" not in text, p
        assert "preview-banner" not in text and "Preview build" not in text, p


# --- other pages --------------------------------------------------------------------------------

def test_every_page_has_head_contract(mini_site):
    for p in html_pages(mini_site):
        doc = parse_file(p)
        assert doc.find("title").text, p
        assert doc.find("meta", name="description").attrs["content"], p
        assert doc.find("meta", name="color-scheme").attrs["content"] == "light dark"
        canon = doc.find("link", rel="canonical").attrs["href"]
        assert canon.startswith("https://interests.kevinrassool.com/"), p
        for prop in ("og:title", "og:description", "og:url", "og:type"):
            assert doc.find("meta", property=prop).attrs["content"], (p, prop)
        css = [l_.attrs["href"] for l_ in doc.find_all("link", rel="stylesheet")]
        assert len(css) == 1 and css[0].startswith("/assets/style."), p
        nav = doc.find("nav", "site-nav")
        assert [a.text for a in nav.find_all("a")] == ["Overview", "Explore", "Members",
                                                       "Entities", "Data", "About"]
        assert doc.find("a", "wordmark").attrs["href"] == "https://kevinrassool.com"
        assert doc.find("a", "skip-link").attrs["href"] == "#main"
        assert doc.by_id("main").tag == "main"


def test_aria_current_matches_page(mini_site):
    want = {"index.html": "Overview", "members/index.html": "Members",
            "members/wayne_swan/index.html": "Members", "entities/index.html": "Entities",
            "explore/index.html": "Explore", "data/index.html": "Data",
            "about/index.html": "About", "sections/1/index.html": None}
    for rel, label in want.items():
        doc = parse_file(mini_site / rel)
        cur = [a.text for a in doc.find("nav", "site-nav").find_all("a")
               if a.attrs.get("aria-current") == "page"]
        assert cur == ([label] if label else []), rel


def test_index_pages(mini_site, con, page_entities):
    doc = parse_file(mini_site / "members" / "index.html")
    rows = doc.find("table", "filterable").rows()
    assert len(rows) == con.execute("select count(*) from members").fetchone()[0]
    assert doc.find("div", "filter").attrs.get("hidden") is not None
    doc = parse_file(mini_site / "entities" / "index.html")
    rows = doc.find("table", "filterable").rows()
    assert {tr.find("a").attrs["href"] for tr in rows} == \
        {f"/entities/{e}/" for e in page_entities}
    n_single = con.execute("select count(*) from (select entity_id from items where entity_id "
                           "is not null group by 1 having count(*) = 1)").fetchone()[0]
    assert f"{n_single:,} names appear in one item only" in doc.find("p", "note").text


def test_section_pages(mini_site, con):
    for n in range(1, 15):
        doc = parse_file(mini_site / "sections" / str(n) / "index.html")
        total = con.execute("select count(*) from items where section = ?", (n,)).fetchone()[0]
        assert doc.by_id("section-items").text == f"{total:,}"
        assert doc.by_id("house-wording").text
        assert doc.by_id("senate-wording").text
        assert doc.find("a", href=f"/explore/?section={n}")
        rows = doc.find("table", "section-parliament-bloc").rows()
        by_reg = dict(((c, p), k) for c, p, k in con.execute(
            "select chamber, parliament, count(*) from items where section = ? group by 1, 2",
            (n,)))
        for tr in rows:
            label = tr.cells()[0].text
            ch, p = label.split()
            key = ("house" if ch == "House" else "senate", int(p[:-2]))
            assert tr.cells()[-1].text == f"{by_reg.get(key, 0):,}"
    s11 = parse_file(mini_site / "sections" / "11" / "index.html").by_id("senate-wording").text
    s13 = parse_file(mini_site / "sections" / "13" / "index.html").by_id("senate-wording").text
    assert "gifts" in s11 and "officeHolderDonating" in s13


def test_senate_category_keys_match_adapter():
    from disclosures.senate import SECTIONS
    from disclosures.web.pages import SENATE_CATEGORY

    assert {n: key for n, (key, _) in SENATE_CATEGORY.items()} == \
        {n: key for key, (n, _) in SECTIONS.items()}


def test_parliament_pages(mini_site, con):
    regs = con.execute("select chamber, parliament, count(distinct member_id), "
                       "count(distinct pdf_sha256), count(*) from items group by 1, 2").fetchall()
    for ch, p, m, d, n in regs:
        doc = parse_file(mini_site / "parliaments" / f"{ch}-{p}" / "index.html")
        assert doc.by_id("register-members").text == f"{m:,}"
        assert doc.by_id("register-statements").text == f"{d:,}"
        assert doc.by_id("register-items").text == f"{n:,}"
        assert len(doc.find("table", "register-members").rows()) == m
    dirs = sorted(x.name for x in (mini_site / "parliaments").iterdir())
    assert dirs == sorted(f"{c}-{p}" for c, p, *_ in regs)


def test_explore_page_without_js_content(mini_site):
    """AC-C5: the overview counts table and a pointer to the indexes, plus the mount point."""
    doc = parse_file(mini_site / "explore" / "index.html")
    assert doc.find("table", "coverage").rows()
    intro = doc.by_id("explore-intro")
    assert {a.attrs["href"] for a in intro.find_all("a")} == {"/members/", "/entities/"}
    mount = doc.by_id("explorer")
    assert mount.tag == "div" and "hidden" in mount.attrs and mount.children == []


def test_data_page(mini_site):
    doc = parse_file(mini_site / "data" / "index.html")
    names = [tr.cells()[0].text for tr in doc.find("table", "dictionary").rows()]
    assert names == [c[0] for c in COLUMNS]
    dl = doc.find("table", "downloads")
    hrefs = [a.attrs["href"] for a in dl.find_all("a")]
    assert "https://data.kevinrassool.com/interests/latest/disclosures_v2.db" in hrefs
    assert all(h.startswith("https://data.kevinrassool.com/interests/latest/") for h in hrefs)
    assert "published with the dataset" in dl.text
    assert doc.find("a", href="https://lite.datasette.io/?url=https://data.kevinrassool.com/"
                              "interests/latest/disclosures_v2.db")
    assert doc.find("a", href="/changes.xml")
    assert doc.by_id("bundle-version").text == "1"
    assert "CC BY-NC-ND 4.0" in doc.text and "Rassool, K." in doc.find("pre", "cite").text


def test_data_page_with_local_data_files(tmp_path):
    files = tmp_path / "r2"
    files.mkdir()
    for name in ("disclosures_v2.db", "disclosures_v2.csv", "disclosures_v2.csv.gz",
                 "disclosures_v2.jsonl.gz", "README.md", "datapackage.json", "MANIFEST.json"):
        (files / name).write_bytes(name.encode() * 10)
    out = tmp_path / "s"
    build(MINI_DB, MINI_MANIFEST, out, data_files=files)
    import hashlib

    doc = parse_file(out / "data" / "index.html")
    rows = {tr.cells()[0].text: tr for tr in doc.find("table", "downloads").rows()}
    assert set(rows) == {"disclosures_v2.db", "disclosures_v2.csv", "disclosures_v2.csv.gz",
                         "disclosures_v2.jsonl.gz", "README.md", "datapackage.json",
                         "MANIFEST.json"}
    sha = hashlib.sha256(b"disclosures_v2.db" * 10).hexdigest()
    assert rows["disclosures_v2.db"].find("code").text == sha
    assert "published with the dataset" not in doc.find("table", "downloads").text


def test_about_page_reuses_readme_prose(mini_site):
    from disclosures.export import README_LIMITATIONS

    doc = parse_file(mini_site / "about" / "index.html")
    text = doc.text
    for phrase in ("Senate before the 48th parliament is missing.", "Two prompt versions.",
                   "One-off entities are untyped.", "Transcription is not perfect.",
                   "precision 0.986, recall 0.987 (F1 0.987)", "odowdk45p"):
        assert phrase in text, phrase
    n_bullets = sum(1 for line in README_LIMITATIONS.splitlines() if line.startswith("- "))
    assert len(doc.by_id("limitations-list").find_all("li")) == n_bullets
    assert len(doc.by_id("method").parent.find("ol", "prose").find_all("li")) == 4


def test_no_em_dashes_in_site_or_sources(mini_site):
    from pathlib import Path

    import disclosures.web as W

    pkg = Path(W.__file__).parent
    sources = [*pkg.glob("*.py"), *pkg.glob("templates/*.html"), pkg / "static" / "style.css"]
    for p in sources:
        assert "\u2014" not in p.read_text(), p
    for p in html_pages(mini_site):
        assert "\u2014" not in p.read_text(), p


def test_no_inference_words(mini_site):
    """ADR-W9: the site's own copy describes what was declared; no wrongdoing words. Item
    descriptions (the members' own words) are left out of the check."""
    import re

    bad = re.compile(r"\b(wealthy|rich|corrupt|corruption|scandal|conflicted|suspicious|"
                     r"dodgy|wrongdoing)\b", re.I)
    for rel in ("index.html", "about/index.html", "data/index.html", "explore/index.html",
                "members/wayne_swan/index.html", "entities/index.html", "sections/1/index.html",
                "parliaments/house-43/index.html"):
        main = parse_file(mini_site / rel).by_id("main")
        for t in main.find_all("table", "items") + main.find_all("ul", "alterations"):
            t.children.clear()
        assert bad.findall(main.text) == [], rel
