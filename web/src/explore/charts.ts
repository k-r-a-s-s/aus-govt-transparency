// Three Observable Plot charts that follow the selection (ADR-W7), coloured from the page's
// CSS tokens (DESIGN.md) read at render time so they match light and dark mode. Each has a
// tooltip per mark, a legend when there is more than one series, one axis, and text in ink.

import * as Plot from "@observablehq/plot";
import type { Data } from "./data";
import { registerLabel } from "./filters";

const BLOC_VARS: Record<string, string> = {
  Labor: "--bloc-labor", Coalition: "--bloc-coalition", Crossbench: "--bloc-crossbench",
};

function cssVar(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function tokens(): { ink: string; muted: string; rule: string; accent: string; blocColor: (b: string) => string } {
  const ink = cssVar("--ink", "#24251f");
  const muted = cssVar("--muted", "#626458");
  return {
    ink, muted,
    rule: cssVar("--rule", "#d2d3c8"),
    accent: cssVar("--seq-3", cssVar("--accent", "#176b50")),
    blocColor: (b: string) => (BLOC_VARS[b] ? cssVar(BLOC_VARS[b], muted) : muted),
  };
}

const base = (width: number, t: ReturnType<typeof tokens>, label: string) => ({
  width,
  marginLeft: 8,
  style: { background: "transparent", color: t.ink, fontFamily: "var(--mono)", fontSize: "11px" },
  ariaLabel: label,
});

/** Plot labels its inner <g> groups with aria-label, which ARIA forbids on role-less elements
 *  (axe aria-prohibited-attr). Give the chart one name on its <svg role="img"> instead; the
 *  result table below is its text equivalent. */
function mount(el: HTMLElement, chart: SVGSVGElement | HTMLElement, label: string): void {
  const svgs = chart instanceof SVGSVGElement ? [chart] : Array.from(chart.querySelectorAll("svg"));
  for (const svg of svgs) {
    svg.querySelectorAll("[aria-label]").forEach((g) => g.removeAttribute("aria-label"));
    svg.querySelectorAll("[aria-description]").forEach((g) => g.removeAttribute("aria-description"));
  }
  const main = chart instanceof SVGSVGElement ? chart : chart.querySelector<SVGSVGElement>("svg:last-of-type");
  if (main) { main.setAttribute("role", "img"); main.setAttribute("aria-label", label); }
  el.replaceChildren(chart);
}

function empty(el: HTMLElement, text: string): void {
  el.replaceChildren(Object.assign(document.createElement("p"), { className: "note", textContent: text }));
}

/** Items per section, stacked by bloc. */
export function sectionByBloc(el: HTMLElement, d: Data, rows: Int32Array): void {
  const t = tokens();
  const counts = new Map<string, number>();
  for (let k = 0; k < rows.length; k++) {
    const i = rows[k];
    const key = `${d.col.section[i]}|${d.blocs[d.bloc[i]]}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  if (!counts.size) return empty(el, "No items in the selection.");
  const data = [...counts].map(([key, n]) => {
    const [s, bloc] = key.split("|");
    const sec = Number(s);
    return { section: `${sec}. ${d.sectionNames.get(sec) ?? ""}`, order: sec, bloc, n };
  });
  const blocs = d.blocs.filter((b) => data.some((r) => r.bloc === b));
  mount(el, Plot.plot({
    ...base(el.clientWidth || 600, t, "Items per section, split by bloc"),
    height: 40 + 26 * new Set(data.map((r) => r.order)).size,
    marginLeft: 150,
    x: { label: "Items", grid: true, tickFormat: "~s" },
    y: { label: null, domain: data.slice().sort((a, b) => a.order - b.order).map((r) => r.section).filter((v, i, a) => a.indexOf(v) === i) },
    color: { domain: blocs, range: blocs.map(t.blocColor), legend: blocs.length > 1 },
    marks: [
      Plot.barX(data, { x: "n", y: "section", fill: "bloc", insetTop: 2, insetBottom: 2, rx: 2,
                        tip: true, title: (r: { section: string; bloc: string; n: number }) => `${r.section}\n${r.bloc}: ${r.n.toLocaleString("en-AU")}` }),
      Plot.ruleX([0], { stroke: t.muted }),
    ],
  }) as SVGSVGElement | HTMLElement, "Items per section, split by bloc");
}

/** Distinct members per register in the selection. */
export function membersByParliament(el: HTMLElement, d: Data, rows: Int32Array): void {
  const t = tokens();
  const sets = new Map<string, Set<number>>();
  for (let k = 0; k < rows.length; k++) {
    const i = rows[k];
    const key = `${d.dict.chamber[d.col.chamber[i]]}|${d.col.parliament[i]}`;
    let s = sets.get(key);
    if (!s) sets.set(key, (s = new Set()));
    s.add(d.col.member[i]);
  }
  if (!sets.size) return empty(el, "No items in the selection.");
  const data = [...sets].map(([key, s]) => {
    const [chamber, p] = key.split("|");
    return { register: registerLabel(chamber, Number(p)), order: (chamber === "senate" ? 1000 : 0) + Number(p), members: s.size };
  }).sort((a, b) => a.order - b.order);
  mount(el, Plot.plot({
    ...base(el.clientWidth || 600, t, "Distinct members per register"),
    height: 40 + 26 * data.length,
    marginLeft: 90,
    x: { label: "Members", grid: true },
    y: { label: null, domain: data.map((r) => r.register) },
    marks: [
      Plot.barX(data, { x: "members", y: "register", fill: t.accent, insetTop: 2, insetBottom: 2, rx: 2, tip: true,
                        title: (r: { register: string; members: number }) => `${r.register}: ${r.members.toLocaleString("en-AU")} members` }),
      Plot.ruleX([0], { stroke: t.muted }),
    ],
  }) as SVGSVGElement | HTMLElement, "Distinct members per register");
}

/** Top entities in the selection, by items (ties by distinct members). */
export function topEntities(el: HTMLElement, d: Data, rows: Int32Array, limit = 15): void {
  const t = tokens();
  const items = new Map<number, number>();
  const members = new Map<number, Set<number>>();
  for (let k = 0; k < rows.length; k++) {
    const i = rows[k];
    const e = d.col.entity[i];
    if (e < 0) continue;
    items.set(e, (items.get(e) ?? 0) + 1);
    let s = members.get(e);
    if (!s) members.set(e, (s = new Set()));
    s.add(d.col.member[i]);
  }
  if (!items.size) return empty(el, "No named entities in the selection.");
  const data = [...items].map(([e, n]) => {
    const id = d.dict.entity[e];
    const name = d.entityById.get(id)?.name ?? id.replace(/_/g, " ");
    return { name: name.length > 42 ? `${name.slice(0, 40)}…` : name, items: n, members: members.get(e)?.size ?? 0 };
  }).sort((a, b) => b.items - a.items || b.members - a.members || a.name.localeCompare(b.name)).slice(0, limit);
  mount(el, Plot.plot({
    ...base(el.clientWidth || 600, t, "Entities named most often in the selection"),
    height: 40 + 24 * data.length,
    marginLeft: 220,
    x: { label: "Items", grid: true },
    y: { label: null, domain: data.map((r) => r.name) },
    marks: [
      Plot.barX(data, { x: "items", y: "name", fill: t.accent, insetTop: 2, insetBottom: 2, rx: 2, tip: true,
                        title: (r: { name: string; items: number; members: number }) => `${r.name}\n${r.items.toLocaleString("en-AU")} items, ${r.members.toLocaleString("en-AU")} members` }),
      Plot.ruleX([0], { stroke: t.muted }),
    ],
  }) as SVGSVGElement | HTMLElement, "Entities named most often in the selection");
}
