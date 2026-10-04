# Handover — public site (written 2026-10-04)

Read with: `SPEC.md` (ADRs, ACs, decisions log at the end), `BUILDLOG.md` (what each phase did,
measurements, deviations), `DESIGN.md` (validated tokens and colours), `docs/v2/web.md` (what each
page shows, the explorer, the data contract, rebuild steps). This file only holds what those
don't: current state, how to ship, and the next task.

## State

- **Live:** https://interests.kevinrassool.com (Workers static assets, Worker `aus-interests`,
  Kevin's personal Cloudflare account). Data files on R2 bucket `aus-interests-data` at
  https://data.kevinrassool.com/interests/{latest,v2.2026-10-02}/ (CORS + Range checked;
  Datasette Lite opens the DB from there).
- **Done:** phases A, B, C (explorer + network graph view + "everyday banking" toggle), and part of
  D (`web/wrangler.jsonc`, `web publish-data`). Everything is on `main` (last `5aa14a5`) and on
  `build/2026-10-03-public-site` (same commits; work in this worktree,
  `.claude/worktrees/cf-data-explorer-plan`, or branch fresh from `main`).
- **Tests:** `cd web && npm test` (35 Playwright, builds the mini site from the fixture),
  `.venv/bin/python -m pytest -q tests/web` (≈ 300). Full `pytest -q` has one environmental
  failure in a worktree without `.env.local` (`tests/test_entities.py::test_cli_missing_db`).
- GitHub Pages (`site/`, `pages.yml`) is still up as the old interim site; not yet a redirect.

## How to ship (Kevin is fine deploying to production and iterating; few visitors)

From the worktree root:
```
(cd web && npm ci && npm run build)
mv web/sites/production web/sites/superseded-$(date +%Y%m%d%H%M%S)   # rm -rf is blocked by a hook
.venv/bin/python -m disclosures web build --db site/disclosures_v2.db --manifest pdfs/manifest.csv \
  --out web/sites/production --mode production --media web/media
.venv/bin/python -m disclosures web check web/sites/production --db site/disclosures_v2.db
cd web && export CLOUDFLARE_API_TOKEN="$(sed -n 's/^CF_TOKEN=//p' ../.env.local)" \
  CLOUDFLARE_ACCOUNT_ID=d06d0928d1ce356f4b926b30efadc5ce
mv sites/og sites/superseded-og-$(date +%Y%m%d%H%M%S) 2>/dev/null
node scripts/og-cards.mjs sites/production sites/og      # ~60 s, 4,884 PNGs
node scripts/r2-upload.mjs sites/og                      # cards first: pages point at them
npx wrangler deploy
```
Cards live at `<data-base>og/<dataset version>.c<OG_CARD_VERSION>/`; a re-upload skips
unchanged objects. Bump `OG_CARD_VERSION` (`disclosures/web/build.py`) when the card design
changes. Photos and logos are committed in `web/media` (see `docs/v2/web.md`, "Photos, logos
and link previews"); a new member needs a row in `web/media/aph_ids.csv` and
`python scripts/fetch_member_photos.py --only <member_id>`.
(In the worktree `.venv` and `.env.local` live three levels up: `../../../.venv`,
`../../../../.env.local` from `web/`.) The token is `CF_TOKEN` in the repo-root `.env.local`
(personal account; Workers, R2, DNS, Zone read). Never print it. The default wrangler OAuth login
is the **work** (HIA) account: never deploy without the env vars. After a deploy, check with a
cache-busting query string: the edge served stale HTML for a minute once.
Data files: `web publish-data --out <dir>` stages them and writes `<dir>/upload.sh`; run it from
`web/` with the same env vars.

## Status 2026-10-04 (end of session): shipped, waiting on OpenAustralia Foundation

Kevin considers the site ready. On 2026-10-04 he sent it to Ben Fairless (CEO, OpenAustralia
Foundation: OpenAustralia, They Vote For You, Right to Know, Planning Alerts), who will consider
whether OAF publishes it on Kevin's behalf. Until there is an answer, hold the announcement
(Reddit draft) and the Zenodo DOI: if OAF publishes it, the domain, attribution, licence
wording, repo home and the HANDOFF deploy steps may all change. Everything is on `main`
(`fc57032`) and deployed; `web/sites/` holds only `production` (deployed) and `og` (cards).

## Done 2026-10-04: Open Graph cards, member photos, organisation logos

Shipped as decided with Kevin (SPEC decisions log 2026-10-04): APH portraits for all 408
members (CC BY-NC-ND, served byte for byte), 259 logos for the 340 entities with 5 or more
members (agent-collected from Commons / own websites, agent-checked; outcomes per entity in
`web/media/logo-review.json`), credits on the about page, a typographic card per page on R2.
Possible follow-ups: logos for entities with 3 or 4 members (353 more); a re-check of the 49
"none" results; Commons photos as a fallback for any member APH lacks (none today).

## Previous task brief (Kevin, 2026-10-04): Open Graph cards, and make the site more visual

1. **Open Graph link previews.** Pages already have `og:title`/description (`base.html`), no
   image. SPEC §7 Q4 proposed a generated card per member and entity (~5,000 small PNGs) vs one
   site-wide card. Kevin said yes to fixing Open Graph; settle per-page vs site-wide with him if
   cost matters (per-page is preferred). Constraints:
   - Platforms need PNG/JPEG (SVG is not accepted by most), 1200×630, `og:image` absolute URL,
     plus `twitter:card=summary_large_image`.
   - ADR-W2: the Python web build imports only Jinja2 + stdlib (a test blocks heavy modules), so
     rasterising belongs in `web/` (Node): e.g. Playwright screenshots of a card template, or a
     pinned SVG→PNG library. Look up the library's current docs; don't rely on memory.
   - Size: the site is ~204 MiB of 300 (ADR-W3 limit) and ~9,800 of 12,000 files; 5,000 PNGs at
     ~30–60 KB fit but check, and update `web check` limits only by SPEC decision.
   - Deterministic output (same inputs, same bytes) like the rest of the build.
2. **Member photos.** Kevin: "pull the images of each person". Use them on member pages, the
   members index and as graph nodes (canvas `drawImage` with a circular clip in
   `web/src/explore-graph.ts` `drawNode`, falling back to the bloc dot; keep the bloc colour as a
   ring so the legend still works).
   - **Check the licence before downloading anything.** APH publishes member photos on
     aph.gov.au; the registers themselves are CC BY-NC-ND 4.0, and the photo terms may differ.
     Wikimedia Commons / Wikidata (P18) photos carry per-file licences and are a likely clean
     source with attribution. Record source + licence + attribution per photo and show credit
     (About page and/or alt/figcaption).
   - Self-host at build time: AC-B9 / `web/tests/requests.spec.ts` fail on any off-origin
     request at view time. Fetching belongs in a separate step (like `publish-data`), never in
     `web build` (no network in `disclosures/web`, `test_web_guard`). Small WebP/JPEG (e.g.
     160 px), cached in the repo or R2, hashed names.
3. **Company/organisation logos.** For entities shown in the graph and on entity pages. Logos
   are trademarks: likely fine to show for identification, but pick a source with clear terms
   (e.g. Wikidata P154 / Commons, or the company's own site favicon) and record provenance. Only
   the entities that matter visually (graph candidates, entities with an entity page and many
   members), not 11k names. Same self-hosting and no-network-in-build rules as photos.
4. Keep: DESIGN.md tokens, axe clean in both themes, no horizontal scroll at 375 px, JS budget
   (explorer 94 KB + graph 64 KB of 250 KB gzip), honest labels (no editorialising: photos and
   logos identify, they don't characterise).

Suggest `/fable-plan` to Kevin first if the scope (sources, licences, per-page cards) needs
written acceptance criteria; it is multi-part.

## Backlog (agreed order, not started)

- **Rest of phase D:** `web.yml` (Actions deploy on push to `main`, `publish-data` when the DB
  changes; needs the token as repo secrets), `deploy.sh` gates (ADR-W11), GitHub Pages →
  redirect (`export --site`), Kaggle README / `pages_url` to the new domain.
- **Announce:** add a code `LICENSE` first (repo has none); Reddit draft from an earlier session.
- **Zenodo DOI:** worth it (free, citable, DataCite/Dataset Search). Connect the GitHub repo to
  Zenodo, cut a release, then rebuild with `web build --doi 10.5281/zenodo.N`.
- Phase E (SQL console, change feed), phase F (blog nav + `/data/` hub + draft post).
- Data: Senate before the 48th (scanned, ≈ US$18–25), typing 7,037 one-off entities, reused ASX
  tickers.

## Housekeeping

- An old orchestrator session (PID 24251) idles with this worktree as its cwd and holds the git
  worktree lock; Kevin may have closed it. Don't let two sessions edit the worktree.
- `web/.kv-explore.tmp.mjs` (untracked scratch from that session) and
  `web/sites/superseded-*` (old builds, gitignored, ~200 MB each) can be deleted by Kevin.
- Auto mode once blocked production deploy / R2 setup until Kevin asked explicitly; if a deploy
  is blocked, stop and ask rather than working around it.
