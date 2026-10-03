// AC-B6: every page works with JavaScript disabled. The overview, a member, an entity and a
// section page show their AC-B2/B3/B4 strings and tables.
import { expect, test } from "@playwright/test";
import { fmt, samples, siteJson, siteUrl } from "./site";

test.use({ javaScriptEnabled: false });

test("overview without JS: headline numbers equal summary.json, tables present", async ({ page }) => {
  const s = siteJson<any>("data/summary.json");
  await page.goto(siteUrl("/"));
  await expect(page.locator("h1")).toHaveText("Australian Parliament Registers of Interests");
  await expect(page.locator('#headline [data-key="items"]')).toHaveText(fmt(s.items));
  await expect(page.locator('#headline [data-key="members"]')).toHaveText(fmt(s.members));
  await expect(page.locator('#headline [data-key="statements"]')).toHaveText(fmt(s.statements));
  await expect(page.locator('#headline [data-key="entities"]')).toHaveText(fmt(s.entities));
  await expect(page.locator('#headline [data-key="data_date"]')).toHaveText(s.data_date);
  await expect(page.locator("table.coverage tbody tr")).toHaveCount(s.coverage.length);
  await expect(page.locator("table.top-entities tbody tr")).toHaveCount(
    s.top_entities_by_members.length);
  await expect(page.locator("svg.chart")).toHaveCount(4);
  await expect(page.locator("footer.site-footer")).toContainText("CC BY 4.0");
});

test("member page without JS: terms, statements, every item, source links", async ({ page }) => {
  const { member } = samples();
  const items = siteJson<any[]>(`members/${member}/items.json`);
  const m = siteJson<any[]>("data/members.json").find((x) => x.id === member);
  await page.goto(siteUrl(`/members/${member}/`));
  await expect(page.locator("h1")).toHaveText(m.name);
  await expect(page.locator("table.terms tbody tr")).toHaveCount(m.terms.length);
  await expect(page.locator("table.statements tbody tr")).toHaveCount(m.documents.length);
  await expect(page.locator("#item-count")).toHaveText(fmt(items.length));
  await expect(page.locator("table.items tbody tr")).toHaveCount(items.length);
  await expect(page.locator("table.items a.source")).toHaveCount(items.length);
  const medium = items.filter((r) => r.extraction_confidence === "medium").length;
  await expect(page.locator(".badge-medium")).toHaveCount(medium);
  await expect(page.locator("svg.chart")).toHaveCount(1);
});

test("entity page without JS: name, match method, members, items", async ({ page }) => {
  const { entity, entityName } = samples();
  const items = siteJson<any[]>(`entities/${entity}/items.json`);
  const members = new Set(items.map((r) => r.member_id));
  await page.goto(siteUrl(`/entities/${entity}/`));
  await expect(page.locator("h1")).toHaveText(entityName);
  await expect(page.locator("#entity-items")).toHaveText(fmt(items.length));
  await expect(page.locator("#entity-members")).toHaveText(fmt(members.size));
  await expect(page.locator("#entity-method")).not.toBeEmpty();
  await expect(page.locator("table.items tbody tr")).toHaveCount(items.length);
  await expect(page.locator("table.entity-members tbody tr")).toHaveCount(members.size);
  await expect(page.locator("table.variants tbody tr").first()).toBeVisible();
});

test("section page without JS: wording, table by parliament and bloc", async ({ page }) => {
  const s = siteJson<any>("data/summary.json");
  const total = s.items_by_section_bloc
    .filter((r: any) => r.section === 1)
    .reduce((a: number, r: any) => a + r.items, 0);
  await page.goto(siteUrl("/sections/1/"));
  await expect(page.locator("h1")).toHaveText("1. Shareholding");
  await expect(page.locator("#house-wording")).toContainText("Shareholdings");
  await expect(page.locator("#section-items")).toHaveText(fmt(total));
  await expect(page.locator("table.section-parliament-bloc tbody tr")).toHaveCount(
    s.coverage.length);
  await expect(page.locator('a[href="/explore/?section=1"]')).toHaveCount(1);
});

test("index pages without JS: full tables, the filter box stays hidden", async ({ page }) => {
  const members = siteJson<any[]>("data/members.json");
  await page.goto(siteUrl("/members/"));
  await expect(page.locator("#members-table tbody tr")).toHaveCount(members.length);
  await expect(page.locator(".filter")).toBeHidden();
  await page.goto(siteUrl("/explore/"));
  await expect(page.locator("table.coverage")).toBeVisible();
  await expect(page.locator("#explore-intro")).toContainText("members index");
  await expect(page.locator("#explorer")).toBeHidden();
});
