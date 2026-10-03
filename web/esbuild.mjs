// Bundle every entry in web/src/ (one ES module per .ts file at the top level) into web/dist/.
// Minified, no sourcemaps, deterministic: the same sources give the same bytes, which the
// Python build then copies into <site>/assets/ under a content hash.
import { build } from "esbuild";
import { readdirSync, rmSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "src");
const dist = join(here, "dist");

const entries = readdirSync(src)
  .filter((f) => f.endsWith(".ts") && !f.endsWith(".d.ts"))
  .sort()
  .map((f) => join(src, f));

rmSync(dist, { recursive: true, force: true });
mkdirSync(dist, { recursive: true });

await build({
  entryPoints: entries,
  outdir: dist,
  bundle: true,
  format: "esm",
  splitting: false,
  minify: true,
  sourcemap: false,
  target: ["es2020"],
  legalComments: "none",
  logLevel: "info",
});
