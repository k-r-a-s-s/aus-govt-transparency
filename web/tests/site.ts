// Shared helpers: the served mini site's URL and directory, and facts read from its JSON.
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

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

// --- SQL on the fixture DB (the explorer specs compare the page with it, not with the bundle) --

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
export const MINI_DB = join(REPO, "tests", "fixtures", "web", "mini.db");

function python(): string {
  if (process.env.PYTHON) return process.env.PYTHON;
  const venv = join(REPO, ".venv", "bin", "python");
  return existsSync(venv) ? venv : "python3";
}

/** Run a Python snippet in the repo (read-only DB at `DB`) and parse what it prints as JSON. */
export function py<T = any>(code: string): T {
  const prelude = "import json, sqlite3\n" +
    `DB = sqlite3.connect("file:${MINI_DB}?mode=ro", uri=True)\n`;
  const out = execFileSync(python(), ["-c", prelude + code], { cwd: REPO, encoding: "utf-8" });
  return JSON.parse(out) as T;
}

/** select count(*) from items where <where>. */
export function sqlCount(where: string, args: (string | number)[] = []): number {
  return py<number>(`print(DB.execute("select count(*) from items i where ${where.replace(/"/g, '\\"')}", ${JSON.stringify(args)}).fetchone()[0])`);
}
