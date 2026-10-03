// Load the data bundle (ADR-W3) and decode it into typed arrays the explorer filters.
//
// data/items.json is columnar: cols[<column>] is an array of n values; a "dict" column's values
// index dict[<column>] (sorted distinct strings), -1 for null. member indexes line up with
// data/members.json (sorted by id) and document indexes with data/documents.json (sorted by
// sha256). Nothing here touches the network except these same-origin JSON files.

export interface Term {
  chamber: string;
  parliament: number;
  party: string | null;
  bloc: string | null;
  electorate_or_state: string | null;
}
export interface Member {
  id: string;
  name: string;
  chamber: string;
  items: number;
  terms: Term[];
  documents: string[];
}
export interface Entity {
  id: string;
  name: string;
  type: string | null;
  asx: string | null;
  items: number;
  members: number;
  page: boolean;
}
export interface Doc {
  sha256: string;
  path: string;
  chamber: string;
  parliament: number;
  member_id: string;
  pages: number;
  url: string;
  url_class: string;
  statement_date: string | null;
  extraction_source: string;
  model: string | null;
}
interface ItemsJson {
  n: number;
  web_bundle_version: string;
  columns: string[];
  cols: Record<string, number[]>;
  dict: Record<string, string[]>;
}

export const BUNDLE_VERSION = "1";
export const UNKNOWN_BLOC = "Not stated";

/** Everything the explorer needs, decoded once. Arrays are row-aligned with items.json. */
export interface Data {
  n: number;
  members: Member[];
  entities: Entity[];
  documents: Doc[];
  entityById: Map<string, Entity>;
  sectionNames: Map<number, string>;
  dict: Record<string, string[]>;
  // dict-indexed Int32Arrays (-1 = null) and int columns
  col: Record<string, Int32Array>;
  // derived per row
  bloc: Int32Array;
  party: Int32Array;
  etype: Int32Array;
  blocs: string[];
  parties: string[];
  etypes: string[];
  // text search haystack per row (member name, entity names, description), lower-cased
  text: string[];
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { credentials: "omit" });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return (await r.json()) as T;
}

function fold(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function indexOf(values: string[]): Map<string, number> {
  const m = new Map<string, number>();
  values.forEach((v, i) => m.set(v, i));
  return m;
}

export async function loadData(base: string): Promise<Data> {
  const [items, members, entities, documents, summary] = await Promise.all([
    getJson<ItemsJson>(`${base}items.json`),
    getJson<Member[]>(`${base}members.json`),
    getJson<Entity[]>(`${base}entities.json`),
    getJson<Doc[]>(`${base}documents.json`),
    getJson<{ sections: { section: number; name: string }[] }>(`${base}summary.json`),
  ]);
  if (items.web_bundle_version !== BUNDLE_VERSION) {
    throw new Error(`bundle version ${items.web_bundle_version}, expected ${BUNDLE_VERSION}`);
  }
  const n = items.n;
  const col: Record<string, Int32Array> = {};
  for (const name of items.columns) {
    const src = items.cols[name];
    if (!src || src.length !== n) throw new Error(`column ${name} has ${src?.length} values, expected ${n}`);
    col[name] = Int32Array.from(src);
  }
  if (items.dict.member.length !== members.length) throw new Error("members.json does not match the bundle");
  if (items.dict.document.length !== documents.length) throw new Error("documents.json does not match the bundle");

  // bloc and party per row, from the member's term in that chamber and parliament
  const termBloc = new Map<string, string>();
  const termParty = new Map<string, string>();
  for (const m of members) {
    for (const t of m.terms) {
      const k = `${m.id}|${t.chamber}|${t.parliament}`;
      termBloc.set(k, t.bloc ?? UNKNOWN_BLOC);
      termParty.set(k, t.party ?? UNKNOWN_BLOC);
    }
  }
  const blocSet = new Set<string>();
  const partySet = new Set<string>();
  const blocRaw: string[] = new Array(n);
  const partyRaw: string[] = new Array(n);
  for (let i = 0; i < n; i++) {
    const k = `${members[col.member[i]].id}|${items.dict.chamber[col.chamber[i]]}|${col.parliament[i]}`;
    const b = termBloc.get(k) ?? UNKNOWN_BLOC;
    const p = termParty.get(k) ?? UNKNOWN_BLOC;
    blocRaw[i] = b;
    partyRaw[i] = p;
    blocSet.add(b);
    partySet.add(p);
  }
  const blocOrder = ["Labor", "Coalition", "Crossbench", UNKNOWN_BLOC];
  const blocs = [...blocSet].sort((a, b) => blocOrder.indexOf(a) - blocOrder.indexOf(b) || a.localeCompare(b));
  const parties = [...partySet].sort((a, b) => a.localeCompare(b));
  const blocIx = indexOf(blocs);
  const partyIx = indexOf(parties);
  const bloc = new Int32Array(n);
  const party = new Int32Array(n);
  for (let i = 0; i < n; i++) {
    bloc[i] = blocIx.get(blocRaw[i]) ?? -1;
    party[i] = partyIx.get(partyRaw[i]) ?? -1;
  }

  // entity type per row (entities.json lists every typed entity; others are untyped)
  const entityById = new Map<string, Entity>();
  for (const e of entities) entityById.set(e.id, e);
  const etypeSet = new Set<string>();
  const etypeRaw: string[] = new Array(n);
  for (let i = 0; i < n; i++) {
    const ei = col.entity[i];
    const e = ei >= 0 ? entityById.get(items.dict.entity[ei]) : undefined;
    const t = ei < 0 ? "no entity" : (e?.type ?? "untyped");
    etypeRaw[i] = t;
    etypeSet.add(t);
  }
  const etypes = [...etypeSet].sort((a, b) => a.localeCompare(b));
  const etypeIx = indexOf(etypes);
  const etype = new Int32Array(n);
  for (let i = 0; i < n; i++) etype[i] = etypeIx.get(etypeRaw[i]) ?? -1;

  // search text per row
  const memberName = members.map((m) => fold(m.name));
  const entityName = items.dict.entity.map((id) => fold(entityById.get(id)?.name ?? id.replace(/_/g, " ")));
  const rawName = items.dict.entity_raw.map(fold);
  const desc = items.dict.description.map(fold);
  const text: string[] = new Array(n);
  for (let i = 0; i < n; i++) {
    const parts = [memberName[col.member[i]]];
    if (col.entity[i] >= 0) parts.push(entityName[col.entity[i]]);
    if (col.entity_raw[i] >= 0) parts.push(rawName[col.entity_raw[i]]);
    if (col.description[i] >= 0) parts.push(desc[col.description[i]]);
    text[i] = parts.join(" | ");
  }

  const sectionNames = new Map<number, string>();
  for (const s of summary.sections) sectionNames.set(s.section, s.name);

  return { n, members, entities, documents, entityById, sectionNames, dict: items.dict, col,
           bloc, party, etype, blocs, parties, etypes, text };
}

export { fold };
