// Phase C, the explorer at /explore/ on the mini site: AC-C1 (filters, facet counts, chart,
// URL state), AC-C2 (CSV of the selection), AC-C3 (bundle budget; the transfer and time
// budget is measured on the real site and recorded in BUILDLOG), AC-C4 (prefilter links).
// Expected numbers come from SQL on the fixture DB, not from the bundle the page reads.
import { expect, test, type Page } from "@playwright/test";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";
import { py, sqlCount, siteUrl } from "./site";

async function ready(page: Page, path: string): Promise<void> {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(siteUrl(path));
  await page.waitForSelector("#explorer[data-ready='1']");
  expect(errors).toEqual([]);
}
const count = (page: Page) => page.locator("#explorer").getAttribute("data-count").then(Number);

/** The register (parliament, section) with the most items, so the filter is never empty. */
function busiest(): { parliament: number; section: number } {
  return py(`p, s = DB.execute("select parliament, section from items group by 1, 2 order by count(*) desc, 1, 2").fetchone()
print(json.dumps({"parliament": p, "section": s}))`);
}

test("AC-C1: ?parliament&section count equals SQL; reload restores it", async ({ page }) => {
  const { parliament, section } = busiest();
  const want = sqlCount("parliament = ? and section = ?", [parliament, section]);
  await ready(page, `/explore/?parliament=${parliament}&section=${section}`);
  expect(await count(page)).toBe(want);
  await expect(page.locator(".count-line")).toContainText(want.toLocaleString("en-AU"));
  await page.reload();
  await page.waitForSelector("#explorer[data-ready='1']");
  expect(await count(page)).toBe(want);
});

test("AC-C1: typing a member's surname narrows to that member's rows", async ({ page }) => {
  // a member whose surname appears in no other member's rows (names, entities, descriptions)
  const m = py<{ id: string; surname: string; n: number }>(`
for mid, name in DB.execute("select member_id, full_name from members order by member_id"):
    sur = name.split()[-1].lower()
    n = DB.execute("select count(*) from items where member_id = ?", (mid,)).fetchone()[0]
    other = DB.execute("""select count(*) from items i join members m using (member_id)
        left join entities e using (entity_id) where i.member_id <> ? and (lower(m.full_name)
        like ? or lower(coalesce(e.canonical_name, '')) like ? or lower(coalesce(i.entity_name_raw, ''))
        like ? or lower(i.description) like ?)""", (mid,) + ("%" + sur + "%",) * 4).fetchone()[0]
    if n and not other and "'" not in sur:
        print(json.dumps({"id": mid, "surname": sur, "n": n})); break
`);
  await ready(page, "/explore/");
  await page.fill("#explore-q", m.surname);
  await expect.poll(() => count(page)).toBe(m.n);
  const members = await page.locator("#explore-table tbody tr td:first-child a").evaluateAll(
    (as) => [...new Set(as.map((a) => a.getAttribute("href")))]);
  expect(members).toEqual([`/members/${m.id}/`]);
  await expect(page).toHaveURL(new RegExp(`[?&]q=${m.surname}`));
});

test("AC-C1: toggling a bloc updates facet counts and the chart's bars; URL holds it", async ({ page }) => {
  await ready(page, "/explore/");
  const bloc = py<string>(`print(json.dumps(DB.execute("""select t.political_bloc from items i join member_terms t
    on t.member_id = i.member_id and t.chamber = i.chamber and t.parliament = i.parliament
    group by 1 order by count(*) desc limit 1""").fetchone()[0]))`);
  const join = `join member_terms t on t.member_id = i.member_id and t.chamber = i.chamber and t.parliament = i.parliament`;
  const want = py<{ n: number; sections: number; perSection: Record<string, number> }>(`
rows = DB.execute("""select i.section, count(*) from items i ${join} where t.political_bloc = ? group by 1""", (${JSON.stringify(bloc)},)).fetchall()
print(json.dumps({"n": sum(c for _, c in rows), "sections": len([s for s, _ in rows if s != 8]), "perSection": {str(s): c for s, c in rows}}))`);
  await page.locator(`#explorer input[name="bloc"][value="${bloc}"]`).check();
  await expect.poll(() => count(page)).toBe(want.n);
  // facet counts follow the selection (the bloc facet itself keeps its own counts)
  for (const [s, c] of Object.entries(want.perSection)) {
    await expect(page.locator(`#explorer input[name="section"][value="${s}"] ~ .facet-count`)).toHaveText(c.toLocaleString("en-AU"));
  }
  // one bloc: one bar per section in the selection (bank accounts, section 8, left out by default)
  await expect(page.locator("#chart-section-bloc svg[role='img'] rect")).toHaveCount(want.sections);
  await expect(page).toHaveURL(new RegExp(`[?&]bloc=${encodeURIComponent(bloc)}`));
  await page.reload();
  await page.waitForSelector("#explorer[data-ready='1']");
  expect(await count(page)).toBe(want.n);
});

test("AC-C2: CSV of the selection has the published columns and values equal SQL", async ({ page }) => {
  const { parliament } = busiest();
  await ready(page, `/explore/?parliament=${parliament}`);
  const n = await count(page);
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download CSV of this selection" }).click(),
  ]);
  const text = readFileSync(await download.path(), "utf-8");
  const rows = parseCsv(text);
  const header = rows.shift()!;
  const want = py<{ header: string[]; rows: Record<string, Record<string, unknown>> }>(`
from pathlib import Path
from disclosures.export import HEADER
from disclosures.web.dataset import Dataset
ds = Dataset(Path("tests/fixtures/web/mini.db"), Path("tests/fixtures/web/mini-manifest.csv"))
rows = {r["item_id"]: r for r in ds.export_rows() if r["parliament"] == ${parliament}}
print(json.dumps({"header": list(HEADER), "rows": rows}))`);
  expect(header).toEqual(want.header);
  expect(rows.length).toBe(n);
  expect(Object.keys(want.rows).length).toBe(n);
  // 20 rows spread through the file, every column
  for (let k = 0; k < 20; k++) {
    const row = rows[Math.floor((k * rows.length) / 20)];
    const got = Object.fromEntries(header.map((h, j) => [h, row[j]]));
    const exp = want.rows[got.item_id];
    expect(exp, got.item_id).toBeTruthy();
    for (const h of header) expect(`${h}=${got[h]}`).toBe(`${h}=${exp[h] === null ? "" : String(exp[h])}`);
  }
});

test("AC-C3: explorer JS (table view plus graph view) is at most 250 KB gzipped", async () => {
  const dir = join(process.env.SITE_DIR!, "assets");
  const files = readdirSync(dir).filter((f) => /^explore(-graph)?\.[0-9a-f]{8}\.js$/.test(f));
  expect(files.length).toBe(2);
  const gz = files.reduce((s, f) => s + gzipSync(readFileSync(join(dir, f)), { level: 9 }).length, 0);
  expect(gz).toBeLessThanOrEqual(250 * 1024);
});

test("AC-C4: section, member and entity pages link into a prefiltered explorer", async ({ page }) => {
  const { section } = busiest();
  const e = py<{ id: string; n: number }>(`r = DB.execute("""select entity_id, count(*) from items where entity_id is not null
    group by 1 order by 2 desc, 1 limit 1""").fetchone()
print(json.dumps({"id": r[0], "n": r[1]}))`);
  const m = py<{ id: string; n: number }>(`r = DB.execute("select member_id, count(*) from items group by 1 order by 2 desc, 1 limit 1").fetchone()
print(json.dumps({"id": r[0], "n": r[1]}))`);
  for (const [path, href, want] of [
    [`/sections/${section}/`, `/explore/?section=${section}`, sqlCount("section = ?", [section])],
    [`/entities/${e.id}/`, `/explore/?entity=${e.id}`, e.n],
    [`/members/${m.id}/`, `/explore/?member=${m.id}`, m.n],
  ] as const) {
    await page.goto(siteUrl(path));
    await page.locator(`a[href="${href}"]`).first().click();
    await page.waitForSelector("#explorer[data-ready='1']");
    expect(await count(page), path).toBe(want);
  }
});

/** RFC 4180 CSV (quoted fields may hold commas, quotes and newlines). */
function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
    else if (c !== "\r") field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  return rows;
}
