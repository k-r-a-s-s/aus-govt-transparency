// The explorer at /explore/ (ADR-W7): filters with facet counts, a result table, three charts,
// CSV of the selection and the state in the URL; plus a network graph view (SPEC decisions log
// 2026-10-03) in its own bundle, imported from data-graph-src the first time it is opened. Progressive enhancement over the static page:
// without JavaScript the counts tables stay; with it this module hides them and mounts on
// <div id="explorer" data-base="/data/" data-senate-href data-senate-text data-graph-src>.
//
// Filtering runs on the main thread: 50,936 rows filter and re-count in a few milliseconds
// (measured in BUILDLOG), so no Web Worker is needed.

import { loadData, type Data } from "./explore/data";
import {
  FACET_KEYS, type Facet, type FacetKey, type State, displayOrder, isEmpty, makeFacets, select,
  stateFromUrl, stateToSearch,
} from "./explore/filters";
import { PAGE, TABLE_HEAD, renderRows, type SenateLink } from "./explore/table";
import { membersByParliament, sectionByBloc, topEntities } from "./explore/charts";
import { buildCsv, download, loadExtra } from "./explore/csv";
import type { GraphView } from "./explore-graph";

const fmt = (n: number): string => n.toLocaleString("en-AU");
const el = <K extends keyof HTMLElementTagNameMap>(tag: K, attrs: Record<string, string> = {}, text?: string): HTMLElementTagNameMap[K] => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text;
  return e;
};

function facetBlock(f: Facet, state: State, onChange: () => void): { root: HTMLElement; update: (counts: Int32Array) => void } {
  const root = el("fieldset", { class: "facet", "data-facet": f.key });
  root.appendChild(el("legend", {}, f.title));
  const list = el("div", { class: "facet-options" });
  root.appendChild(list);
  const countEls: HTMLElement[] = [];
  const boxes: HTMLInputElement[] = [];
  f.values.forEach((v, i) => {
    const id = `f-${f.key}-${i}`;
    const label = el("label", { for: id, class: "facet-option" });
    const box = el("input", { type: "checkbox", id, name: f.key, value: v });
    if (state.facets[f.key as FacetKey].has(v)) box.checked = true;
    box.addEventListener("change", () => {
      const sel = state.facets[f.key as FacetKey];
      if (box.checked) sel.add(v); else sel.delete(v);
      onChange();
    });
    const count = el("span", { class: "facet-count" }, "");
    label.append(box, el("span", { class: "facet-label" }, f.labels[i]), count);
    list.appendChild(label);
    countEls.push(count);
    boxes.push(box);
  });
  return {
    root,
    update(counts: Int32Array) {
      counts.forEach((c, i) => {
        countEls[i].textContent = fmt(c);
        boxes[i].parentElement!.classList.toggle("is-zero", c === 0 && !boxes[i].checked);
      });
    },
  };
}

async function main(mount: HTMLElement): Promise<void> {
  const base = mount.dataset.base ?? "/data/";
  const senate: SenateLink = { href: mount.dataset.senateHref ?? "#", text: mount.dataset.senateText ?? "Senate register" };
  const status = el("p", { class: "note", role: "status" }, "Loading the items…");
  mount.hidden = false;
  mount.replaceChildren(status);

  let data: Data;
  try {
    data = await loadData(base);
  } catch (err) {
    status.textContent = `The explorer could not load its data (${(err as Error).message}). The counts below and the member and entity pages still work.`;
    return;
  }
  const facets = makeFacets(data);
  const order = displayOrder(data);
  const state = stateFromUrl(location.search);
  document.getElementById("explore-static")?.setAttribute("hidden", "");

  // --- layout ---
  const layout = el("div", { class: "explorer" });
  const rail = el("form", { class: "explorer-rail", "aria-label": "Filters" });
  rail.addEventListener("submit", (e) => e.preventDefault());
  const results = el("div", { class: "explorer-results" });
  layout.append(rail, results);

  const qWrap = el("div", { class: "filter" });
  const qLabel = el("label", { for: "explore-q" }, "Search member, entity or description");
  const qInput = el("input", { type: "search", id: "explore-q", name: "q", autocomplete: "off", placeholder: "e.g. qantas" });
  qInput.value = state.q;
  qWrap.append(qLabel, qInput);
  rail.appendChild(qWrap);

  const chips = el("div", { class: "chips" });
  rail.appendChild(chips);

  const blocks = FACET_KEYS.map((k) => facetBlock(facets[k], state, () => update(true)));
  for (const b of blocks) rail.appendChild(b.root);
  const clear = el("button", { type: "button", class: "button" }, "Clear all filters");
  rail.appendChild(clear);

  const countLine = el("p", { class: "count-line", role: "status", "aria-live": "polite" });
  const actions = el("div", { class: "explorer-actions" });
  const csvBtn = el("button", { type: "button", class: "button" }, "Download CSV of this selection");
  const shareNote = el("span", { class: "note" }, "The address bar holds this view; copy it to share.");
  actions.append(csvBtn, shareNote);
  const graphSrc = mount.dataset.graphSrc ?? "";
  const viewSwitch = el("div", { class: "view-switch", role: "group", "aria-label": "View" });
  const viewBtns = {
    table: el("button", { type: "button", "data-view": "table" }, "Table and charts"),
    graph: el("button", { type: "button", "data-view": "graph" }, "Network graph"),
  };
  viewSwitch.append(viewBtns.table, viewBtns.graph);
  if (!graphSrc) viewSwitch.hidden = true;
  const graphRoot = el("div", { class: "graph-view", id: "explore-graph" });
  graphRoot.hidden = true;
  const chartsWrap = el("div", { class: "explorer-charts" });
  const chartEls = [
    ["Items per section, by bloc", el("div", { class: "explorer-chart", id: "chart-section-bloc" })],
    ["Distinct members per register", el("div", { class: "explorer-chart", id: "chart-members" })],
    ["Entities named most often", el("div", { class: "explorer-chart", id: "chart-entities" })],
  ] as const;
  for (const [title, c] of chartEls) {
    const fig = el("figure", { class: "chart-figure explorer-figure" });
    fig.append(c, el("figcaption", {}, title));
    chartsWrap.appendChild(fig);
  }
  const honest = el("p", { class: "note" },
    "Counts are counts of declared items, not of their value. Transcription errors of roughly 1 to 2% exist; confidence is shown per item. Party and bloc are as at the start of each term.");
  const wrap = el("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": "Items in the selection" });
  const table = el("table", { class: "items", id: "explore-table" });
  table.innerHTML = `<caption id="explore-caption"></caption>${TABLE_HEAD}<tbody></tbody>`;
  wrap.appendChild(table);
  const more = el("button", { type: "button", class: "button", id: "explore-more" }, "Show more");
  results.append(countLine, actions, viewSwitch, honest, chartsWrap, wrap, more, graphRoot);
  mount.replaceChildren(layout);

  const tbody = table.tBodies[0];
  const caption = table.caption!;
  let rows: Int32Array = new Int32Array(0);
  let shown = 0;
  // Charts and graph are drawn only while visible (a hidden chart has no width), and redrawn
  // when shown if the selection changed meanwhile.
  let chartsStale = true;
  let graphStale = true;
  let graph: GraphView | null = null;
  let graphLoading: Promise<GraphView | null> | null = null;

  function loadGraph(): Promise<GraphView | null> {
    if (!graphLoading) {
      graphRoot.replaceChildren(el("p", { class: "note", role: "status" }, "Loading the graph…"));
      graphLoading = (import(graphSrc) as Promise<typeof import("./explore-graph")>).then((mod) => {
        graph = mod.createGraph(graphRoot, data, { showItems });
        return graph;
      }).catch((err: Error) => {
        graphRoot.replaceChildren(el("p", { class: "note", role: "status" }, `The graph could not load (${err.message}). The table and charts still work.`));
        graphLoading = null;
        return null;
      });
    }
    return graphLoading;
  }

  function drawVisible(): void {
    if (state.view === "table" && chartsStale) {
      sectionByBloc(chartEls[0][1], data, rows);
      membersByParliament(chartEls[1][1], data, rows);
      topEntities(chartEls[2][1], data, rows);
      chartsStale = false;
    }
    if (state.view === "graph" && graphStale) {
      void loadGraph().then((g) => {
        if (!g || state.view !== "graph" || !graphStale) return;
        g.update(rows);
        graphStale = false;
        mount.dataset.graphReady = "1";
      });
    }
  }

  function applyView(): void {
    const isGraph = state.view === "graph";
    viewBtns.table.setAttribute("aria-pressed", String(!isGraph));
    viewBtns.graph.setAttribute("aria-pressed", String(isGraph));
    chartsWrap.hidden = isGraph;
    wrap.hidden = isGraph;
    more.hidden = isGraph || shown >= rows.length;
    graphRoot.hidden = !isGraph;
    mount.dataset.view = state.view;
    drawVisible();
  }

  function setView(v: "table" | "graph"): void {
    if (state.view === v) return;
    state.view = v;
    history.replaceState(null, "", `${location.pathname}${stateToSearch(state)}`);
    applyView();
  }
  viewBtns.table.addEventListener("click", () => setView("table"));
  viewBtns.graph.addEventListener("click", () => setView("graph"));

  /** From the graph's detail panel: filter to one member or entity and show the table. */
  function showItems(f: { member?: string; entity?: string }): void {
    if (f.member) state.member = f.member;
    if (f.entity) state.entity = f.entity;
    state.view = "table";
    update(true);
    countLine.scrollIntoView({ block: "start" });
  }

  function renderChips(): void {
    chips.replaceChildren();
    const add = (text: string, onRemove: () => void) => {
      const chip = el("button", { type: "button", class: "chip" }, `${text} ×`);
      chip.setAttribute("aria-label", `Remove filter: ${text}`);
      chip.addEventListener("click", () => { onRemove(); update(true); });
      chips.appendChild(chip);
    };
    if (state.member) {
      const m = data.members.find((x) => x.id === state.member);
      add(`Member: ${m?.name ?? state.member}`, () => { state.member = null; });
    }
    if (state.entity) {
      const e = data.entityById.get(state.entity);
      add(`Entity: ${e?.name ?? state.entity}`, () => { state.entity = null; });
    }
  }

  function showMore(): void {
    const next = Math.min(shown + PAGE, rows.length);
    renderRows(tbody, data, rows, shown, next, senate);
    shown = next;
    more.hidden = shown >= rows.length;
    more.textContent = `Show ${fmt(Math.min(PAGE, rows.length - shown))} more (${fmt(shown)} of ${fmt(rows.length)} shown)`;
  }

  function update(pushUrl: boolean): void {
    const t0 = performance.now();
    const sel = select(data, facets, state, order);
    rows = sel.rows;
    blocks.forEach((b, i) => b.update(sel.counts[FACET_KEYS[i]]));
    renderChips();
    const all = isEmpty(state);
    countLine.textContent = all
      ? `All ${fmt(rows.length)} declared items.`
      : `${fmt(rows.length)} of ${fmt(data.n)} declared items match.`;
    caption.textContent = `Items in the selection (${fmt(rows.length)})`;
    shown = 0;
    showMore();
    chartsStale = true;
    graphStale = true;
    applyView();
    csvBtn.disabled = rows.length === 0;
    if (pushUrl) history.replaceState(null, "", `${location.pathname}${stateToSearch(state)}`);
    mount.dataset.filterMs = (performance.now() - t0).toFixed(1);
    mount.dataset.count = String(rows.length);
  }

  let qTimer = 0;
  qInput.addEventListener("input", () => {
    window.clearTimeout(qTimer);
    qTimer = window.setTimeout(() => { state.q = qInput.value.trim(); update(true); }, 150);
  });
  clear.addEventListener("click", () => {
    for (const k of FACET_KEYS) state.facets[k].clear();
    state.q = ""; state.member = null; state.entity = null;
    qInput.value = "";
    rail.querySelectorAll<HTMLInputElement>("input[type=checkbox]").forEach((b) => { b.checked = false; });
    update(true);
  });
  more.addEventListener("click", showMore);
  csvBtn.addEventListener("click", async () => {
    csvBtn.disabled = true;
    const label = csvBtn.textContent;
    csvBtn.textContent = "Preparing CSV…";
    try {
      const extra = await loadExtra(base);
      download(buildCsv(data, extra, rows), `interests-selection-${rows.length}.csv`);
    } catch (err) {
      countLine.textContent = `CSV download failed: ${(err as Error).message}`;
    } finally {
      csvBtn.textContent = label;
      csvBtn.disabled = rows.length === 0;
    }
  });
  window.addEventListener("popstate", () => {
    const s = stateFromUrl(location.search);
    for (const k of FACET_KEYS) state.facets[k] = s.facets[k];
    state.q = s.q; state.member = s.member; state.entity = s.entity; state.view = s.view;
    qInput.value = state.q;
    rail.querySelectorAll<HTMLInputElement>("input[type=checkbox]").forEach((b) => {
      b.checked = state.facets[b.name as FacetKey].has(b.value);
    });
    update(false);
  });

  // Plot reads the colour tokens when it draws, so redraw on a light/dark switch
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { chartsStale = true; drawVisible(); });

  update(false);
  mount.dataset.ready = "1";
}

const mountEl = document.getElementById("explorer");
if (mountEl) void main(mountEl);
