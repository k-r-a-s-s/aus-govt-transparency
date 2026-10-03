// The result table: the same columns, labels and links as the member page's items table
// (templates/_macros.html items_table with show_member), built from the decoded bundle.

import type { Data } from "./data";
import { CHANGE, OWNER, registerLabel } from "./filters";

export const PAGE = 200;

const esc = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export interface SenateLink { href: string; text: string }

/** ADR-W5 source link, by the document's URL class (mirrors disclosures/web/urls.py). */
export function sourceLink(urlClass: string, url: string, page: number, senate: SenateLink): [string, string] {
  if (urlClass === "house-pdf" || urlClass === "house-api") {
    return [`${url.replace(/#.*$/, "")}#page=${page}`, `page ${page}`];
  }
  if (urlClass === "house-redirect") return [url, `page ${page} of the PDF`];
  return [senate.href, senate.text];
}

export function lodged(d: Data, i: number): string {
  const li = d.col.lodged_date[i];
  if (li < 0) return "not stated";
  const date = d.dict.lodged_date[li];
  const pi = d.col.date_precision[i];
  return pi >= 0 && d.dict.date_precision[pi] === "month" ? date.slice(0, 7) : date;
}

export function dictValue(d: Data, column: string, i: number): string | null {
  const ix = d.col[column][i];
  return ix < 0 ? null : d.dict[column][ix];
}

export function rowHtml(d: Data, i: number, senate: SenateLink): string {
  const m = d.members[d.col.member[i]];
  const chamber = d.dict.chamber[d.col.chamber[i]];
  const parliament = d.col.parliament[i];
  const owner = dictValue(d, "owner", i) ?? "";
  const eid = dictValue(d, "entity", i);
  const e = eid ? d.entityById.get(eid) : undefined;
  const raw = dictValue(d, "entity_raw", i) ?? "";
  const entityCell = e && e.page
    ? `<a href="/entities/${esc(e.id)}/">${esc(e.name)}</a>`
    : esc(raw);
  const description = dictValue(d, "description", i) ?? "";
  const conf = dictValue(d, "confidence", i);
  const badge = conf && conf !== "high"
    ? ` <span class="badge badge-${esc(conf)}">${esc(conf)} confidence</span>` : "";
  const change = dictValue(d, "change_type", i) ?? "";
  const doc = d.documents[d.col.document[i]];
  const [href, text] = sourceLink(doc.url_class, doc.url, d.col.page[i], senate);
  return `<tr><td><a href="/members/${esc(m.id)}/">${esc(m.name)}</a></td>` +
    `<td class="nowrap">${esc(registerLabel(chamber, parliament))}</td>` +
    `<td>${esc(OWNER[owner] ?? owner)}</td>` +
    `<td class="entity">${entityCell}</td>` +
    `<td class="desc">${esc(description)}${badge}</td>` +
    `<td>${esc(CHANGE[change] ?? change)}</td>` +
    `<td class="nowrap">${esc(lodged(d, i))}</td>` +
    `<td class="nowrap"><a class="source" href="${esc(href)}">${esc(text)}</a></td></tr>`;
}

export const TABLE_HEAD =
  '<thead><tr><th scope="col">Member</th><th scope="col">Parliament</th><th scope="col">Owner</th>' +
  '<th scope="col">Entity</th><th scope="col">Description</th><th scope="col">Change</th>' +
  '<th scope="col">Lodged</th><th scope="col">Source</th></tr></thead>';

/** Render rows [from, to) of the selection into tbody (appending when from > 0). */
export function renderRows(tbody: HTMLTableSectionElement, d: Data, rows: Int32Array, from: number, to: number, senate: SenateLink): void {
  const parts: string[] = [];
  for (let k = from; k < Math.min(to, rows.length); k++) parts.push(rowHtml(d, rows[k], senate));
  if (from === 0) tbody.innerHTML = parts.join("");
  else tbody.insertAdjacentHTML("beforeend", parts.join(""));
}
