// AC-B9: no third-party requests and no cookies. Every request on these pages goes to the
// site's own origin (the documented data host is allowed on /data/ only, and is only linked,
// never fetched); fonts come from /fonts/.
import { expect, test } from "@playwright/test";
import { samples, siteUrl } from "./site";

const DATA_HOST = "data.kevinrassool.com";

for (const path of ["/", "member", "entity", "/explore/", "/data/"]) {
  test(`requests on ${path} are same-origin`, async ({ page, context }) => {
    const { member, entity } = samples();
    const url = siteUrl(
      path === "member" ? `/members/${member}/` : path === "entity" ? `/entities/${entity}/` : path,
    );
    const origin = new URL(url).origin;
    const seen: { url: string; type: string }[] = [];
    page.on("request", (r) => seen.push({ url: r.url(), type: r.resourceType() }));
    await page.goto(url, { waitUntil: "networkidle" });
    expect(seen.length).toBeGreaterThan(0);
    for (const r of seen) {
      const u = new URL(r.url);
      const allowed = u.origin === origin || (path === "/data/" && u.hostname === DATA_HOST);
      expect(allowed, `third-party request ${r.url}`).toBe(true);
    }
    const fonts = seen.filter((r) => r.type === "font");
    expect(fonts.length).toBeGreaterThan(0);
    for (const f of fonts) expect(new URL(f.url).pathname.startsWith("/fonts/")).toBe(true);
    expect(await context.cookies()).toEqual([]);
    expect(await page.evaluate(() => document.cookie)).toBe("");
  });
}
