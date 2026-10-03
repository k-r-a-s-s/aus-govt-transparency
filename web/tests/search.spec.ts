// Index-page search (web/src/index-search.ts): with JS the filter box appears and typing
// narrows the table rows; clearing it restores every row.
import { expect, test } from "@playwright/test";
import { siteJson, siteUrl } from "./site";

test("members index: typing a surname narrows the rows", async ({ page }) => {
  const members = siteJson<{ id: string; name: string }[]>("data/members.json");
  const target = members[members.length - 1];
  const surname = target.name.split(" ").slice(-1)[0];
  await page.goto(siteUrl("/members/"));
  const box = page.locator("#members-filter");
  await expect(box).toBeVisible();
  const rows = page.locator("#members-table tbody tr:visible");
  await expect(rows).toHaveCount(members.length);
  await box.fill(surname.toUpperCase());
  await expect(rows).toHaveCount(
    members.filter((m) => m.name.toLowerCase().includes(surname.toLowerCase())).length);
  await expect(rows.first()).toContainText(target.name);
  await expect(page.locator("[data-filter-count]")).toContainText("of");
  await box.fill("");
  await expect(rows).toHaveCount(members.length);
});

test("entities index: a query narrows the rows", async ({ page }) => {
  const search = siteJson<{ entities: [string, string, number][] }>("data/search.json");
  await page.goto(siteUrl("/entities/"));
  const rows = page.locator("#entities-table tbody tr:visible");
  await expect(rows).toHaveCount(search.entities.length);
  const name = search.entities[0][1];
  await page.locator("#entities-filter").fill(name);
  const n = await rows.count();
  expect(n).toBeGreaterThan(0);
  expect(n).toBeLessThan(search.entities.length);
  await expect(rows.first()).toContainText(name);
  await page.locator("#entities-filter").fill("zzzz-no-such-entity");
  await expect(rows).toHaveCount(0);
});
