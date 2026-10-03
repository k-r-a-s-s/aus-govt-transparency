// "Download CSV of this selection": every published column (export.HEADER), built in the
// browser from the bundle plus data/items-extra.json (fetched only when a reader downloads).

import type { Data } from "./data";
import { dictValue } from "./table";

interface Extra {
  web_bundle_version: string;
  n: number;
  header: string[];
  item_id: string[];
  entity: { name: (string | null)[]; type: (string | null)[]; asx: (string | null)[] };
  entity_raw_method: (string | null)[];
  category: Record<string, string>;
}

let extraPromise: Promise<Extra> | null = null;

export function loadExtra(base: string): Promise<Extra> {
  if (!extraPromise) {
    extraPromise = fetch(`${base}items-extra.json`, { credentials: "omit" }).then((r) => {
      if (!r.ok) throw new Error(`items-extra.json: HTTP ${r.status}`);
      return r.json() as Promise<Extra>;
    });
  }
  return extraPromise;
}

const cell = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

/** One CSV row per selected item, columns in the published order. */
export function buildCsv(d: Data, extra: Extra, rows: Int32Array): string {
  const out: string[] = [extra.header.join(",")];
  const termOf = new Map<string, { party: string | null; bloc: string | null; place: string | null }>();
  for (const m of d.members) for (const t of m.terms) termOf.set(`${m.id}|${t.chamber}|${t.parliament}`, { party: t.party, bloc: t.bloc, place: t.electorate_or_state });
  for (let k = 0; k < rows.length; k++) {
    const i = rows[k];
    const m = d.members[d.col.member[i]];
    const chamber = d.dict.chamber[d.col.chamber[i]];
    const parliament = d.col.parliament[i];
    const term = termOf.get(`${m.id}|${chamber}|${parliament}`);
    const doc = d.documents[d.col.document[i]];
    const ei = d.col.entity[i];
    const ri = d.col.entity_raw[i];
    const values: Record<string, string | number | null> = {
      item_id: extra.item_id[i],
      chamber,
      parliament,
      member_id: m.id,
      member_name: m.name,
      party: term?.party ?? null,
      political_bloc: term?.bloc ?? null,
      electorate_or_state: term?.place ?? null,
      statement_date: doc.statement_date,
      section: d.col.section[i],
      subsection: dictValue(d, "subsection", i),
      category: extra.category[String(d.col.section[i])] ?? null,
      owner: dictValue(d, "owner", i),
      entity_name_as_printed: ri < 0 ? null : d.dict.entity_raw[ri],
      entity_id: ei < 0 ? null : d.dict.entity[ei],
      entity_name: ei < 0 ? null : extra.entity.name[ei],
      entity_type: ei < 0 ? null : extra.entity.type[ei],
      entity_asx_code: ei < 0 ? null : extra.entity.asx[ei],
      entity_match_method: ri < 0 ? null : extra.entity_raw_method[ri],
      description: dictValue(d, "description", i),
      location: dictValue(d, "location", i),
      purpose: dictValue(d, "purpose", i),
      is_alteration: d.col.alteration[i],
      change_type: dictValue(d, "change_type", i),
      lodged_date: dictValue(d, "lodged_date", i),
      date_precision: dictValue(d, "date_precision", i),
      page: d.col.page[i],
      extraction_confidence: dictValue(d, "confidence", i),
      source_file: doc.path,
      source_sha256: doc.sha256,
      source_url: doc.url,
      extraction_source: doc.extraction_source,
      extraction_model: doc.model,
    };
    out.push(extra.header.map((h) => cell(values[h])).join(","));
  }
  return out.join("\n") + "\n";
}

export function download(text: string, filename: string): void {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
