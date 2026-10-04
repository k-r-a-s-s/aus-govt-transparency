// Normalise collected organisation logos into web/media/logos and record them in media.json.
//
//   node scripts/import-logos.mjs <results.json> [--media media] [--size 160]
//
// <results.json> is the logo collection's output: a list of
// {entity_id, status, file, image_url, source_page, source_kind, licence, author, verdict, ...}
// (one per entity; collected by agents from Wikidata P154 / Wikimedia Commons or the
// organisation's own website, then checked by a second agent). Only status "found" with
// verdict "ok" is imported. Each file (SVG, PNG, JPEG, WebP or ICO) is drawn by Chromium into
// a canvas, trimmed of transparent or white margins, scaled to fit <size> px and saved as PNG
// (web/media/logos/<entity_id>.png). Wikimedia entries get their licence URL from the Commons
// API (network; this script is never part of `web build`). media.json's "logos" list is
// rewritten; its "photos" list is kept.
import { chromium } from "@playwright/test";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";

const args = process.argv.slice(2);
const flag = (name, dflt) => {
  const i = args.indexOf(name);
  if (i < 0) return dflt;
  const v = args[i + 1];
  args.splice(i, 2);
  return v;
};
const media = resolve(flag("--media", "media"));
const size = Number(flag("--size", "160"));
const [resultsPath] = args;
if (!resultsPath) {
  console.error("usage: node scripts/import-logos.mjs <results.json> [--media media] [--size 160]");
  process.exit(2);
}
const results = JSON.parse(readFileSync(resultsPath, "utf8"));
const todo = results.filter((r) => r.status === "found" && r.verdict === "ok" && r.file && existsSync(r.file));
const UA = "aus-interests-logos/1.0 (https://interests.kevinrassool.com)";
const strip = (s) => String(s || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();

// Licence URLs and attribution for the Commons files, 50 titles per API call.
const commons = new Map();
const titles = [...new Set(todo.filter((r) => r.source_kind === "wikimedia_commons")
  .map((r) => decodeURIComponent((r.source_page.match(/\/wiki\/(File:[^?#]+)/) || [])[1] || "").replace(/_/g, " "))
  .filter(Boolean))];
for (let i = 0; i < titles.length; i += 50) {
  const q = new URLSearchParams({ action: "query", format: "json", prop: "imageinfo", iiprop: "extmetadata", titles: titles.slice(i, i + 50).join("|") });
  const j = await (await fetch(`https://commons.wikimedia.org/w/api.php?${q}`, { headers: { "User-Agent": UA } })).json();
  for (const p of Object.values(j.query?.pages ?? {})) {
    const m = p.imageinfo?.[0]?.extmetadata ?? {};
    commons.set(p.title, { licence: strip(m.LicenseShortName?.value), licence_url: strip(m.LicenseUrl?.value), author: strip(m.Artist?.value) });
  }
}

const browser = await chromium.launch();
const page = await browser.newPage();
await page.setContent("<!doctype html><body></body>");
// Files go in as data: URLs (a file:// image would taint the canvas and block getImageData).
const MIME = { svg: "image/svg+xml", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg",
               webp: "image/webp", ico: "image/x-icon", gif: "image/gif" };
mkdirSync(join(media, "logos"), { recursive: true });
const today = new Date().toISOString().slice(0, 10);
const logos = [];
const failed = [];
for (const r of todo) {
  const ext = r.file.split(".").pop().toLowerCase();
  const src = `data:${MIME[ext] || "application/octet-stream"};base64,${readFileSync(r.file).toString("base64")}`;
  const isSvg = ext === "svg";
  const dataUrl = await page.evaluate(async ({ src, size, isSvg }) => {
    const img = new Image();
    img.src = src;
    try { await img.decode(); } catch { return null; }
    // SVGs without width/height report 0x0 (or 300x150): draw them big, then trim.
    let w = img.naturalWidth || 1024, h = img.naturalHeight || 1024;
    const big = 1024 / Math.max(w, h);
    if (isSvg || Math.max(w, h) < 1024) { w = Math.round(w * big); h = Math.round(h * big); }
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    const g = c.getContext("2d");
    g.drawImage(img, 0, 0, w, h);
    const px = g.getImageData(0, 0, w, h).data;
    let x0 = w, y0 = h, x1 = -1, y1 = -1;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      const ink = px[i + 3] > 12 && !(px[i] > 245 && px[i + 1] > 245 && px[i + 2] > 245);
      if (ink) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    }
    if (x1 < 0) return null;
    const tw = x1 - x0 + 1, th = y1 - y0 + 1;
    const sc = Math.min(size / tw, size / th);
    const o = document.createElement("canvas");
    o.width = Math.max(1, Math.round(tw * sc)); o.height = Math.max(1, Math.round(th * sc));
    const og = o.getContext("2d");
    og.imageSmoothingQuality = "high";
    og.drawImage(c, x0, y0, tw, th, 0, 0, o.width, o.height);
    return o.toDataURL("image/png");
  }, { src, size, isSvg });
  if (!dataUrl) { failed.push(r.entity_id); continue; }
  const png = Buffer.from(dataUrl.split(",")[1], "base64");
  const rel = `logos/${r.entity_id}.png`;
  writeFileSync(join(media, rel), png);
  const title = decodeURIComponent((r.source_page.match(/\/wiki\/(File:[^?#]+)/) || [])[1] || "").replace(/_/g, " ");
  const cm = commons.get(title);
  logos.push({
    entity_id: r.entity_id, file: rel, sha256: createHash("sha256").update(png).digest("hex"),
    source_url: r.image_url, source_page: r.source_page, source_kind: r.source_kind,
    licence: cm?.licence || r.licence, licence_url: cm?.licence_url || "",
    author: cm?.author || r.author, wikidata: r.wikidata_qid || "", retrieved: today,
    notes: r.notes || "",
  });
}
await browser.close();
const docPath = join(media, "media.json");
const doc = existsSync(docPath) ? JSON.parse(readFileSync(docPath, "utf8")) : { media_version: 1, photos: [], logos: [] };
doc.logos = logos.sort((a, b) => a.entity_id.localeCompare(b.entity_id));
// Same layout as scripts/fetch_member_photos.py writes (sorted keys, one-space indent).
const sortKeys = (v) => Array.isArray(v) ? v.map(sortKeys) : v && typeof v === "object"
  ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortKeys(v[k])])) : v;
writeFileSync(docPath, JSON.stringify(sortKeys(doc), null, 1) + "\n");
console.log(`import-logos: ${logos.length} logos -> ${join(media, "logos")}; ${failed.length} unreadable${failed.length ? ": " + failed.join(", ") : ""}`);
