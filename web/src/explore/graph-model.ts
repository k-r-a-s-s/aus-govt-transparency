// The network graph's data (ported from the GitHub Pages explorer, disclosures/explore.py):
// the entities the most members declared in the current selection, the members who
// declared them, and one link per (member, entity) pair. Every entity type is included (people
// named in the registers too: the registers are public records). Built in the browser from the
// selection's rows, so it follows every explorer filter.

import type { Data, Member } from "./data";

export const TOP_ENTITIES = 60;
export const GRAPH_BLOCS = ["Labor", "Coalition", "Crossbench"] as const;

export interface GraphEntity {
  id: string;
  name: string;
  type: string | null;
  asx: string | null;
  page: boolean;
  members: number;
  items: number;
  blocs: Record<string, number>;
  years: [string, string] | null;
}
export interface GraphMember {
  id: string;
  name: string;
  chamber: string;
  seat: string;
  party: string;
  bloc: string;
  parliaments: number[];
}
export interface GraphModel {
  entities: GraphEntity[];
  members: GraphMember[];
  /** [member id, entity id, items] */
  links: [string, string, number][];
}

/** Bloc, party and seat from the member's latest term (the colour the graph gives them). */
export function latestTerm(m: Member): GraphMember {
  let t = m.terms[0];
  for (const x of m.terms) if (x.parliament > t.parliament || (x.parliament === t.parliament && x.chamber === "senate")) t = x;
  const bloc = t?.bloc && (GRAPH_BLOCS as readonly string[]).includes(t.bloc) ? t.bloc : "Crossbench";
  return {
    id: m.id, name: m.name, chamber: t?.chamber ?? m.chamber, seat: t?.electorate_or_state ?? "",
    party: t?.party ?? "", bloc,
    parliaments: [...new Set(m.terms.map((x) => x.parliament))].sort((a, b) => a - b),
  };
}

export function graphModel(d: Data, rows: Int32Array, limit = TOP_ENTITIES): GraphModel {
  // entity index -> member index -> items; years per entity
  const pairs = new Map<number, Map<number, number>>();
  const years = new Map<number, [string, string]>();
  const lodged = d.dict.lodged_date;
  for (let k = 0; k < rows.length; k++) {
    const i = rows[k];
    const e = d.col.entity[i];
    if (e < 0) continue;
    let byMember = pairs.get(e);
    if (!byMember) pairs.set(e, (byMember = new Map()));
    const m = d.col.member[i];
    byMember.set(m, (byMember.get(m) ?? 0) + 1);
    const li = d.col.lodged_date[i];
    if (li >= 0) {
      const y = lodged[li].slice(0, 4);
      const r = years.get(e);
      if (!r) years.set(e, [y, y]);
      else { if (y < r[0]) r[0] = y; if (y > r[1]) r[1] = y; }
    }
  }
  const ids = d.dict.entity;
  const top = [...pairs.keys()]
    .sort((a, b) => pairs.get(b)!.size - pairs.get(a)!.size || (ids[a] < ids[b] ? -1 : ids[a] > ids[b] ? 1 : 0))
    .slice(0, limit);

  const memberCache = new Map<number, GraphMember>();
  const member = (mi: number): GraphMember => {
    let gm = memberCache.get(mi);
    if (!gm) memberCache.set(mi, (gm = latestTerm(d.members[mi])));
    return gm;
  };
  const entities: GraphEntity[] = [];
  const links: [string, string, number][] = [];
  for (const e of top) {
    const id = ids[e];
    const info = d.entityById.get(id);
    const blocs: Record<string, number> = { Labor: 0, Coalition: 0, Crossbench: 0 };
    let items = 0;
    for (const [mi, n] of pairs.get(e)!) {
      const gm = member(mi);
      blocs[gm.bloc]++;
      items += n;
      links.push([gm.id, id, n]);
    }
    entities.push({
      id, name: info?.name ?? id.replace(/_/g, " "), type: info?.type ?? null, asx: info?.asx ?? null,
      page: info?.page ?? false, members: pairs.get(e)!.size, items, blocs, years: years.get(e) ?? null,
    });
  }
  const members = [...memberCache.values()].sort((a, b) => (a.id < b.id ? -1 : 1));
  return { entities, members, links };
}
