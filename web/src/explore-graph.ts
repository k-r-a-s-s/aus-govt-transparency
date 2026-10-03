// The explorer's network view (an addition to ADR-W7, SPEC decisions log 2026-10-03): a
// force-directed graph of members and the entities they declared, with a bar list of those
// entities split by bloc. Ported from the GitHub Pages explorer
// (disclosures/site_assets/explore.html): hovering a dot or a bar highlights its neighbours,
// a click pins a detail panel, and labels are de-overlapped after each frame.
//
// Its own bundle (force-graph is ~60 KB gzipped), imported by explore.ts only when a reader
// opens the view. It follows the explorer's selection: explore.ts calls update(rows).

import ForceGraph from "force-graph";
import { forceCollide } from "d3-force-3d";
import type { Data } from "./explore/data";
import { GRAPH_BLOCS, graphModel, type GraphEntity, type GraphMember, type GraphModel } from "./explore/graph-model";

export interface GraphHooks {
  /** Filter the explorer to one member or entity and show its items in the table. */
  showItems(filter: { member?: string; entity?: string }): void;
}
export interface GraphView {
  update(rows: Int32Array): void;
}

const BARS_SHOWN = 20;
const LABELLED = 6;
const fmt = (n: number): string => n.toLocaleString("en-AU");
const esc = (s: string): string =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
const typeLabel = (t: string | null): string => (t ? t.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) : "Type not assigned");
const yearsLabel = (y: [string, string] | null): string => (!y ? "" : y[0] === y[1] ? y[0] : `${y[0]} to ${y[1]}`);

interface Node {
  id: string;
  kind: "entity" | "member";
  label: string;
  r: number;
  rank: number;
  e?: GraphEntity;
  m?: GraphMember;
  x?: number;
  y?: number;
}
interface Link { source: string | Node; target: string | Node; n: number }

interface Colors {
  paper: string; ink: string; muted: string; rule: string; accent: string;
  link: string; linkHi: string; bloc: Record<string, string>;
}

function readColors(): Colors {
  const cs = getComputedStyle(document.documentElement);
  const v = (name: string, fallback: string) => cs.getPropertyValue(name).trim() || fallback;
  const rule = v("--rule", "#d2d3c8");
  const accent = v("--accent", "#176b50");
  return {
    paper: v("--paper", "#f6f5f0"), ink: v("--ink", "#24251f"), muted: v("--muted", "#626458"),
    rule, accent, link: alpha(v("--muted", "#626458"), 0.22), linkHi: alpha(accent, 0.8),
    bloc: {
      Labor: v("--bloc-labor", "#c0392b"), Coalition: v("--bloc-coalition", "#2a5db0"),
      Crossbench: v("--bloc-crossbench", "#a0730a"),
    },
  };
}

/** #rrggbb + alpha -> rgba(); anything else is returned unchanged. */
function alpha(hex: string, a: number): string {
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
  if (!m) return hex;
  return `rgba(${parseInt(m[1], 16)}, ${parseInt(m[2], 16)}, ${parseInt(m[3], 16)}, ${a})`;
}

const endId = (x: string | Node): string => (typeof x === "string" ? x : x.id);

export function createGraph(root: HTMLElement, d: Data, hooks: GraphHooks): GraphView {
  root.innerHTML = `
<p class="note" id="graph-sub"></p>
<div class="filter graph-find">
  <label for="graph-find">Find a member or entity in the graph</label>
  <input type="search" id="graph-find" list="graph-names" autocomplete="off">
  <datalist id="graph-names"></datalist>
</div>
<div class="graph-grid">
  <div class="graph-card">
    <div class="graph-canvas" id="graph-canvas" role="img" aria-label="Network graph of members and the entities they declared. The bar list and its table give the same figures."></div>
    <div class="graph-legend legend" id="graph-legend" aria-hidden="true"></div>
    <p class="graph-hint" aria-hidden="true">Scroll to zoom, drag to pan, click a dot for details</p>
    <aside class="graph-panel" id="graph-panel" aria-live="polite"></aside>
  </div>
  <section class="graph-bars" aria-labelledby="graph-bars-title">
    <h2 id="graph-bars-title">Declared by the most members</h2>
    <div class="legend" id="graph-bar-legend" aria-hidden="true"></div>
    <ol class="graph-bar-list" id="graph-bar-list"></ol>
    <details class="graph-table"><summary>Show as a table</summary><div class="table-wrap" id="graph-table"></div></details>
  </section>
</div>
<div class="graph-tip" id="graph-tip" role="tooltip"></div>`;
  const $ = <T extends HTMLElement>(id: string) => root.querySelector<T>(`#${id}`)!;
  const canvasEl = $("graph-canvas");
  const panel = $("graph-panel");
  const tip = $("graph-tip");
  const barList = $("graph-bar-list");
  const find = $<HTMLInputElement>("graph-find");

  let colors = readColors();
  let model: GraphModel = { entities: [], members: [], links: [] };
  let nodes: Node[] = [];
  let byId = new Map<string, Node>();
  let adj = new Map<string, Set<string>>();
  let hover: Node | null = null;
  let pinned: Node | null = null;
  let hi: Set<string> | null = null;
  let fitted = false;
  const blocColor = (b: string) => colors.bloc[b] ?? colors.muted;

  // --- tooltip ---------------------------------------------------------------------------------
  function showTip(html: string, x: number, y: number): void {
    tip.innerHTML = html;
    tip.classList.add("show");
    const r = tip.getBoundingClientRect();
    const pad = 14;
    let left = x + pad;
    let top = y + pad;
    if (left + r.width > innerWidth - 8) left = x - r.width - pad;
    if (top + r.height > innerHeight - 8) top = y - r.height - pad;
    tip.style.left = `${Math.max(8, left)}px`;
    tip.style.top = `${Math.max(8, top)}px`;
  }
  const hideTip = () => tip.classList.remove("show");
  const sw = (color: string, round = false) => `<i class="sw${round ? " round" : ""}" style="background:${color}"></i>`;

  function entityTip(e: GraphEntity): string {
    const kind = [typeLabel(e.type), e.asx ? `ASX: ${e.asx}` : ""].filter(Boolean).join(" · ");
    const years = yearsLabel(e.years);
    return `<b>${esc(e.name)}</b><div class="k">${esc(kind)}</div>
      <div class="tip-lead">${fmt(e.members)} member${e.members === 1 ? "" : "s"} declared it</div>
      ${GRAPH_BLOCS.map((b) => `<div class="row">${sw(blocColor(b))}${b}<span class="v">${fmt(e.blocs[b])}</span></div>`).join("")}
      <div class="k">${fmt(e.items)} item${e.items === 1 ? "" : "s"}${years ? ` · ${years}` : ""}</div>`;
  }
  function memberTip(m: GraphMember): string {
    const n = adj.get(`m:${m.id}`)?.size ?? 0;
    return `<b>${esc(m.name)}</b><div class="row">${sw(blocColor(m.bloc), true)}${esc(m.party || m.bloc)}</div>
      <div class="k">${m.chamber === "senate" ? "Senator" : "MP"}${m.seat ? ` for ${esc(m.seat)}` : ""} · parliaments ${m.parliaments.join(", ")}</div>
      <div class="tip-lead">${n} of these entities</div>`;
  }
  const nodeTip = (n: Node) => (n.kind === "entity" ? entityTip(n.e!) : memberTip(n.m!));

  // --- legends, bars, table --------------------------------------------------------------------
  function legends(): void {
    const blocs = GRAPH_BLOCS.map((b) => `<span>${sw(blocColor(b), true)}${b}</span>`).join("");
    $("graph-legend").innerHTML = `${blocs}<span>${sw(colors.muted, true)}Entity</span>`;
    $("graph-bar-legend").innerHTML = GRAPH_BLOCS.map((b) => `<span>${sw(blocColor(b))}${b}</span>`).join("");
  }

  function renderBars(): void {
    const top = model.entities.slice(0, BARS_SHOWN);
    const max = top[0]?.members || 1;
    barList.innerHTML = top.map((e, i) => {
      const segs = GRAPH_BLOCS.filter((b) => e.blocs[b] > 0).map((b) =>
        `<span class="seg" style="width:calc(${(e.blocs[b] / max) * 100}% - 2px);background:${blocColor(b)}"></span>`).join("");
      return `<li class="graph-bar" tabindex="0" data-i="${i}" aria-label="${esc(e.name)}: ${e.members} members">` +
        `<span class="name">${esc(e.name)}</span><span class="track">${segs}</span><span class="num">${fmt(e.members)}</span></li>`;
    }).join("");
    barList.querySelectorAll<HTMLElement>(".graph-bar").forEach((li) => {
      const e = top[Number(li.dataset.i)];
      const node = () => byId.get(`e:${e.id}`) ?? null;
      li.addEventListener("mousemove", (ev) => showTip(entityTip(e), ev.clientX, ev.clientY));
      li.addEventListener("mouseenter", () => { hover = node(); refresh(); });
      li.addEventListener("mouseleave", () => { hideTip(); hover = null; refresh(); });
      li.addEventListener("focus", () => { const r = li.getBoundingClientRect(); showTip(entityTip(e), r.right, r.top); hover = node(); refresh(); });
      li.addEventListener("blur", () => { hideTip(); hover = null; refresh(); });
      const pick = () => pin(node(), true);
      li.addEventListener("click", pick);
      li.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); pick(); } });
    });
    $("graph-table").innerHTML =
      `<table class="items"><caption>Entities in the graph, by members who declared them</caption><thead><tr><th scope="col">Entity</th><th scope="col" class="num">Members</th>` +
      GRAPH_BLOCS.map((b) => `<th scope="col" class="num">${b}</th>`).join("") +
      `<th scope="col" class="num">Items</th></tr></thead><tbody>` +
      model.entities.map((e) => `<tr><td>${esc(e.name)}</td><td class="num">${fmt(e.members)}</td>` +
        GRAPH_BLOCS.map((b) => `<td class="num">${fmt(e.blocs[b])}</td>`).join("") +
        `<td class="num">${fmt(e.items)}</td></tr>`).join("") + `</tbody></table>`;
  }

  // --- graph -----------------------------------------------------------------------------------
  const focusNode = () => hover ?? pinned;
  function refresh(): void {
    const n = focusNode();
    hi = n ? new Set([...(adj.get(n.id) ?? []), n.id]) : null;
    barList.querySelectorAll<HTMLElement>(".graph-bar").forEach((li) => {
      const e = model.entities[Number(li.dataset.i)];
      li.classList.toggle("active", !!pinned && pinned.id === `e:${e.id}`);
    });
  }
  const touchesFocus = (l: Link) => { const f = focusNode(); return !!f && (endId(l.source) === f.id || endId(l.target) === f.id); };

  function drawNode(n: Node, ctx: CanvasRenderingContext2D, k: number): void {
    ctx.globalAlpha = hi && !hi.has(n.id) ? 0.12 : 1;
    ctx.beginPath();
    ctx.arc(n.x!, n.y!, n.r, 0, 2 * Math.PI);
    ctx.fillStyle = n.kind === "entity" ? colors.muted : blocColor(n.m!.bloc);
    ctx.fill();
    if (focusNode()?.id === n.id) { ctx.lineWidth = 2 / k; ctx.strokeStyle = colors.accent; ctx.stroke(); }
    ctx.globalAlpha = 1;
  }

  // Labels after every frame: the focus first, then entities by rank, skipping any label
  // that would overlap one already placed.
  function drawLabels(ctx: CanvasRenderingContext2D, k: number): void {
    const focus = focusNode();
    const few = !!focus && (adj.get(focus.id)?.size ?? 0) <= 40;
    const wanted = (n: Node) => n.kind === "entity"
      ? (!hi || hi.has(n.id)) && (n.rank < LABELLED || k > 1.6 || !!hi)
      : (!!focus && (focus.id === n.id || (few && !!hi && hi.has(n.id)))) || (!hi && k > 3.2);
    const order = nodes.filter((n) => n.x !== undefined && wanted(n));
    if (focus) order.sort((a, b) => Number(b === focus) - Number(a === focus));
    const placed: number[][] = [];
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (const n of order) {
      const fs = (n.kind === "entity" ? 11 : 10) / k;
      ctx.font = `${n.kind === "entity" ? 600 : 400} ${fs}px "Atkinson Hyperlegible Next", system-ui, sans-serif`;
      const w = ctx.measureText(n.label).width;
      const y = n.y! + n.r + 2 / k;
      const box = [n.x! - w / 2, y, n.x! + w / 2, y + fs * 1.25];
      if (placed.some((b) => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1])) continue;
      placed.push(box);
      ctx.lineWidth = 3 / k;
      ctx.strokeStyle = colors.paper;
      ctx.strokeText(n.label, n.x!, y);
      ctx.fillStyle = n.kind === "entity" ? colors.ink : colors.muted;
      ctx.fillText(n.label, n.x!, y);
    }
  }

  const graph = new ForceGraph<Node, Link>(canvasEl)
    .backgroundColor(colors.paper)
    .autoPauseRedraw(false)
    .nodeId("id")
    .nodeLabel(() => "")
    .nodeCanvasObjectMode(() => "replace")
    .nodeCanvasObject(drawNode)
    .nodePointerAreaPaint((n, c, ctx) => { ctx.fillStyle = c; ctx.beginPath(); ctx.arc(n.x!, n.y!, n.r + 2, 0, 2 * Math.PI); ctx.fill(); })
    .linkColor((l) => (touchesFocus(l) ? colors.linkHi : colors.link))
    .linkWidth((l) => (touchesFocus(l) ? 1.2 : 0.5))
    .linkVisibility((l) => !hi || (hi.has(endId(l.source)) && hi.has(endId(l.target))))
    .onRenderFramePost(drawLabels)
    .cooldownTicks(300)
    .onEngineStop(() => {
      if (!fitted) { graph.zoomToFit(400, 40); fitted = true; }
      root.dataset.settled = "1";
    })
    .onNodeHover((n) => { hover = n ?? null; canvasEl.style.cursor = n ? "pointer" : "grab"; if (!n) hideTip(); refresh(); })
    .onNodeClick((n) => pin(n, false))
    .onBackgroundClick(() => { pinned = null; closePanel(); refresh(); });
  canvasEl.addEventListener("mousemove", (ev) => { if (hover) showTip(nodeTip(hover), ev.clientX, ev.clientY); });
  canvasEl.addEventListener("mouseleave", hideTip);
  const resize = () => { graph.width(canvasEl.clientWidth).height(canvasEl.clientHeight); };
  new ResizeObserver(resize).observe(canvasEl);
  resize();

  function buildGraph(): void {
    byId = new Map();
    adj = new Map();
    const ents: Node[] = model.entities.map((e, rank) => ({
      id: `e:${e.id}`, kind: "entity", label: e.name, rank, e, r: 3 + Math.sqrt(e.members) * 1.15,
    }));
    const mems: Node[] = model.members.map((m) => ({ id: `m:${m.id}`, kind: "member", label: m.name, rank: 0, m, r: 2.4 }));
    nodes = [...ents, ...mems];
    for (const n of nodes) { byId.set(n.id, n); adj.set(n.id, new Set()); }
    const links: Link[] = model.links.map(([m, e, n]) => {
      adj.get(`m:${m}`)!.add(`e:${e}`);
      adj.get(`e:${e}`)!.add(`m:${m}`);
      return { source: `m:${m}`, target: `e:${e}`, n };
    });
    $("graph-names").innerHTML = nodes.map((n) => `<option value="${esc(n.label)}">`).join("");
    hover = null;
    pinned = null;
    closePanel();
    fitted = false;
    root.dataset.settled = "0";
    graph.graphData({ nodes, links });
    graph.d3Force("charge")?.strength((n: Node) => (n.kind === "entity" ? -140 - n.e!.members * 1.2 : -26));
    graph.d3Force("link")?.distance(60).strength(0.12);
    graph.d3Force("collide", forceCollide((n: Node) => n.r + 3));
    refresh();
  }

  // --- pinning and the detail panel ------------------------------------------------------------
  function closePanel(): void { panel.classList.remove("open"); }

  function pin(n: Node | null, fromOutside: boolean): void {
    if (!n) return;
    pinned = n;
    hover = null;
    hideTip();
    refresh();
    openPanel(n);
    if (fromOutside && n.x !== undefined) {
      const k = Math.max(graph.zoom(), 1.8);
      const shift = panel.offsetWidth && panel.offsetWidth < canvasEl.clientWidth * 0.7 ? (panel.offsetWidth + 10) / 2 / k : 0;
      graph.zoom(k, 600);
      graph.centerAt(n.x + shift, n.y, 600);
    }
  }

  function openPanel(n: Node): void {
    const close = `<button type="button" class="graph-close" aria-label="Close details">&times;</button>`;
    if (n.kind === "entity") {
      const e = n.e!;
      const ms = model.links.filter((l) => l[1] === e.id).sort((a, b) => b[2] - a[2]);
      const name = new Map(model.members.map((m) => [m.id, m]));
      panel.innerHTML = `${close}<h3>${esc(e.name)}</h3>
        <p class="meta">${esc(typeLabel(e.type))}${e.asx ? ` · ASX: ${esc(e.asx)}` : ""}</p>
        <div class="stats"><div class="stat"><b>${fmt(e.members)}</b><span>members</span></div>
          <div class="stat"><b>${fmt(e.items)}</b><span>items</span></div>
          <div class="stat"><b>${esc(yearsLabel(e.years) || "not stated")}</b><span>lodged</span></div></div>
        <div class="legend">${GRAPH_BLOCS.map((b) => `<span>${sw(blocColor(b))}${b} ${fmt(e.blocs[b])}</span>`).join("")}</div>
        <p class="graph-links"><button type="button" class="linklike" data-show="entity">Show these items in the table</button>${e.page ? ` · <a href="/entities/${esc(e.id)}/">Entity page</a>` : ""}</p>
        <h4>Members (${ms.length}), by items in this selection</h4>
        <ol>${ms.map(([mid, , c]) => { const m = name.get(mid)!; return `<li data-id="m:${esc(mid)}" tabindex="0">${sw(blocColor(m.bloc), true)}${esc(m.name)}<span class="n">${c}</span></li>`; }).join("")}</ol>`;
      panel.querySelector<HTMLElement>("[data-show]")!.onclick = () => hooks.showItems({ entity: e.id });
    } else {
      const m = n.m!;
      const es = model.links.filter((l) => l[0] === m.id).sort((a, b) => b[2] - a[2]);
      const ent = new Map(model.entities.map((e) => [e.id, e]));
      panel.innerHTML = `${close}<h3>${esc(m.name)}</h3>
        <p class="meta">${sw(blocColor(m.bloc), true)} ${esc(m.party || m.bloc)} · ${m.chamber === "senate" ? "Senator" : "MP"}${m.seat ? ` for ${esc(m.seat)}` : ""}<br>Parliaments ${m.parliaments.join(", ")}</p>
        <p class="graph-links"><button type="button" class="linklike" data-show="member">Show their items in the table</button> · <a href="/members/${esc(m.id)}/">Member page</a></p>
        <h4>${es.length} of the entities here, by items</h4>
        <ol>${es.map(([, eid, c]) => `<li data-id="e:${esc(eid)}" tabindex="0">${sw(colors.muted, true)}${esc(ent.get(eid)!.name)}<span class="n">${c}</span></li>`).join("")}</ol>`;
      panel.querySelector<HTMLElement>("[data-show]")!.onclick = () => hooks.showItems({ member: m.id });
    }
    panel.classList.add("open");
    panel.scrollTop = 0;
    panel.querySelector<HTMLElement>(".graph-close")!.onclick = () => { pinned = null; closePanel(); refresh(); };
    panel.querySelectorAll<HTMLElement>("li[data-id]").forEach((li) => {
      const go = () => pin(byId.get(li.dataset.id!) ?? null, true);
      li.onclick = go;
      li.onkeydown = (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); go(); } };
      li.onmouseenter = () => { hover = byId.get(li.dataset.id!) ?? null; refresh(); };
      li.onmouseleave = () => { hover = null; refresh(); };
    });
  }

  find.addEventListener("change", () => {
    const t = find.value.trim().toLowerCase();
    if (!t) return;
    const n = nodes.find((x) => x.label.toLowerCase() === t) ?? nodes.find((x) => x.label.toLowerCase().includes(t));
    if (n) pin(n, true);
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    colors = readColors();
    graph.backgroundColor(colors.paper);
    legends();
    renderBars();
    refresh();
  });
  legends();

  return {
    update(rows: Int32Array): void {
      model = graphModel(d, rows);
      const shown = Math.min(model.entities.length, BARS_SHOWN);
      $("graph-sub").textContent = model.entities.length
        ? `The ${fmt(model.entities.length)} entities the most members declared in this selection, and the ${fmt(model.members.length)} members who declared them. ` +
          `Each dot is a member (coloured by bloc in their latest term) or an entity (grey); a line joins them when the member declared it. ` +
          `The list shows the top ${shown}.`
        : "No named entities in this selection.";
      root.dataset.entities = String(model.entities.length);
      root.dataset.members = String(model.members.length);
      root.dataset.links = String(model.links.length);
      renderBars();
      buildGraph();
    },
  };
}
