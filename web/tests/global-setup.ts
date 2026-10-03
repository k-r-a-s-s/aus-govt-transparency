// Build the mini site from the committed fixture and serve it for the browser tests.
//
// Python: $PYTHON if set, else <repo>/.venv/bin/python, else python3. It needs Jinja2 (the
// web build's only dependency). The server is `python -m http.server` (stdlib; serves
// index.html for directory URLs, which matches the Workers `auto-trailing-slash` handling
// for the pages we test). Mode is preview; SOURCE_DATE_EPOCH=0 pins the build time.
import { execFileSync, spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
export const REPO = resolve(here, "..", "..");

function python(): string {
  if (process.env.PYTHON) return process.env.PYTHON;
  const venv = join(REPO, ".venv", "bin", "python");
  return existsSync(venv) ? venv : "python3";
}

function freePort(): Promise<number> {
  return new Promise((ok, fail) => {
    const srv = createServer();
    srv.unref();
    srv.on("error", fail);
    srv.listen(0, "127.0.0.1", () => {
      const addr = srv.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      srv.close(() => ok(port));
    });
  });
}

async function waitFor(url: string, ms = 15000): Promise<void> {
  const until = Date.now() + ms;
  while (Date.now() < until) {
    try {
      const r = await fetch(url);
      if (r.ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error(`site server did not answer at ${url}`);
}

export default async function globalSetup(): Promise<() => Promise<void>> {
  const py = python();
  const tmp = mkdtempSync(join(tmpdir(), "aus-interests-site-"));
  const out = join(tmp, "site");
  execFileSync(
    py,
    [
      "-m", "disclosures", "web", "build",
      "--db", join(REPO, "tests", "fixtures", "web", "mini.db"),
      "--manifest", join(REPO, "tests", "fixtures", "web", "mini-manifest.csv"),
      "--out", out,
      "--mode", "preview",
    ],
    { cwd: REPO, env: { ...process.env, SOURCE_DATE_EPOCH: "0" }, stdio: "inherit" },
  );
  const port = await freePort();
  const server = spawn(py, ["-m", "http.server", String(port), "--bind", "127.0.0.1",
                            "--directory", out], { stdio: "ignore" });
  const url = `http://127.0.0.1:${port}`;
  await waitFor(`${url}/`);
  process.env.SITE_URL = url;
  process.env.SITE_DIR = out;
  return async () => {
    server.kill();
    rmSync(tmp, { recursive: true, force: true });
  };
}
