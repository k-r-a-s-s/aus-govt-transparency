// The explorer's network graph view (SPEC decisions log 2026-10-03, ported from the Pages
// explorer): opens from the view switch or ?view=graph, follows the filters, its counts equal
// SQL, hovering a bar shows a tooltip, a click pins a panel that links back to the table, and
// it passes axe and the 375px layout check.
import { expect, test, type Page } from "@playwright/test";
import { createRequire } from "node:module";
import { py, siteUrl } from "./site";

const require = createRequire(import.meta.url);
const AXE = require.resolve("axe-core/axe.min.js");

/** Top 60 entities by distinct members (ties by id), as graph-model.ts builds them; everyday
 *  banking (sections 6 and 8) left out unless `banking`. */
function expected(where = "1", banking = false): { entities: number; members: number; links: number; top: string; topName: string } {
  return py(`
rows = DB.execute("""select i.entity_id, i.member_id from items i join entities e using (entity_id)
    join member_terms t on t.member_id = i.member_id and t.chamber = i.chamber and t.parliament = i.parliament
    where ${banking ? "1" : "i.section not in (6, 8)"} and (${where})""").fetchall()
by = {}
for e, m in rows:
    by.setdefault(e, set()).add(m)
top = sorted(by, key=lambda e: (-len(by[e]), e))[:60]
name = DB.execute("select canonical_name from entities where entity_id = ?", (top[0],)).fetchone()[0] if top else ""
print(json.dumps({"entities": len(top), "members": len({m for e in top for m in by[e]}),
                  "links": sum(len(by[e]) for e in top), "top": top[0] if top else "", "topName": name}))`);
}

async function graphReady(page: Page, path: string): Promise<string[]> {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto(siteUrl(path));
  await page.waitForSelector("#explorer[data-graph-ready='1']");
  return errors;
}
const attr = (page: Page, name: string) => page.locator("#explore-graph").getAttribute(`data-${name}`).then(Number);

test("?view=graph opens the graph; its counts equal SQL; no errors", async ({ page }) => {
  const want = expected();
  const errors = await graphReady(page, "/explore/?view=graph");
  expect(await attr(page, "entities")).toBe(want.entities);
  expect(await attr(page, "members")).toBe(want.members);
  expect(await attr(page, "links")).toBe(want.links);
  await expect(page.locator("#explore-graph canvas")).toHaveCount(1);
  await expect(page.locator("#explore-table")).toBeHidden();
  await expect(page.locator(".explorer-charts")).toBeHidden();
  await expect(page.locator(".graph-bar")).toHaveCount(Math.min(20, want.entities));
  await expect(page.locator(".graph-bar .name").first()).toHaveText(want.topName);
  await expect(page.locator("#graph-table tbody tr")).toHaveCount(want.entities);
  await page.waitForSelector("#explore-graph[data-settled='1']");
  expect(errors).toEqual([]);
});

test("view switch: the button sets ?view=graph, reload keeps it, table view drops it", async ({ page }) => {
  await page.goto(siteUrl("/explore/?parliament=48"));
  await page.waitForSelector("#explorer[data-ready='1']");
  await page.getByRole("button", { name: "Network graph" }).click();
  await page.waitForSelector("#explorer[data-graph-ready='1']");
  await expect(page).toHaveURL(/\?parliament=48&view=graph$/);
  expect(await attr(page, "entities")).toBe(expected("i.parliament = 48").entities);
  await page.reload();
  await page.waitForSelector("#explorer[data-graph-ready='1']");
  await expect(page.getByRole("button", { name: "Network graph" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Table and charts" }).click();
  await expect(page).toHaveURL(/\?parliament=48$/);
  await expect(page.locator("#explore-table")).toBeVisible();
  await expect(page.locator("#explore-graph")).toBeHidden();
});

test("the graph follows the filters", async ({ page }) => {
  await graphReady(page, "/explore/?view=graph");
  const bloc = "Labor";
  const want = expected(`t.political_bloc = '${bloc}'`);
  await page.locator(`#explorer input[name="bloc"][value="${bloc}"]`).check();
  await expect.poll(() => attr(page, "links")).toBe(want.links);
  expect(await attr(page, "entities")).toBe(want.entities);
  expect(await attr(page, "members")).toBe(want.members);
});

test("hover a bar: tooltip; click: panel; 'show these items' filters the table", async ({ page }) => {
  const want = expected();
  const n = py<number>(`print(DB.execute("select count(*) from items where entity_id = ?", (${JSON.stringify(want.top)},)).fetchone()[0])`);
  await graphReady(page, "/explore/?view=graph");
  const bar = page.locator(".graph-bar").first();
  await bar.hover();
  await expect(page.locator("#graph-tip")).toHaveClass(/show/);
  await expect(page.locator("#graph-tip")).toContainText(want.topName);
  await expect(page.locator("#graph-tip")).toContainText("declared it");
  await bar.click();
  await expect(page.locator(".graph-bar").first()).toHaveClass(/active/);
  const panel = page.locator("#graph-panel");
  await expect(panel).toHaveClass(/open/);
  await expect(panel.locator("h3")).toHaveText(want.topName);
  await panel.getByRole("button", { name: "Show these items in the table" }).click();
  await expect(page).toHaveURL(new RegExp(`[?&]entity=${want.top}(&|$)`));
  await expect(page.locator("#explore-table")).toBeVisible();
  expect(Number(await page.locator("#explorer").getAttribute("data-count"))).toBe(n);
});

test("panel: a member in the list re-pins the panel on that member", async ({ page }) => {
  await graphReady(page, "/explore/?view=graph");
  await page.locator(".graph-bar").first().click();
  const first = page.locator("#graph-panel li[data-id^='m:']").first();
  const name = (await first.innerText()).replace(/\s*\d+$/, "").trim();
  await first.click();
  await expect(page.locator("#graph-panel h3")).toHaveText(name);
  await expect(page.locator("#graph-panel a[href^='/members/']")).toHaveText("Member page");
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe: no serious or critical violations in the graph view (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await graphReady(page, "/explore/?view=graph");
    await page.locator(".graph-bar").first().click();
    await page.addScriptTag({ path: AXE });
    const result: any = await page.evaluate(async () => {
      // @ts-ignore injected above
      return await window.axe.run(document, { resultTypes: ["violations"] });
    });
    const serious = result.violations
      .filter((v: any) => v.impact === "serious" || v.impact === "critical")
      .map((v: any) => `${v.id}: ${v.nodes.slice(0, 3).map((x: any) => x.target.join(" ")).join(" | ")}`);
    expect(serious).toEqual([]);
  });
}

test("everyday banking: left out of the graph by default; the toggle puts it back", async ({ page }) => {
  const hidden = expected();
  const shown = expected("1", true);
  const n8 = py<number>(`print(DB.execute("select count(*) from items where section in (6, 8)").fetchone()[0])`);
  await graphReady(page, "/explore/?view=graph");
  const box = page.locator("#explore-hide-banking");
  await expect(box).toBeChecked();
  expect(await attr(page, "links")).toBe(hidden.links);
  await expect(page.locator("#explore-viz-note")).toHaveText(`(${n8.toLocaleString("en-AU")} items left out)`);
  await box.uncheck();
  await expect.poll(() => attr(page, "links")).toBe(shown.links);
  await expect(page).toHaveURL(/[?&]banking=show/);
  await expect(page.locator("#explore-viz-note")).toHaveText("");
  // the table and counts never drop them
  expect(Number(await page.locator("#explorer").getAttribute("data-count"))).toBe(
    py<number>(`print(DB.execute("select count(*) from items").fetchone()[0])`));
  await page.reload();
  await page.waitForSelector("#explorer[data-graph-ready='1']");
  await expect(page.locator("#explore-hide-banking")).not.toBeChecked();
  expect(await attr(page, "links")).toBe(shown.links);
});

test("everyday banking: a section picked in the filter is drawn, the other stays out", async ({ page }) => {
  await graphReady(page, "/explore/?section=1,8&view=graph");
  expect(await attr(page, "links")).toBe(expected("i.section in (1, 8)", true).links);
  await graphReady(page, "/explore/?section=6&view=graph");
  expect(await attr(page, "links")).toBe(expected("i.section = 6", true).links);
});

test.describe("375px", () => {
  test.use({ viewport: { width: 375, height: 800 } });
  test("graph view does not scroll sideways", async ({ page }) => {
    await graphReady(page, "/explore/?view=graph");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
  });
});

test("zoomed in, member dots draw their photo (same-origin /media/ requests); no errors", async ({ page }) => {
  const errors = await graphReady(page, "/explore/?view=graph");
  await page.waitForSelector("#explore-graph[data-settled='1']");
  await expect(page.locator("#explore-graph")).toHaveAttribute("data-media", /^[1-9]\d*$/);
  const photo = page.waitForRequest((r) => /\/media\/p\/[a-z0-9_]+\.[0-9a-f]{8}\.jpg$/.test(new URL(r.url()).pathname));
  const canvas = page.locator("#graph-canvas canvas");
  await canvas.scrollIntoViewIfNeeded();
  const box = (await canvas.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let i = 0; i < 12; i++) { await page.mouse.wheel(0, -300); await page.waitForTimeout(60); }
  const req = await photo;
  expect(new URL(req.url()).origin).toBe(new URL(page.url()).origin);
  expect(errors).toEqual([]);
});

test("member page shows the portrait; members index shows avatars", async ({ page }) => {
  await page.goto(siteUrl("/members/josh_wilson/"));
  const img = page.locator(".portrait img");
  await expect(img).toHaveAttribute("alt", "Official portrait of Josh Wilson");
  expect(await img.evaluate((el: HTMLImageElement) => el.decode().then(() => el.naturalWidth))).toBeGreaterThan(100);
  await page.goto(siteUrl("/members/"));
  expect(await page.locator("#members-table .avatar img").count()).toBeGreaterThan(0);
});
