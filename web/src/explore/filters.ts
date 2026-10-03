// Filter state, its URL form, and the selection and facet counts over the decoded bundle.
//
// Every active filter lives in the query string (?parliament=47&section=1&bloc=Coalition&q=qantas,
// multi-values comma-separated), so a view can be shared and the section, member and entity
// pages can link into a prefiltered view (member=<id>, entity=<id>). view=graph opens the
// network graph instead of the table and charts; it is not a filter.

import type { Data } from "./data";
import { fold } from "./data";

export const OWNER: Record<string, string> = {
  self: "Self", spouse: "Spouse or partner", dependent_child: "Dependent child", unknown: "Not stated",
};
export const CHANGE: Record<string, string> = {
  initial: "Initial statement", added: "Added", removed: "Removed", varied: "Varied",
  unknown: "change not stated",
};
export const CHAMBER: Record<string, string> = { house: "House", senate: "Senate" };

export function ordinal(n: number): string {
  const r100 = n % 100;
  const suffix = r100 >= 10 && r100 <= 20 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${suffix}`;
}
export const registerLabel = (chamber: string, parliament: number): string =>
  `${CHAMBER[chamber] ?? chamber} ${ordinal(parliament)}`;

/** One filterable dimension: each row has an index into `values`; `labels` is what we show. */
export interface Facet {
  key: string;
  title: string;
  values: string[];
  labels: string[];
  idx: Int32Array;
}

export const FACET_KEYS = ["chamber", "parliament", "bloc", "party", "section", "owner", "type", "change", "confidence"] as const;
export type FacetKey = (typeof FACET_KEYS)[number];

export interface State {
  facets: Record<FacetKey, Set<string>>;
  q: string;
  member: string | null;
  entity: string | null;
  view: View;
}
export type View = "table" | "graph";

export function emptyState(): State {
  const facets = {} as Record<FacetKey, Set<string>>;
  for (const k of FACET_KEYS) facets[k] = new Set();
  return { facets, q: "", member: null, entity: null, view: "table" };
}

function intFacet(key: string, title: string, src: Int32Array, label: (v: number) => string): Facet {
  const distinct = [...new Set(Array.from(src))].sort((a, b) => a - b);
  const pos = new Map<number, number>();
  distinct.forEach((v, i) => pos.set(v, i));
  const idx = new Int32Array(src.length);
  for (let i = 0; i < src.length; i++) idx[i] = pos.get(src[i]) ?? -1;
  return { key, title, values: distinct.map(String), labels: distinct.map(label), idx };
}

function dictFacet(key: string, title: string, src: Int32Array, values: string[], label: (v: string) => string, order?: string[]): Facet {
  if (!order) return { key, title, values, labels: values.map(label), idx: src };
  // re-order the dictionary into the display order
  const rank = new Map(order.map((v, i) => [v, i]));
  const sorted = values.map((v, i) => ({ v, i })).sort((a, b) => (rank.get(a.v) ?? 99) - (rank.get(b.v) ?? 99) || a.v.localeCompare(b.v));
  const remap = new Int32Array(values.length);
  sorted.forEach((s, j) => { remap[s.i] = j; });
  const idx = new Int32Array(src.length);
  for (let i = 0; i < src.length; i++) idx[i] = src[i] < 0 ? -1 : remap[src[i]];
  return { key, title, values: sorted.map((s) => s.v), labels: sorted.map((s) => label(s.v)), idx };
}

export function makeFacets(d: Data): Record<FacetKey, Facet> {
  return {
    chamber: dictFacet("chamber", "Chamber", d.col.chamber, d.dict.chamber, (v) => CHAMBER[v] ?? v),
    parliament: intFacet("parliament", "Parliament", d.col.parliament, (v) => ordinal(v)),
    bloc: { key: "bloc", title: "Bloc", values: d.blocs, labels: d.blocs, idx: d.bloc },
    party: { key: "party", title: "Party (start of term)", values: d.parties, labels: d.parties, idx: d.party },
    section: intFacet("section", "Section", d.col.section, (v) => `${v}. ${d.sectionNames.get(v) ?? ""}`),
    owner: dictFacet("owner", "Owner", d.col.owner, d.dict.owner, (v) => OWNER[v] ?? v, ["self", "spouse", "dependent_child", "unknown"]),
    type: { key: "type", title: "Entity type", values: d.etypes, labels: d.etypes.map((t) => t.replace(/_/g, " ")), idx: d.etype },
    change: dictFacet("change", "Change", d.col.change_type, d.dict.change_type, (v) => CHANGE[v] ?? v, ["initial", "added", "removed", "varied", "unknown"]),
    confidence: dictFacet("confidence", "Confidence", d.col.confidence, d.dict.confidence, (v) => v, ["high", "medium", "low"]),
  };
}

// --- URL <-> state -----------------------------------------------------------------------------

export function stateFromUrl(search: string): State {
  const p = new URLSearchParams(search);
  const s = emptyState();
  for (const k of FACET_KEYS) {
    const v = p.get(k);
    if (v) for (const part of v.split(",")) if (part) s.facets[k].add(part);
  }
  s.q = (p.get("q") ?? "").trim();
  s.member = p.get("member") || null;
  s.entity = p.get("entity") || null;
  s.view = p.get("view") === "graph" ? "graph" : "table";
  return s;
}

export function stateToSearch(s: State): string {
  const p = new URLSearchParams();
  for (const k of FACET_KEYS) if (s.facets[k].size) p.set(k, [...s.facets[k]].sort().join(","));
  if (s.q) p.set("q", s.q);
  if (s.member) p.set("member", s.member);
  if (s.entity) p.set("entity", s.entity);
  if (s.view === "graph") p.set("view", "graph");
  const str = p.toString().replace(/%2C/g, ",");
  return str ? `?${str}` : "";
}

export function isEmpty(s: State): boolean {
  return !s.q && !s.member && !s.entity && FACET_KEYS.every((k) => s.facets[k].size === 0);
}

// --- selection -------------------------------------------------------------------------------

export interface Selection {
  /** Row indexes in the selection, in display order. */
  rows: Int32Array;
  /** facet key -> counts per facet value, over the selection with that facet's own filter lifted. */
  counts: Record<FacetKey, Int32Array>;
}

/** Display order: parliament desc, member name, section, then bundle order. Computed once. */
export function displayOrder(d: Data): Int32Array {
  const names = d.members.map((m) => m.name);
  const order = Array.from({ length: d.n }, (_, i) => i);
  order.sort((a, b) =>
    d.col.parliament[b] - d.col.parliament[a] ||
    names[d.col.member[a]].localeCompare(names[d.col.member[b]]) ||
    d.col.section[a] - d.col.section[b] ||
    a - b);
  return Int32Array.from(order);
}

export function select(d: Data, facets: Record<FacetKey, Facet>, s: State, order: Int32Array): Selection {
  const n = d.n;
  // one mask per facet with a selection; null when the facet is unfiltered
  const masks: (Uint8Array | null)[] = FACET_KEYS.map((k) => {
    const sel = s.facets[k];
    if (!sel.size) return null;
    const f = facets[k];
    const want = new Uint8Array(f.values.length);
    f.values.forEach((v, i) => { if (sel.has(v)) want[i] = 1; });
    const m = new Uint8Array(n);
    for (let i = 0; i < n; i++) m[i] = f.idx[i] >= 0 ? want[f.idx[i]] : 0;
    return m;
  });
  // fixed masks: text query, member, entity (always applied, never lifted)
  const fixed = new Uint8Array(n).fill(1);
  if (s.q) {
    const words = fold(s.q).split(/\s+/).filter(Boolean);
    for (let i = 0; i < n; i++) if (!words.every((w) => d.text[i].includes(w))) fixed[i] = 0;
  }
  if (s.member) {
    const mi = d.members.findIndex((m) => m.id === s.member);
    for (let i = 0; i < n; i++) if (d.col.member[i] !== mi) fixed[i] = 0;
  }
  if (s.entity) {
    const ei = d.dict.entity.indexOf(s.entity);
    for (let i = 0; i < n; i++) if (d.col.entity[i] !== ei) fixed[i] = 0;
  }

  const counts = {} as Record<FacetKey, Int32Array>;
  FACET_KEYS.forEach((k) => { counts[k] = new Int32Array(facets[k].values.length); });
  const inSel = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    if (!fixed[i]) continue;
    let fails = 0;
    let failed = -1;
    for (let f = 0; f < masks.length; f++) {
      const m = masks[f];
      if (m && !m[i]) { fails++; failed = f; if (fails > 1) break; }
    }
    if (fails === 0) {
      inSel[i] = 1;
      for (let f = 0; f < FACET_KEYS.length; f++) {
        const ix = facets[FACET_KEYS[f]].idx[i];
        if (ix >= 0) counts[FACET_KEYS[f]][ix]++;
      }
    } else if (fails === 1) {
      const k = FACET_KEYS[failed];
      const ix = facets[k].idx[i];
      if (ix >= 0) counts[k][ix]++;
    }
  }
  let total = 0;
  for (let i = 0; i < n; i++) total += inSel[i];
  const rows = new Int32Array(total);
  let j = 0;
  for (let k = 0; k < n; k++) { const i = order[k]; if (inSel[i]) rows[j++] = i; }
  return { rows, counts };
}
