"""Render every HTML page of the public site (ADR-W4) from ``dataset.py`` data.

Every number a page prints comes from the same ``Dataset`` the bundle uses; the overview reads
the ``data/summary.json`` the bundle just wrote, so the page and the JSON cannot disagree
(AC-B4). Pages render only DB columns, manifest URLs and the fixed copy in this module and in
``export`` (AC-B11). Copy rules (ADR-W9): describe what was declared; never infer value, wealth
or wrongdoing; plain English, no em dashes.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup

from .. import export
from . import WEB_BUNDLE_VERSION
from . import charts as C
from . import metadata as MD
from . import urls as U
from .bundle import DATA_FILES, write
from .dataset import Dataset, sections
from .media import Media

TEMPLATES = Path(__file__).parent / "templates"
SITE_NAME = "Registers of Interests"
NAV = [("overview", "/", "Overview"), ("explore", "/explore/", "Explore"),
       ("members", "/members/", "Members"), ("entities", "/entities/", "Entities"),
       ("data", "/data/", "Data"), ("about", "/about/", "About")]

CHAMBER = {"house": "House", "senate": "Senate"}
CHAMBER_LONG = {"house": "House of Representatives", "senate": "Senate"}
OWNER = {"self": "Self", "spouse": "Spouse or partner", "dependent_child": "Dependent child",
         "unknown": "Not stated"}
CHANGE = {"initial": "Initial statement", "added": "Added", "removed": "Removed",
          "varied": "Varied", "unknown": "change not stated"}
FLAGGED_CONFIDENCE = ("medium", "low")
METHOD_WORDS = {
    "curated": "curated alias table",
    "asx": "matched by the ASX listed-companies list",
    "llm": "LLM grouping of spelling variants",
    "singleton": "one-off name, its own entity",
    "generic": "generic term, no entity",
}
METHOD_SHORT = {"curated": "curated table", "asx": "ASX list", "llm": "LLM grouping",
                "singleton": "one-off name", "generic": "generic term"}
METHOD_ORDER = ("curated", "asx", "llm", "singleton", "generic")
PARLIAMENT_YEARS = {43: "2010 to 2013", 44: "2013 to 2016", 45: "2016 to 2019",
                    46: "2019 to 2022", 47: "2022 to 2025", 48: "2025 to now"}
SCANNED_PARLIAMENTS = (43, 44, 45)  # "more on poor scans (43rd-45th parliaments)", README

# Official section wording: the House form (v2 SPEC section 0, disclosures/prompts/extract.md).
HOUSE_WORDING = {
    1: "Shareholdings in public and private companies",
    2: "Family and business trusts and nominee companies: 2(i) a beneficial interest, "
       "2(ii) trustee",
    3: "Real estate, with its location and the purpose for which it is owned",
    4: "Registered directorships of companies",
    5: "Partnerships",
    6: "Liabilities: the nature of the liability and the creditor",
    7: "Bonds, debentures and like investments",
    8: "Saving or investment accounts, with the bank or institution",
    9: "The nature of any other assets (excluding household and personal effects) over $7,500",
    10: "The nature of any other substantial sources of income",
    11: "Gifts",
    12: "Any sponsored travel or hospitality received over $300",
    13: "Membership of any organisation where a conflict of interest could arise",
    14: "Any other interests where a conflict of interest could arise",
}
# The Senate register's category for each section: the senators' interests API key
# (disclosures/senate.py SECTIONS) and a plain reading of it. 11 and 13 are worded differently
# from the House form; the rest match.
SENATE_CATEGORY = {
    1: ("shareHoldings", None), 2: ("trusts", None), 3: ("realEstate", None),
    4: ("registeredDirectorshipsOfCompanies", None), 5: ("partnerships", None),
    6: ("liabilities", None), 7: ("investments", None),
    8: ("savingsOrInvestmentAccounts", None), 9: ("otherAssets", None),
    10: ("otherIncome", None),
    11: ("gifts", "Gifts, as the Senate register words them"),
    12: ("sponsoredTravelOrHospitality", None),
    13: ("officeHolderDonating", "Office holder of, or donor to, an organisation"),
    14: ("otherInterest", None),
}


# --- shared prose, derived from export's README text ------------------------------------------

def _gold() -> Dict[str, str]:
    m = export.README_METHOD
    get = lambda pat: re.search(pat, m).group(1)  # noqa: E731
    return {"precision": get(r"precision (\d\.\d+)"), "recall": get(r"recall (\d\.\d+)"),
            "f1": get(r"\(F1 (\d\.\d+)\)"), "items": get(r"\((\d+) items\)"),
            "pdfs": get(r"On a (\d+)-PDF"), "owner": get(r"(\d+%) owner and page"),
            "page": get(r"(\d+%) owner and page")}


GOLD = _gold()


def md_inline(text: str) -> Markup:
    """The README's inline Markdown (``**bold**``, backticks, ``[text](url)``) as safe HTML."""
    s = escape(" ".join(text.split()), quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    return Markup(s)


def md_list(block: str) -> List[Markup]:
    """Split a Markdown list (``1. `` or ``- `` items with indented continuation lines)."""
    items: List[str] = []
    for line in block.splitlines():
        if re.match(r"^(\d+\.|-) ", line):
            items.append(re.sub(r"^(\d+\.|-) ", "", line))
        elif items:
            items[-1] += " " + line.strip()
    return [md_inline(i) for i in items]


def v1_reruns() -> Dict[int, List[str]]:
    """Statements re-run on prompt v1, by parliament, read from the README's limitations."""
    out: Dict[int, List[str]] = defaultdict(list)
    for code in re.findall(r"`([a-z]+_?(\d\d)p)`", export.README_LIMITATIONS):
        out[int(code[1])].append(code[0])
    return dict(out)


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def register_label(chamber: str, parliament: int) -> str:
    return f"{CHAMBER[chamber]} {ordinal(parliament)}"


def register_slug(chamber: str, parliament: int) -> str:
    return f"{chamber}-{parliament}"


def register_title(chamber: str, parliament: int) -> str:
    return f"{ordinal(parliament)} Parliament, {CHAMBER_LONG[chamber]}"


def fmt(n: int) -> str:
    return f"{n:,}"


def _lodged(date: Optional[str], precision: Optional[str]) -> Tuple[str, Optional[str]]:
    if not date:
        return "not stated", None
    if precision == "month":
        return date[:7], date[:7]
    return date, date


def _human_size(n: int) -> str:
    for unit, div in (("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if n >= div:
            return f"{n / div:.1f} {unit}"
    return f"{n} bytes"


def _span(nums: List[int]) -> str:
    """[43, 44, 45, 47] -> '43-45, 47'."""
    nums = sorted(set(nums))
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return ", ".join(out)


# --- context -----------------------------------------------------------------------------------

@dataclass
class SiteConfig:
    mode: str
    site_url: str
    data_base: str
    doi: Optional[str]
    css_href: str
    js: Dict[str, str] = field(default_factory=dict)
    data_files: Optional[Path] = None
    media: Media = field(default_factory=Media)
    og_base: str = ""


def og_file(path: str) -> str:
    """Page path -> its card's file under the og base: '/' -> 'index.png',
    '/members/x/' -> 'members/x.png', '/404.html' -> '404.png'."""
    stem = path.strip("/")
    if stem.endswith(".html"):
        stem = stem[:-5]
    return (stem or "index") + ".png"


class Renderer:
    def __init__(self, ds: Dataset, cfg: SiteConfig, summary: dict):
        self.ds, self.cfg, self.s = ds, cfg, summary
        self.env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True,
                               trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined,
                               keep_trailing_newline=True)
        self.env.filters["num"] = fmt
        self.meta = ds.meta()
        self.members = ds.members()
        self.member_by_id = {m["id"]: m for m in self.members}
        self.entities = ds.entities()
        self.entity_by_id = {e["id"]: e for e in self.entities}
        self.page_ids = {e["id"] for e in self.entities if e["page"]}
        self.documents = ds.documents()
        self.doc_by_sha = {d["sha256"]: d for d in self.documents}
        self.items = ds.items()
        self.blocs = ds.item_blocs()
        self.aliases = ds.aliases()
        self.section_names = {s["section"]: s["name"] for s in sections()}
        self.terms = {(m["id"], t["chamber"], t["parliament"]): t
                      for m in self.members for t in m["terms"]}
        self.registers = sorted({(it["chamber"], it["parliament"]) for it in self.items})
        self.version = MD.dataset_version(self.meta)
        self.data_date = (self.meta.get("loaded_at") or "")[:10] or "unknown"
        self.pages: List[str] = []
        self.cards: List[dict] = []
        year = self.data_date[:4]
        cite = (f"Rassool, K. ({year}). Australian Parliament Registers of Interests "
                f"({self.version}) [Data set]. Transcribed from the Parliament of Australia "
                f"Register of Members' Interests and Register of Senators' Interests. "
                f"{cfg.site_url}/")
        if cfg.doi:
            cite += f" {MD.doi_url(cfg.doi)}"
        self.site = {
            "name": SITE_NAME,
            "preview": cfg.mode == "preview",
            "site_url": cfg.site_url,
            "css_href": cfg.css_href,
            "js": cfg.js,
            "nav": NAV,
            "version": self.version,
            "data_date": self.data_date,
            "doi": cfg.doi,
            "doi_url": MD.doi_url(cfg.doi),
            "repo_url": export.REPO_URL,
            "og_base": cfg.og_base,
            "gold": GOLD,
            "cite": cite,
            "labels_note": ("Confidence is marked when the transcriber was not sure (medium "
                            "or low); unmarked items are high confidence. \"Change not "
                            "stated\" means the statement does not say whether the item was "
                            "added, removed or varied. Each source link opens the statement "
                            "at the item's page where the source allows it."),
        }
        self._rows = [self._row(it) for it in self.items]

    # --- helpers ---------------------------------------------------------------------------

    def bloc(self, it: dict) -> str:
        return self.blocs.get((it["member_id"], it["chamber"], it["parliament"])) or \
            C.UNKNOWN_BLOC_SERIES[0]

    def _row(self, it: dict) -> dict:
        doc = self.doc_by_sha[it["pdf_sha256"]]
        href, text = U.source_link(doc["url"], it["page"])
        eid = it["entity_id"]
        if eid and eid in self.page_ids:
            ename, ehref = self.entity_by_id[eid]["name"], f"/entities/{eid}/"
        else:
            ename, ehref = it["entity_name_raw"], None
        lodged, dt_attr = _lodged(it["lodged_date"], it["date_precision"])
        conf = it["confidence"] if it["confidence"] in FLAGGED_CONFIDENCE else None
        member = self.member_by_id.get(it["member_id"], {"name": it["member_id"]})
        return {
            "item_id": it["item_id"], "member_id": it["member_id"], "member_name": member["name"],
            "chamber": it["chamber"], "parliament": it["parliament"],
            "register": register_label(it["chamber"], it["parliament"]),
            "section": it["section"], "section_name": self.section_names[it["section"]],
            "owner": OWNER.get(it["owner"], it["owner"]), "owner_key": it["owner"],
            "entity_id": eid, "entity_name": ename, "entity_href": ehref,
            "description": it["description"] or "", "change": CHANGE.get(it["change_type"],
                                                                         it["change_type"]),
            "is_alteration": it["is_alteration"], "lodged": lodged, "datetime": dt_attr,
            "lodged_raw": it["lodged_date"], "confidence": conf, "source_href": href,
            "source_text": text,
        }

    def page(self, path: str, nav: Optional[str], title: str, description: str,
             scripts: Tuple[str, ...] = (), jsonld: Optional[str] = None,
             card: Optional[dict] = None) -> dict:
        """The page dict for base.html. Also records the page's Open Graph card spec
        (``og-cards.json``): ``card`` overrides the default of the site's headline numbers."""
        spec = {"eyebrow": SITE_NAME, "title": title, "subtitle": description,
                "stats": self._site_stats(), "accent": None, "bar": None}
        spec.update(card or {})
        spec.update({"path": path, "file": og_file(path)})
        self.cards.append(spec)
        return {"path": path, "nav": nav, "title": f"{title} | {SITE_NAME}",
                "og_title": title, "description": description, "scripts": list(scripts),
                "jsonld": Markup(jsonld) if jsonld else None,
                "og_image": self.cfg.og_base + spec["file"] if self.cfg.og_base else None,
                "og_image_alt": f"{title}: {', '.join(f'{v} {k}' for v, k in spec['stats'])}."}

    def _site_stats(self) -> List[List[str]]:
        return [[fmt(self.s["items"]), "declared items"], [fmt(self.s["members"]), "members"],
                [fmt(self.s["statements"]), "statements"]]

    def render(self, out: Path, template: str, page: dict, **ctx) -> None:
        html = self.env.get_template(template).render(site=self.site, page=page, **ctx)
        path = page["path"]
        rel = path.lstrip("/") + "index.html" if path.endswith("/") else path.lstrip("/")
        write(out, rel, html.encode("utf-8"))
        if template != "404.html":
            self.pages.append(path)

    @staticmethod
    def _groups(rows: List[dict]) -> List[dict]:
        by = defaultdict(list)
        for r in rows:
            by[r["section"]].append(r)
        return [{"section": s, "name": by[s][0]["section_name"], "rows": by[s]}
                for s in sorted(by)]

    def _model_text(self, chamber: str, parliament: int) -> str:
        models = Counter(d["model"] for d in self.documents
                         if d["chamber"] == chamber and d["parliament"] == parliament)
        return "; ".join(f"{m} ({fmt(n)} {'statement' if n == 1 else 'statements'})"
                         for m, n in sorted(models.items()))

    def _models_for(self, shas) -> str:
        """Phrase naming the language model(s) that transcribed these House documents."""
        primary, fallback = set(), set()
        for sha in shas:
            d = self.doc_by_sha[sha]
            if d["chamber"] != "house" or not d["model"]:
                continue
            first, *rest = d["model"].split("+")  # "a+b": model b took pages model a refused
            primary.add(first)
            fallback.update(rest)
        if not primary:
            return "a language model"
        names = sorted(primary)
        text = ("the language model " if len(names) == 1 else "the language models ") + \
            (names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1])
        if fallback - primary:
            text += f", with {' and '.join(sorted(fallback - primary))} for pages it refused"
        return text

    def _entity_honest(self, items: List[dict]) -> str:
        """ADR-W9 sentence for an entity page: method, measured accuracy, what the page shows."""
        shas = {it["pdf_sha256"] for it in items}
        chambers = {self.doc_by_sha[sha]["chamber"] for sha in shas}
        parts = []
        if "house" in chambers:
            parts.append(f"House items were transcribed from the statement PDFs by "
                         f"{self._models_for(shas)} (precision {GOLD['precision']}, recall "
                         f"{GOLD['recall']} on a hand-checked gold set), so a few may be "
                         f"missing or misread.")
        if "senate" in chambers:
            parts.append("Senate items come from the Senate register's structured data, not "
                         "a transcription.")
        parts.append("This page groups items by the entity they name and shows what was "
                     "declared, not its value. A spelling grouped by mistake is possible: the "
                     "printed names above show what each statement said. Check the source "
                     "before relying on an item.")
        return " ".join(parts)

    # --- distribution (downloads, JSON-LD) ----------------------------------------------------

    def distribution(self) -> List[dict]:
        local = self.cfg.data_files
        out = []
        for name, enc, label, is_data, optional in MD.R2_FILES:
            p = (local / name) if local else None
            present = bool(p and p.is_file())
            if optional and not present:
                continue
            row = {"name": name, "format": enc, "label": label, "is_data": is_data,
                   "url": MD.data_url(self.cfg.data_base, name), "size": None, "sha256": None,
                   "licence": "CC BY 4.0" if is_data else ""}
            if present:
                from .dataset import sha256_file

                row["bytes"] = p.stat().st_size
                row["size"] = _human_size(row["bytes"])
                row["sha256"] = sha256_file(p)
            out.append(row)
        return out

    def jsonld(self) -> str:
        dist = [d for d in self.distribution() if d["is_data"]]
        doc = MD.dataset_jsonld(self.s, self.meta, site_url=self.cfg.site_url,
                                data_base=self.cfg.data_base, distribution=dist, doi=self.cfg.doi)
        return MD.jsonld_script(doc)

    # --- pages -------------------------------------------------------------------------------

    def coverage_rows(self) -> List[list]:
        return [[Markup(f'<a href="/parliaments/{register_slug(c["chamber"], c["parliament"])}/">'
                        f'{escape(register_label(c["chamber"], c["parliament"]))}</a>'),
                 fmt(c["members"]), fmt(c["statements"]), fmt(c["items"])]
                for c in self.s["coverage"]]

    def render_overview(self, out: Path) -> None:
        s = self.s
        blocs_present = sorted({r["bloc"] for r in s["items_by_section_bloc"]})
        series = C.bloc_series(blocs_present)
        sb = defaultdict(dict)
        for r in s["items_by_section_bloc"]:
            sb[r["section"]][r["bloc"]] = r["items"]
        sec_rows = [(f"{x['section']}. {x['name']}", [sb[x["section"]].get(k, 0)
                                                     for k, _, _ in series])
                    for x in s["sections"]]
        po = defaultdict(dict)
        for r in s["items_by_parliament_owner"]:
            po[(r["chamber"], r["parliament"])][r["owner"]] = r["items"]
        regs = sorted(po)
        owner_rows = [(register_label(*k), [po[k].get(o, 0) for o, _, _ in C.OWNER_SERIES])
                      for k in regs]
        alt = s["alterations_by_parliament"]
        charts = {
            "sections": Markup(C.stacked(
                "chart-sections", "Items per section, split by bloc",
                "Horizontal stacked bars, one per register section, split into Labor, "
                "Coalition and Crossbench.", sec_rows, series)),
            "top_entities": Markup(C.single(
                "chart-top-entities", "Top 15 entities by distinct members",
                "Horizontal bars: number of distinct members naming each entity.",
                [(e["name"], e["members"]) for e in s["top_entities_by_members"]])),
            "owner": Markup(C.stacked(
                "chart-owner", "Items per register by owner",
                "Horizontal stacked bars, one per register, split by whose interest the item "
                "is.", owner_rows, C.OWNER_SERIES)),
            "alterations": Markup(C.single(
                "chart-alterations", "Share of items that are alterations, per register",
                "Horizontal bars: percentage of items from a notification of alteration.",
                [(register_label(a["chamber"], a["parliament"]), a["share"] * 100)
                 for a in alt], C.fmt_pct, axis_max=max([a["share"] * 100 for a in alt] + [1]))),
        }
        section_head = [("Section", False)] + [(label, True) for _, label, _ in series] + \
            [("Total", True)]
        section_rows = [[Markup(f'<a href="/sections/{x["section"]}/">{x["section"]}. '
                                f'{escape(x["name"])}</a>')]
                        + [fmt(v) for v in vals] + [fmt(sum(vals))]
                        for x, (_, vals) in zip(s["sections"], sec_rows)]
        top_rows = [[self._entity_link(e["id"], e["name"]), fmt(e["members"]), fmt(e["items"])]
                    for e in s["top_entities_by_members"]]
        owner_head = [("Register", False)] + [(label, True) for _, label, _ in C.OWNER_SERIES] + \
            [("Total", True)]
        owner_table = [[label] + [fmt(v) for v in vals] + [fmt(sum(vals))]
                       for label, vals in owner_rows]
        alt_rows = [[register_label(a["chamber"], a["parliament"]), fmt(a["items"]),
                     fmt(a["alterations"]), C.fmt_pct(a["share"] * 100)] for a in alt]
        desc = (f"{fmt(s['items'])} interests declared by {fmt(s['members'])} Australian "
                f"federal MPs and senators, item by item, with a link to the source page.")
        self.render(out, "overview.html",
                    self.page("/", "overview", "Australian Parliament Registers of Interests",
                              desc, jsonld=self.jsonld()),
                    s=s, charts=charts, coverage_rows=self.coverage_rows(),
                    section_head=section_head, section_rows=section_rows, top_rows=top_rows,
                    owner_head=owner_head, owner_rows=owner_table, alt_rows=alt_rows)

    def _entity_link(self, eid: str, name: str) -> Markup:
        if eid in self.page_ids:
            return Markup(f'<a href="/entities/{eid}/">{escape(name)}</a>')
        return Markup(escape(name))

    def render_members_index(self, out: Path) -> None:
        rows = []
        for m in sorted(self.members, key=lambda m: (m["name"].casefold(), m["id"])):
            terms = m["terms"]
            chambers = {t["chamber"] for t in terms} or {m["chamber"]}
            if len(chambers) == 1:
                parl = _span([t["parliament"] for t in terms])
            else:
                parl = "; ".join(f"{CHAMBER[c]} {_span([t['parliament'] for t in terms if t['chamber'] == c])}"
                                 for c in sorted(chambers))
            places: List[str] = []
            for t in reversed(terms):
                p = t["electorate_or_state"] or ""
                if p and p.casefold() not in {x.casefold() for x in places}:
                    places.append(p)
            parties: List[Tuple[str, List[int]]] = []
            for t in terms:
                party = t["party"] or "not recorded"
                if parties and parties[-1][0] == party:
                    parties[-1][1].append(t["parliament"])
                else:
                    parties.append((party, [t["parliament"]]))
            rows.append({"id": m["id"], "name": m["name"],
                         "chamber": ", ".join(CHAMBER[c] for c in sorted(chambers)),
                         "parliaments": parl, "places": ", ".join(reversed(places)),
                         "parties": "; ".join(f"{p} ({_span(ps)})" for p, ps in parties),
                         "items": m["items"], "photo": self.cfg.media.photo(m["id"])})
        self.render(out, "members_index.html",
                    self.page("/members/", "members", "Members and senators",
                              f"All {fmt(len(rows))} members and senators in the dataset, with "
                              f"their terms, party and number of declared items.",
                              scripts=("index-search",)),
                    rows=rows)

    def render_member(self, out: Path, m: dict, rows: List[dict]) -> None:
        n_by_reg = Counter((r["chamber"], r["parliament"]) for r in rows)
        terms = [{"slug": register_slug(t["chamber"], t["parliament"]),
                  "register": register_label(t["chamber"], t["parliament"]),
                  "place": t["electorate_or_state"] or "not recorded",
                  "party": t["party"] or "not recorded", "bloc": t["bloc"] or "not recorded",
                  "items": n_by_reg.get((t["chamber"], t["parliament"]), 0)}
                 for t in m["terms"]]
        n_by_doc = Counter(it["pdf_sha256"] for it in self._member_items[m["id"]])
        statements = []
        for sha in m["documents"]:
            d = self.doc_by_sha[sha]
            if d["url_class"] == U.SENATE_JSON:
                href, text = U.SENATE_REGISTER_INDEX, "Senate register (structured source)"
            elif d["url_class"] == U.HOUSE_REDIRECT:
                href, text = d["url"], "statement PDF (via APH)"
            else:
                href, text = d["url"], "statement PDF"
            statements.append({"sha256": sha, "register": register_label(d["chamber"],
                                                                         d["parliament"]),
                               "date": d["statement_date"] or "not stated", "pages": d["pages"],
                               "items": n_by_doc.get(sha, 0), "href": href, "text": text})
        groups = self._groups(rows)
        chart = None
        if groups:
            chart = Markup(C.single(
                f"chart-member-sections", f"Items per section: {m['name']}",
                "Horizontal bars: number of declared items in each register section.",
                [(f"{g['section']}. {g['name']}", len(g["rows"])) for g in groups]))
        alterations = sorted((r for r in rows if r["is_alteration"]),
                             key=lambda r: (r["lodged_raw"] or "9999", r["chamber"],
                                            r["parliament"], r["section"], r["item_id"]))
        alts = [{"datetime": r["datetime"], "lodged": r["lodged"], "change": r["change"],
                 "section_name": r["section_name"], "register": r["register"],
                 "owner_note": None if r["owner_key"] == "self" else r["owner"],
                 "description": r["description"]} for r in alterations]
        chambers = {t["chamber"] for t in m["terms"]} or {m["chamber"]}
        lede_terms = ", ".join(t["register"] for t in terms)
        if "senate" in chambers and "house" not in chambers:
            label = "Senator"
            honest = (f"These items come from the Senate register's structured data (no "
                      f"transcription). The Senate is covered for the 48th parliament only, and "
                      f"only the senator's own interests are public. Check the Senate register "
                      f"before relying on an item. Party is the party at the start of the term.")
        else:
            label = "Member of the House of Representatives" if chambers == {"house"} else \
                "Member and senator"
            senate_note = (" Senate items come from the Senate register's structured data, "
                           "not a transcription." if "senate" in chambers else "")
            honest = (f"These items were transcribed from {m['name']}'s statements by "
                      f"{self._models_for(m['documents'])} (precision {GOLD['precision']}, "
                      f"recall {GOLD['recall']} on a hand-checked gold set), so a few may be "
                      f"missing or misread. Each item links to the page of its statement: check "
                      f"the source before relying on an item.{senate_note} Party is the party "
                      f"at the start of each term.")
        latest = m["terms"][-1] if m["terms"] else None
        mem = {"id": m["id"], "name": m["name"], "chamber_label": label, "honest": honest,
               "photo": self.cfg.media.photo(m["id"]),
               "lede": f"{label}. {fmt(len(rows))} declared "
                       f"{'item' if len(rows) == 1 else 'items'} across "
                       f"{fmt(len(statements))} {'statement' if len(statements) == 1 else 'statements'}"
                       f" ({lede_terms})."}
        self.render(out, "member.html",
                    self.page(f"/members/{m['id']}/", "members", m["name"],
                              f"Interests declared by {m['name']} in the Parliament of "
                              f"Australia registers: {fmt(len(rows))} items, with links to the "
                              f"source statements.",
                              card=self._member_card(m, label, latest, len(rows), len(statements),
                                                     terms)),
                    mem=mem, terms=terms, statements=statements, n_items=len(rows),
                    groups=groups, chart=chart, alterations=alts)

    def _member_card(self, m: dict, label: str, latest: Optional[dict], n_items: int,
                     n_statements: int, terms: List[dict]) -> dict:
        sub = label
        if latest:
            place = latest["electorate_or_state"] or ""
            if place.isupper():
                place = place.title()
            party = latest["party"] or ""
            sub = ", ".join(x for x in (party, place) if x) + \
                f" ({ordinal(latest['parliament'])} parliament)"
        return {"eyebrow": label, "title": m["name"], "subtitle": sub,
                "accent": (latest or {}).get("bloc"),
                "stats": [[fmt(n_items), "declared items" if n_items != 1 else "declared item"],
                          [fmt(n_statements), "statements" if n_statements != 1 else
                           "statement"],
                          [fmt(len(terms)), "parliaments" if len(terms) != 1 else
                           "parliament"]]}

    def _bloc_bar(self, items: List[dict]) -> List[dict]:
        """Distinct members per bloc (at the start of each term) among ``items``."""
        by_bloc: Dict[str, set] = defaultdict(set)
        for it in items:
            by_bloc[self.bloc(it)].add(it["member_id"])
        return [{"bloc": key, "label": lab, "value": len(by_bloc[key])}
                for key, lab, _ in C.bloc_series(sorted(by_bloc)) if by_bloc.get(key)]

    def _bloc_card(self, eyebrow: str, title: str, subtitle: str, items: List[dict],
                   stats: List[List[str]]) -> dict:
        return {"eyebrow": eyebrow, "title": title, "subtitle": subtitle, "stats": stats,
                "bar": self._bloc_bar(items)}

    def _entity_card(self, ent: dict, items: List[dict], n_regs: int) -> dict:
        bar = self._bloc_bar(items)
        return {"eyebrow": ent["type_label"].capitalize(), "title": ent["name"],
                "subtitle": "Named in interests declared by Australian federal MPs and "
                            "senators.",
                "stats": [[fmt(ent["members"]), "members" if ent["members"] != 1 else "member"],
                          [fmt(ent["items"]), "declared items" if ent["items"] != 1 else
                           "declared item"],
                          [fmt(n_regs), "registers" if n_regs != 1 else "register"]],
                "bar": bar}

    def render_entities_index(self, out: Path) -> None:
        rows = [{"id": e["id"], "name": e["name"],
                 "type": (e["type"] or "untyped").replace("_", " "), "asx": e["asx"] or "",
                 "members": e["members"], "items": e["items"],
                 "method": ", ".join(METHOD_SHORT.get(x, x) for x in METHOD_ORDER
                                     if x in e["methods"])}
                for e in sorted(self.entities, key=lambda e: (e["name"].casefold(), e["id"]))
                if e["page"]]
        n_single = sum(1 for e in self.entities if e["items"] == 1)
        self.render(out, "entities_index.html",
                    self.page("/entities/", "entities", "Entities",
                              f"{fmt(len(rows))} companies, organisations and other entities "
                              f"named in two or more declared items.",
                              scripts=("index-search",)),
                    rows=rows, n_singletons=n_single)

    def render_entity(self, out: Path, e: dict, rows: List[dict], items: List[dict]) -> None:
        raw = Counter(it["entity_name_raw"] for it in items if it["entity_name_raw"])
        variants = [{"name": n, "items": c}
                    for n, c in sorted(raw.items(), key=lambda kv: (-kv[1], kv[0]))]
        aliases = [{"alias": a["alias"], "method_words": METHOD_WORDS.get(a["method"], a["method"]),
                    "confidence": a["confidence"]} for a in self.aliases.get(e["id"], [])]
        blocs_present = sorted({self.bloc(it) for it in items})
        series = C.bloc_series(blocs_present)
        by_reg: Dict[tuple, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
        for it in items:
            by_reg[(it["chamber"], it["parliament"])][self.bloc(it)].add(it["member_id"])
        regs = sorted(by_reg)
        chart_rows = [(register_label(*k), [len(by_reg[k].get(b, ())) for b, _, _ in series])
                      for k in regs]
        by_reg_head = [("Register", False)] + [(label, True) for _, label, _ in series] + \
            [("Members", True)]
        by_reg_rows = [[label] + [fmt(v) for v in vals] +
                       [fmt(len(set().union(*by_reg[k].values())))]
                       for k, (label, vals) in zip(regs, chart_rows)]
        per_member: Dict[str, List[dict]] = defaultdict(list)
        for it in items:
            per_member[it["member_id"]].append(it)
        member_rows = []
        for mid in sorted(per_member, key=lambda x: (self.member_by_id[x]["name"].casefold(), x)):
            its = per_member[mid]
            regs_m = sorted({(it["chamber"], it["parliament"]) for it in its})
            member_rows.append([
                Markup(f'<a href="/members/{mid}/">{escape(self.member_by_id[mid]["name"])}</a>'),
                ", ".join(register_label(*k) for k in regs_m), fmt(len(its))])
        methods = [x for x in METHOD_ORDER if x in e["methods"]]
        ent = {"id": e["id"], "name": e["name"], "asx": e["asx"],
               "type_label": (e["type"] or "untyped").replace("_", " "),
               "items": len(items), "members": len(per_member),
               "method_words": "; ".join(METHOD_WORDS[x] for x in methods) or "not recorded",
               "honest": self._entity_honest(items), "logo": self.cfg.media.logo(e["id"])}
        chart = Markup(C.stacked(
            "chart-entity-members", f"Distinct members per register by bloc: {e['name']}",
            "Horizontal stacked bars, one per register, of distinct members naming this "
            "entity, split by bloc.", chart_rows, series))
        self.render(out, "entity.html",
                    self.page(f"/entities/{e['id']}/", "entities", e["name"],
                              f"{e['name']}: named in {fmt(len(items))} interests declared by "
                              f"{fmt(len(per_member))} Australian federal MPs and senators.",
                              card=self._entity_card(ent, items, len(regs))),
                    ent=ent, variants=variants, aliases=aliases, chart=chart,
                    by_reg_head=by_reg_head, by_reg_rows=by_reg_rows, member_rows=member_rows,
                    groups=self._groups(rows))

    def render_section(self, out: Path, n: int, items: List[dict]) -> None:
        name = self.section_names[n]
        blocs_present = sorted({self.bloc(it) for it in items})
        series = C.bloc_series(blocs_present)
        cnt = Counter(((it["chamber"], it["parliament"]), self.bloc(it)) for it in items)
        chart_rows = [(register_label(*k), [cnt.get((k, b), 0) for b, _, _ in series])
                      for k in self.registers]
        head = [("Register", False)] + [(label, True) for _, label, _ in series] + \
            [("Total", True)]
        rows = [[label] + [fmt(v) for v in vals] + [fmt(sum(vals))] for label, vals in chart_rows]
        ent_members: Dict[str, set] = defaultdict(set)
        ent_items: Counter = Counter()
        for it in items:
            if it["entity_id"]:
                ent_members[it["entity_id"]].add(it["member_id"])
                ent_items[it["entity_id"]] += 1
        top = sorted(ent_members, key=lambda x: (-len(ent_members[x]), -ent_items[x], x))[:15]
        top_rows = [[self._entity_link(x, self.entity_by_id[x]["name"]),
                     fmt(len(ent_members[x])), fmt(ent_items[x])] for x in top]
        key, senate_words = SENATE_CATEGORY[n]
        senate = (f"{senate_words} (Senate register category {key})." if senate_words else
                  f"Same as the House form (Senate register category {key}).")
        note = ("Section numbers follow the House form; the Senate register's categories are "
                "mapped onto the same numbers. Senate items are the senator's own only.")
        if n in (11, 13):
            note += " The Senate wording here is a plain reading of the Senate register's category."
        sec = {"section": n, "name": name, "house": HOUSE_WORDING[n], "senate": senate,
               "items": len(items), "note": note,
               "no_entity": sum(1 for it in items if not it["entity_id"])}
        chart = Markup(C.stacked(
            f"chart-section-{n}", f"Items in section {n} ({name}) per register by bloc",
            "Horizontal stacked bars, one per register, split by bloc.", chart_rows, series))
        others = [{"section": x, "name": self.section_names[x]}
                  for x in sorted(self.section_names) if x != n]
        self.render(out, "section.html",
                    self.page(f"/sections/{n}/", None, f"Section {n}: {name}",
                              f"Register section {n} ({HOUSE_WORDING[n]}): {fmt(len(items))} "
                              f"declared items by parliament and bloc, and the most named "
                              f"entities.",
                              card=self._bloc_card(
                                  "Register section", f"Section {n}: {name}", HOUSE_WORDING[n],
                                  items, [[fmt(len(items)), "declared items"],
                                          [fmt(len({it["member_id"] for it in items})), "members"],
                                          [fmt(len(ent_members)), "entities named"]])),
                    sec=sec, chart=chart, head=head, rows=rows, top_rows=top_rows, others=others)

    def render_register(self, out: Path, chamber: str, parliament: int,
                        items: List[dict]) -> None:
        cov = next(c for c in self.s["coverage"]
                   if c["chamber"] == chamber and c["parliament"] == parliament)
        docs = [d for d in self.documents if d["chamber"] == chamber and
                d["parliament"] == parliament]
        dates = sorted(d["statement_date"] for d in docs if d["statement_date"])
        sec_counts = Counter(it["section"] for it in items)
        member_items = Counter(it["member_id"] for it in items)
        member_rows = []
        for mid in sorted(member_items, key=lambda x: (self.member_by_id[x]["name"].casefold(), x)):
            t = self.terms.get((mid, chamber, parliament), {})
            member_rows.append([
                Markup(f'<a href="/members/{mid}/">{escape(self.member_by_id[mid]["name"])}</a>'),
                t.get("electorate_or_state") or "not recorded", t.get("party") or "not recorded",
                t.get("bloc") or "not recorded", fmt(member_items[mid])])
        reruns = v1_reruns().get(parliament, []) if chamber == "house" else []
        lim: List[str] = []
        if chamber == "senate":
            source = ("The Senate register's structured data (the senators' interests API), "
                      "read directly with no transcription.")
            lim += ["Senate registers before the 48th parliament are not in this release.",
                    "Only the senator's own interests are public (the part of the form about "
                    "family is confidential), so every item's owner is the senator.",
                    "The source is structured data, not a PDF, so item links go to the Senate "
                    "register rather than to a page."]
        else:
            source = (f"Statement PDFs from aph.gov.au, transcribed by language model: "
                      f"{self._model_text(chamber, parliament)}. A model pair means the second "
                      f"model handled pages the first refused.")
            if parliament == 48:
                lim.append("The live register, transcribed with prompt v1.")
            else:
                lim.append("Transcribed with prompt v0" + (
                    f"; {len(reruns)} {'statement was' if len(reruns) == 1 else 'statements were'}"
                    f" re-run on prompt v1 to itemise attached lists ({', '.join(reruns)})."
                    if reruns else ".") + " A few v0 statements may describe an attachment in "
                    "one item instead of itemising it.")
            if parliament in SCANNED_PARLIAMENTS:
                lim.append("Many statements are scans; expect more missed or misread items than "
                           "in later parliaments, and check the source page.")
            if any(d["url_class"] == U.HOUSE_REDIRECT for d in docs):
                lim.append("Source links go through an APH redirector that may not jump to the "
                           "page; the link text gives the page to open.")
        lim.append("Party and bloc are as at the start of the term; mid-term changes are not "
                   "tracked.")
        n_alt = sum(1 for it in items if it["is_alteration"])
        reg = {"title": register_title(chamber, parliament),
               "years": PARLIAMENT_YEARS.get(parliament, ""), "members": cov["members"],
               "statements": cov["statements"], "items": cov["items"], "alterations": n_alt,
               "dates": (f"{dates[0]} to {dates[-1]}" if dates else "not stated"),
               "source": source, "limitations": lim}
        section_rows = [[Markup(f'<a href="/sections/{n}/">{n}. {escape(self.section_names[n])}'
                                f'</a>'), fmt(sec_counts[n])]
                        for n in sorted(self.section_names) if sec_counts.get(n)]
        chart = Markup(C.single(
            f"chart-register-sections", f"Items per section: {reg['title']}",
            "Horizontal bars: number of declared items in each register section.",
            [(f"{n}. {self.section_names[n]}", sec_counts[n])
             for n in sorted(self.section_names) if sec_counts.get(n)]))
        others = [{"slug": register_slug(*k), "title": register_title(*k)}
                  for k in self.registers if k != (chamber, parliament)]
        self.render(out, "parliament.html",
                    self.page(f"/parliaments/{register_slug(chamber, parliament)}/", None,
                              reg["title"],
                              f"The {reg['title']} register of interests: {fmt(cov['items'])} "
                              f"declared items from {fmt(cov['statements'])} statements, by "
                              f"section and member.",
                              card=self._bloc_card(
                                  "Register of interests", reg["title"],
                                  f"{reg['years']}. Statements dated {reg['dates']}."
                                  if reg["years"] else f"Statements dated {reg['dates']}.",
                                  items, [[fmt(cov["items"]), "declared items"],
                                          [fmt(cov["members"]), "members"],
                                          [fmt(cov["statements"]), "statements"]])),
                    reg=reg, chart=chart, section_rows=section_rows, member_rows=member_rows,
                    others=others)

    def render_explore(self, out: Path) -> None:
        sec = {r["section"]: 0 for r in self.s["sections"]}
        for r in self.s["items_by_section_bloc"]:
            sec[r["section"]] += r["items"]
        section_rows = [[Markup(f'<a href="/sections/{n}/">{n}. {escape(self.section_names[n])}'
                                f'</a>'), fmt(v)] for n, v in sorted(sec.items())]
        self.render(out, "explore.html",
                    self.page("/explore/", "explore", "Explore the items",
                              f"Filter all {fmt(self.s['items'])} declared interests by "
                              f"parliament, party, section, owner, entity and text.",
                              scripts=("explore",)),
                    s=self.s, coverage_rows=self.coverage_rows(), section_rows=section_rows,
                    explorer={"senate_href": U.SENATE_REGISTER_INDEX,
                              "senate_text": U.SENATE_LINK_TEXT})

    def render_data(self, out: Path) -> None:
        dist = self.distribution()
        known = all(d["sha256"] for d in dist)
        downloads = []
        for d in dist:
            downloads.append({**d, "size": d["size"] or "published with the dataset",
                              "sha_text": "published with the dataset"})
        db = next((d for d in dist if d["name"] == export.DB_NAME), None)
        columns = [{"name": n, "type": t, "description": md_inline(desc)}
                   for n, t, desc in export.COLUMNS]
        api_routes = [("/" + path, text) for path, text in DATA_FILES.items()]
        self.render(out, "data.html",
                    self.page("/data/", "data", "Download and reuse the data",
                              "Download the Registers of Interests dataset (SQLite, CSV, JSON "
                              "Lines), read the field dictionary, use the static JSON API or "
                              "query it in the browser.", jsonld=self.jsonld()),
                    downloads=downloads, downloads_known=known,
                    manifest_href=MD.data_url(self.cfg.data_base, "MANIFEST.json"),
                    datapackage_href=MD.data_url(self.cfg.data_base, "datapackage.json"),
                    datasette_href=("https://lite.datasette.io/?url="
                                    + MD.data_url(self.cfg.data_base, export.DB_NAME)),
                    kaggle_href=MD.KAGGLE_URL,
                    db_note=(db["size"] if db and db["size"] else "the whole file"),
                    columns=columns, api_routes=api_routes,
                    example_member=self.members[0]["id"] if self.members else "tony_abbott",
                    bundle_version=WEB_BUNDLE_VERSION,
                    attribution=(f"Australian Parliament Registers of Interests "
                                 f"({self.version}) by Kevin Rassool, CC BY 4.0, transcribed "
                                 f"from the Parliament of Australia website."))

    def render_about(self, out: Path) -> None:
        n_ent = len(self.entities)
        n_untyped = sum(1 for e in self.entities if not e["type"])
        method = md_list(export.README_METHOD.format(n_ent=n_ent))
        limitations = md_list(export.README_LIMITATIONS.format(n_ent=n_ent,
                                                               n_untyped=n_untyped))
        prompts = next(x for x in limitations if "Two prompt versions" in x)
        accuracy_rows = [["Precision", GOLD["precision"]], ["Recall", GOLD["recall"]],
                         ["F1", GOLD["f1"]], ["Owner accuracy", GOLD["owner"]],
                         ["Page accuracy", GOLD["page"]]]
        labels = [
            "Each item shows a confidence badge when the transcriber's confidence was medium "
            "or low; high confidence is not marked.",
            "Party and bloc are the party at the start of each term.",
            "Senate: 48th parliament only, and only the senator's own interests.",
            "One-off entities (names that appear once) are untyped and have no page.",
            "A change type the statement does not give is shown as \"change not stated\".",
            "Entity pages say how each name was matched: the curated alias table, the ASX "
            "listed-companies list, or an LLM grouping of spelling variants.",
            "Counts are counts of declared items, not of their value.",
        ]
        changelog = [{"version": self.version, "loaded_at": self.meta.get("loaded_at", "unknown"),
                      "text": f"{fmt(self.s['items'])} items from {fmt(self.s['statements'])} "
                              f"statements of {fmt(self.s['members'])} members; first release "
                              f"on this site."}]
        self.render(out, "about.html",
                    self.page("/about/", "about", "About this dataset",
                              "How the Registers of Interests dataset was made: collection, "
                              "transcription, validation, entity matching, measured accuracy "
                              "and known limitations."),
                    method=method, limitations=limitations, prompts=prompts,
                    accuracy_rows=accuracy_rows, labels=labels, changelog=changelog,
                    credits=self._credits())

    def _credits(self) -> dict:
        """Image credits for the about page: the APH portraits as one source, each logo with
        its own source, licence and author."""
        media = self.cfg.media
        photos = sorted(media.photos.values(), key=lambda e: e["member_id"])
        logos = []
        for e in sorted(media.logos.values(),
                        key=lambda e: (self.entity_by_id[e["entity_id"]]["name"].casefold(),
                                       e["entity_id"])):
            logos.append({"id": e["entity_id"], "name": self.entity_by_id[e["entity_id"]]["name"],
                          "source_page": e["source_page"], "licence": e["licence"],
                          "licence_url": e.get("licence_url") or None,
                          "author": e.get("author") or ""})
        return {"photos": len(photos),
                "photo_licence": photos[0]["licence"] if photos else None,
                "photo_licence_url": photos[0].get("licence_url") if photos else None,
                "photo_credit": photos[0]["credit"] if photos else None,
                "logos": logos}

    def render_404(self, out: Path) -> None:
        self.render(out, "404.html", self.page("/404.html", None, "Page not found",
                                               "There is no page at this address."))

    # --- all -------------------------------------------------------------------------------

    def render_all(self, out: Path) -> List[str]:
        rows_by_member: Dict[str, List[dict]] = defaultdict(list)
        rows_by_entity: Dict[str, List[dict]] = defaultdict(list)
        self._member_items: Dict[str, List[dict]] = defaultdict(list)
        items_by_entity: Dict[str, List[dict]] = defaultdict(list)
        items_by_section: Dict[int, List[dict]] = defaultdict(list)
        items_by_reg: Dict[tuple, List[dict]] = defaultdict(list)
        for it, r in zip(self.items, self._rows):
            rows_by_member[it["member_id"]].append(r)
            self._member_items[it["member_id"]].append(it)
            items_by_section[it["section"]].append(it)
            items_by_reg[(it["chamber"], it["parliament"])].append(it)
            if it["entity_id"] in self.page_ids:
                rows_by_entity[it["entity_id"]].append(r)
                items_by_entity[it["entity_id"]].append(it)
        self.render_overview(out)
        self.render_members_index(out)
        for m in self.members:
            self.render_member(out, m, rows_by_member.get(m["id"], []))
        self.render_entities_index(out)
        for e in self.entities:
            if e["page"]:
                self.render_entity(out, e, rows_by_entity[e["id"]], items_by_entity[e["id"]])
        for n in sorted(self.section_names):
            self.render_section(out, n, items_by_section.get(n, []))
        for chamber, parliament in self.registers:
            self.render_register(out, chamber, parliament, items_by_reg[(chamber, parliament)])
        self.render_explore(out)
        self.render_data(out)
        self.render_about(out)
        self.render_404(out)
        return list(self.pages)


def render_site(ds: Dataset, out: Path, cfg: SiteConfig) -> Tuple[List[str], List[dict]]:
    """Render every page into ``out`` (after ``bundle.write_data``). Returns the page paths
    (for the sitemap; ``/404.html`` excluded) and every page's Open Graph card spec."""
    summary = json.loads((out / "data" / "summary.json").read_text(encoding="utf-8"))
    r = Renderer(ds, cfg, summary)
    pages = r.render_all(out)
    return pages, r.cards
