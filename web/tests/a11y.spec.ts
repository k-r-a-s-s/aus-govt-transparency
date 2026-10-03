// AC-B10: axe-core (injected from node_modules, no network) finds no serious or critical
// violations on the overview, a member page and the explorer page (light and dark themes);
// at 375px no page type scrolls sideways.
import { expect, test, type Page } from "@playwright/test";
import { createRequire } from "node:module";
import { pageTypes, samples, siteUrl } from "./site";

const require = createRequire(import.meta.url);
const AXE = require.resolve("axe-core/axe.min.js");

async function seriousViolations(page: Page): Promise<string[]> {
  await page.addScriptTag({ path: AXE });
  const result: any = await page.evaluate(async () => {
    // @ts-ignore injected above
    return await window.axe.run(document, { resultTypes: ["violations"] });
  });
  return result.violations
    .filter((v: any) => v.impact === "serious" || v.impact === "critical")
    .map((v: any) => `${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map((n: any) => n.target.join(" ")).join(" | ")}`);
}

for (const scheme of ["light", "dark"] as const) {
  for (const path of ["/", "member", "/explore/"]) {
    test(`axe: no serious or critical violations on ${path} (${scheme})`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      const { member } = samples();
      await page.goto(siteUrl(path === "member" ? `/members/${member}/` : path));
      expect(await seriousViolations(page)).toEqual([]);
    });
  }
}

test.describe("375px layout", () => {
  test.use({ viewport: { width: 375, height: 800 } });
  test("no page type overflows horizontally", async ({ page }) => {
    const wide: string[] = [];
    for (const path of pageTypes()) {
      await page.goto(siteUrl(path));
      const w = await page.evaluate(() => document.documentElement.scrollWidth);
      if (w > 375) wide.push(`${path}: ${w}px`);
    }
    expect(wide).toEqual([]);
  });
});
