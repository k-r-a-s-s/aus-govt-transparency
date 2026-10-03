// Shared helpers: the served mini site's URL and directory, and facts read from its JSON.
import { readFileSync } from "node:fs";
import { join } from "node:path";

export function siteUrl(path = "/"): string {
  const base = process.env.SITE_URL;
  if (!base) throw new Error("SITE_URL not set: run through playwright test (global setup)");
  return base + path;
}

export function siteJson<T = any>(rel: string): T {
  const dir = process.env.SITE_DIR;
  if (!dir) throw new Error("SITE_DIR not set");
  return JSON.parse(readFileSync(join(dir, rel), "utf-8")) as T;
}

export const fmt = (n: number): string => n.toLocaleString("en-US");

/** The member with the most items and the entity page with the most items, from the bundle. */
export function samples(): { member: string; entity: string; entityName: string } {
  const members = siteJson<{ id: string; items: number }[]>("data/members.json");
  const member = [...members].sort((a, b) => b.items - a.items || a.id.localeCompare(b.id))[0].id;
  const search = siteJson<{ entities: [string, string, number][] }>("data/search.json");
  const [entity, entityName] = [...search.entities].sort(
    (a, b) => b[2] - a[2] || a[0].localeCompare(b[0]),
  )[0];
  return { member, entity, entityName };
}

/** Every HTML page type, for the layout checks. */
export function pageTypes(): string[] {
  const { member, entity } = samples();
  return [
    "/", "/members/", `/members/${member}/`, "/entities/", `/entities/${entity}/`,
    "/sections/1/", "/parliaments/house-43/", "/parliaments/senate-48/", "/explore/", "/data/",
    "/about/", "/404.html",
  ];
}
