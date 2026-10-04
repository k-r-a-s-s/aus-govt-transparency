// Upload a folder tree to the R2 data bucket through the Cloudflare API, many files at once.
//
//   CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... \
//     node scripts/r2-upload.mjs <dir> [--bucket aus-interests-data] [--jobs 16] [--dry-run]
//
// Each file's key is its path under <dir> (og-cards.mjs writes interests/og/<version>/...).
// `wrangler r2 object put` starts one process per object, which is hours for ~5,000 Open Graph
// cards; this PUTs to /accounts/<id>/r2/buckets/<bucket>/objects/<key> with the same token.
// Objects already in the bucket with the same size and MD5 (ETag) are skipped, so a re-run
// only sends what changed. The token is read from the environment and never printed.
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const args = process.argv.slice(2);
const flag = (name, dflt) => {
  const i = args.indexOf(name);
  if (i < 0) return dflt;
  const v = args[i + 1];
  args.splice(i, 2);
  return v;
};
const dry = args.includes("--dry-run");
if (dry) args.splice(args.indexOf("--dry-run"), 1);
const bucket = flag("--bucket", "aus-interests-data");
const jobs = Number(flag("--jobs", "16"));
const [root] = args;
const token = process.env.CLOUDFLARE_API_TOKEN;
const account = process.env.CLOUDFLARE_ACCOUNT_ID;
if (!root || (!dry && (!token || !account))) {
  console.error("usage: CLOUDFLARE_API_TOKEN=.. CLOUDFLARE_ACCOUNT_ID=.. node scripts/r2-upload.mjs <dir> [--bucket B] [--jobs N] [--dry-run]");
  process.exit(2);
}
const TYPES = { ".png": "image/png", ".jpg": "image/jpeg", ".json": "application/json", ".txt": "text/plain" };
const walk = (d) => readdirSync(d, { withFileTypes: true }).flatMap((e) =>
  e.isDirectory() ? walk(join(d, e.name)) : e.isFile() ? [join(d, e.name)] : []);
const files = walk(root).sort();
const api = `https://api.cloudflare.com/client/v4/accounts/${account}/r2/buckets/${bucket}/objects/`;
const auth = { Authorization: `Bearer ${token}` };

async function existing(key) {
  // The objects endpoint answers a GET with the body; a HEAD is enough for size and ETag.
  const r = await fetch(api + encodeURI(key), { method: "HEAD", headers: auth });
  if (!r.ok) return null;
  return { size: Number(r.headers.get("content-length")), etag: (r.headers.get("etag") || "").replace(/"/g, "") };
}

let sent = 0, skipped = 0, failed = 0;
const queue = files.slice();
async function worker() {
  while (queue.length) {
    const f = queue.shift();
    const key = relative(root, f).split(sep).join("/");
    const body = readFileSync(f);
    const md5 = createHash("md5").update(body).digest("hex");
    if (dry) { sent++; continue; }
    const have = await existing(key).catch(() => null);
    if (have && have.size === body.length && have.etag === md5) { skipped++; continue; }
    const ext = key.slice(key.lastIndexOf("."));
    let ok = false;
    for (let i = 0; i < 4 && !ok; i++) {
      try {
        const r = await fetch(api + encodeURI(key), {
          method: "PUT", body,
          headers: { ...auth, "Content-Type": TYPES[ext] || "application/octet-stream" },
        });
        ok = r.ok;
        if (!ok && r.status !== 429 && r.status < 500) {
          console.error(`r2-upload: ${key}: HTTP ${r.status}`);
          break;
        }
      } catch { /* retry */ }
      if (!ok) await new Promise((res) => setTimeout(res, 1000 * (i + 1)));
    }
    ok ? sent++ : failed++;
    if ((sent + skipped) % 500 === 0) console.log(`r2-upload: ${sent + skipped}/${files.length}`);
  }
}
await Promise.all(Array.from({ length: Math.max(1, jobs) }, worker));
console.log(`r2-upload: ${sent} sent, ${skipped} unchanged, ${failed} failed (${files.length} files, bucket ${bucket}${dry ? ", dry run" : ""})`);
process.exit(failed ? 1 : 0);
