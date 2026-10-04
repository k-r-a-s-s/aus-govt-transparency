// Render every page's Open Graph card (1200x630 PNG) from a built site's og-cards.json.
//
//   node scripts/og-cards.mjs <site-dir> <out-dir> [--only <path-prefix>] [--jobs 6]
//
// Writes <out-dir>/<R2 key> for each card, where the key is og_base's path plus the card's
// file (e.g. interests/og/v2.2026-10-02.c1/members/anthony_albanese.png), ready for
// scripts/r2-upload.mjs. Cards are typographic only: name, what it is, three counts and, for
// entities, members by bloc. No member photo (the APH portraits are CC BY-NC-ND, so they are
// not composited into new images) and no logo. Fonts are the site's own woff2 files; the
// same Chromium (pinned by @playwright/test) gives the same bytes for the same inputs.
import { chromium } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const flag = (name, dflt) => {
  const i = args.indexOf(name);
  if (i < 0) return dflt;
  const v = args[i + 1];
  args.splice(i, 2);
  return v;
};
const only = flag("--only", "");
const jobs = Number(flag("--jobs", "6"));
const [siteArg, outArg] = args;
if (!siteArg || !outArg) {
  console.error("usage: node scripts/og-cards.mjs <site-dir> <out-dir> [--only <path-prefix>] [--jobs N]");
  process.exit(2);
}
const site = resolve(siteArg);
const out = resolve(outArg);
const spec = JSON.parse(readFileSync(join(site, "og-cards.json"), "utf8"));
const prefix = new URL(spec.og_base).pathname.replace(/^\//, "");
const cards = spec.cards.filter((c) => c.path.startsWith(only));

// Light-theme tokens from DESIGN.md / style.css.
const BLOC = { Labor: "#c0392b", Coalition: "#2a5db0", Crossbench: "#a0730a", Unknown: "#8a8c80" };
const font = (f) => pathToFileURL(join(site, "fonts", f)).href;
const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: "Young Serif"; src: url(${font("young-serif-latin.woff2")}) format("woff2"); unicode-range: U+0000-00FF, U+2000-206F; }
@font-face { font-family: "Young Serif"; src: url(${font("young-serif-latin-ext.woff2")}) format("woff2"); unicode-range: U+0100-02FF, U+1E00-1EFF; }
@font-face { font-family: "Atkinson"; font-weight: 200 800; src: url(${font("atkinson-hyperlegible-next-latin.woff2")}) format("woff2"); unicode-range: U+0000-00FF, U+2000-206F; }
@font-face { font-family: "Atkinson"; font-weight: 200 800; src: url(${font("atkinson-hyperlegible-next-latin-ext.woff2")}) format("woff2"); unicode-range: U+0100-02FF, U+1E00-1EFF; }
@font-face { font-family: "Mono"; src: url(${font("jetbrains-mono-latin.woff2")}) format("woff2"); }
* { box-sizing: border-box; margin: 0; }
html, body { width: 1200px; height: 630px; overflow: hidden; }
body { background: #f6f5f0; color: #24251f; font-family: "Atkinson", Verdana, sans-serif; }
.card { position: relative; width: 1200px; height: 630px; padding: 52px 72px 44px 88px; display: flex; flex-direction: column; }
.card > * { flex-shrink: 0; }
.card > .spacer { flex: 1 1 0; min-height: 12px; }
.stripe { position: absolute; left: 0; top: 0; bottom: 0; width: 16px; background: #176b50; }
.eyebrow { font-family: "Mono", monospace; font-size: 24px; letter-spacing: 0.04em; text-transform: uppercase; color: #626458; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
h1 { font-family: "Young Serif", Georgia, serif; font-weight: 400; color: #176b50; letter-spacing: -0.02em; line-height: 1.05; margin-top: 16px; }
.sub { margin-top: 18px; font-size: 30px; line-height: 1.3; color: #24251f; max-height: 2.6em; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.stats { display: flex; gap: 64px; align-items: flex-end; }
.stat b { display: block; font-family: "Young Serif", Georgia, serif; font-weight: 400; font-size: 64px; line-height: 1; color: #24251f; }
.stat span { display: block; margin-top: 8px; font-size: 24px; color: #626458; }
.bar { margin-top: 28px; }
.bar .track { display: flex; gap: 3px; height: 22px; }
.bar .track i { display: block; height: 100%; border-radius: 3px; }
.bar .legend { display: flex; gap: 28px; margin-top: 10px; font-size: 22px; color: #626458; }
.bar .legend em { font-style: normal; display: inline-block; width: 14px; height: 14px; border-radius: 3px; margin-right: 8px; vertical-align: -1px; }
.foot { display: flex; justify-content: space-between; align-items: baseline; margin-top: 28px; padding-top: 18px; border-top: 2px solid #d2d3c8; font-size: 24px; color: #626458; }
.foot .mark { font-family: "Young Serif", Georgia, serif; font-size: 34px; color: #24251f; }
.foot .mark span { color: #f2c42b; }
</style></head><body><div class="card" id="card"></div>
<script>
const BLOC = ${JSON.stringify(BLOC)};
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
window.renderCard = (c) => {
  const el = document.getElementById("card");
  const bar = c.bar && c.bar.length ? (() => {
    const total = c.bar.reduce((a, b) => a + b.value, 0) || 1;
    return '<div class="bar"><div class="track">' +
      c.bar.map((b) => '<i style="flex:' + b.value / total + ';background:' + (BLOC[b.bloc] || BLOC.Unknown) + '"></i>').join("") +
      '</div><div class="legend"><span>Members by bloc at the start of the term:</span>' +
      c.bar.map((b) => '<span><em style="background:' + (BLOC[b.bloc] || BLOC.Unknown) + '"></em>' + esc(b.label) + " " + b.value.toLocaleString("en-AU") + "</span>").join("") +
      "</div></div>";
  })() : "";
  el.innerHTML =
    '<div class="stripe"' + (c.accent && BLOC[c.accent] ? ' style="background:' + BLOC[c.accent] + '"' : "") + "></div>" +
    '<p class="eyebrow">' + esc(c.eyebrow) + "</p>" +
    "<h1>" + esc(c.title) + "</h1>" +
    '<p class="sub">' + esc(c.subtitle) + "</p>" +
    '<div class="spacer"></div>' +
    '<div class="stats">' + c.stats.map((s) => '<div class="stat"><b>' + esc(s[0]) + "</b><span>" + esc(s[1]) + "</span></div>").join("") + "</div>" +
    bar +
    '<div class="foot"><span class="mark">kr<span>.</span> Registers of Interests</span><span>interests.kevinrassool.com</span></div>';
  // Largest title size (96 down to 40 px) that fits in two lines with the whole card inside
  // 630 px; the subtitle drops to one line before the title goes below 56 px.
  const h1 = el.querySelector("h1");
  const sub = el.querySelector(".sub");
  for (let px = 96; px >= 40; px -= 4) {
    h1.style.fontSize = px + "px";
    sub.style.webkitLineClamp = px < 72 ? "1" : "2";
    const fits = h1.offsetHeight <= Math.ceil(px * 1.05 * 2) + 4 && h1.scrollWidth <= h1.clientWidth;
    if (fits && el.scrollHeight <= 630) break;
  }
};
</script></body></html>`;

const tmp = mkdtempSync(join(tmpdir(), "og-cards-"));
const tpl = join(tmp, "card.html");
writeFileSync(tpl, html);

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1, colorScheme: "light" });
let done = 0;
const t0 = Date.now();
const queue = cards.slice();
async function worker() {
  const page = await ctx.newPage();
  await page.goto(pathToFileURL(tpl).href);
  // Load every face before the first measurement: fonts otherwise load lazily on first use,
  // and the title would be fitted with the fallback font.
  await page.evaluate(() => Promise.all([...document.fonts].map((f) => f.load())));
  while (queue.length) {
    const c = queue.shift();
    await page.evaluate((card) => window.renderCard(card), c);
    await page.evaluate(() => document.fonts.ready);
    const dest = join(out, prefix, c.file);
    mkdirSync(dirname(dest), { recursive: true });
    await page.screenshot({ path: dest, type: "png", clip: { x: 0, y: 0, width: 1200, height: 630 } });
    if (++done % 500 === 0) console.log(`og-cards: ${done}/${cards.length} (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
  }
  await page.close();
}
await Promise.all(Array.from({ length: Math.max(1, jobs) }, worker));
await browser.close();
console.log(`og-cards: ${done} cards -> ${join(out, prefix)} in ${((Date.now() - t0) / 1000).toFixed(0)} s`);
