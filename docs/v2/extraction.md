# Extraction (Phase 2, ADR-5)

Two extractors write the same ADR-2 contract (`schema/extraction.schema.json`), one file per PDF
at `extractions/<source_id>/<chamber>/<parliament>/<pdf_stem>.json`. Both use the same
instructions, `disclosures/prompts/extract.md`. Check any output with
`python -m disclosures validate extractions/<source_id>` and score it with
`python -m disclosures score --pred extractions/<source_id> --gold eval/gold`.

**Prompt versions.** The header line of `extract.md` carries the version. v0 (conventions
C1–C11) produced the Phase 2 backfill. v1 (2026-10-02) adds C12, which itemises "see attached"
lists bound into the PDF, and checklist item 7. Only the files confirmed in
`eval/attachment_gaps.md` are re-extracted on v1; the rest of the corpus stays on v0, since C12
changes nothing but attachment handling.

| Arm | `source_id` | Runs as | Who can run it |
|---|---|---|---|
| A | `workflow-claude` | Claude Code Workflow `.claude/workflows/extract-disclosures.js` | the orchestrating Claude Code session or Kevin (implementer subagents cannot invoke Workflow) |
| B | `gemini-api` | `python -m disclosures extract --source gemini ...` | anyone with an OpenRouter key (`--provider openrouter`, default when `OPENROUTER_KEY` is set) or a funded Gemini API key (`--provider gemini`) |
| B′ | `openrouter-<model>` | the same command with a non-Gemini `--model` (bake-off arms only, e.g. `openai/gpt-6-luna`, `anthropic/claude-sonnet-5.5`) | anyone with an OpenRouter key |

## Arm B: Gemini API (`gemini-api`)

The extractor has two transports, chosen with `--provider`. Everything above the transport
(chunking, re-split, page offsets, merge, validation) is shared and lives in
`disclosures/extract_gemini.py`; the transports are `GenaiBackend` (same file) and
`disclosures/openrouter.py`.

| `--provider` | Talks to | Key (`.env.local`) | Models |
|---|---|---|---|
| `openrouter` | `POST https://openrouter.ai/api/v1/chat/completions` (OpenAI-compatible) | `OPENROUTER_KEY` | any OpenRouter id with native `file` input: `google/gemini-3.8-flash` (default), `openai/gpt-6-luna`, `anthropic/claude-sonnet-5.5`, ... |
| `gemini` | AI Studio through the `google-genai` SDK | `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) | Gemini ids only |
| `auto` (default) | `openrouter` if `OPENROUTER_KEY` is set, else `gemini` | | |

### Setup
- `.env.local` at the repo root (gitignored; never commit or print it):
  - `OPENROUTER_KEY`: the OpenRouter key (added 2026-10-02). Check the balance with
    `curl -H "Authorization: Bearer $OPENROUTER_KEY" https://openrouter.ai/api/v1/credits`.
  - `GOOGLE_API_KEY` (or `GEMINI_API_KEY`): only for `--provider gemini`. **The project's AI
    Studio credits are depleted (402 since 2026-10-01); use OpenRouter.**
  - `GEMINI_MODEL`: optional. Defaults to `gemini-3.8-flash`.
- The CLI loads `.env.local` with `override=False`, so real environment variables win.
  Model precedence: `--model` > `GEMINI_MODEL` > default. Every Gemini id, bare or
  `google/`-prefixed, goes through `disclosures.gemini_model.resolve_gemini_model()`, which
  strips a `models/` prefix and **rejects any Gemini 0.x/1.x/2.x id** (regex
  `^gemini-[0-2]\.`), whatever its source. Non-Gemini OpenRouter ids pass through unchanged
  (they must be `<vendor>/<model>`).
- Missing key, banned model, bad `--workers` or `--batch`: the command exits 2 with a one-line
  message.

### Usage
```sh
python -m disclosures extract --source gemini [--provider auto|gemini|openrouter] [--model ID] \
    [--provider-order google-ai-studio/flex] [--fallback-model ID] [--reasoning-effort low|medium|high] \
    [--ignore-providers azure] \
    [--source-id gemini-api] [--out-root extractions/<source-id>] [--chunk-pages 20] \
    [--max-retries 4] [--workers 1] [--force] pdfs/45/husice_45p.pdf pdfs/47/kingm_47p.pdf ...

# the 12 gold PDFs, Gemini 3.8 Flash on OpenRouter's half-price flex endpoints, Sonnet 5.5 as the
# fallback for chunks Gemini refuses, 4 PDFs at a time. NB zsh does not word-split $GOLD: use ${=GOLD}
# in zsh, or inline the $(...) as below.
python -m disclosures extract --source gemini --provider openrouter --model google/gemini-3.8-flash \
    --provider-order google-ai-studio/flex --fallback-model anthropic/claude-sonnet-5.5 --workers 4 \
    $(.venv/bin/python -c "import json;print(' '.join(p['pdf_path'] for p in json.load(open('eval/gold/selection.json'))['pdfs']))")
python -m disclosures validate extractions/gemini-api

# a bake-off arm on another vendor's model (lands in extractions/openrouter-gpt-6-luna/):
python -m disclosures extract --source gemini --provider openrouter --model openai/gpt-6-luna --workers 4 $GOLD
python -m disclosures score --pred extractions/openrouter-gpt-6-luna --gold eval/gold
```
Each PDF prints one line (`ok`, `skip` or `FAILED`), with its cost when the provider reports
one. The run ends with `N ok, M failed, K skipped`, token totals, the cost (reported by
OpenRouter, or estimated from the Gemini price table on the `gemini` transport) and a
`Failed PDFs:` list. The exit code is 1 if any PDF failed and 0 otherwise. A PDF whose output
already exists and validates is skipped unless `--force` is given, so a backfill can be
re-run until clean. `--workers N` extracts N PDFs at once (threads); the summary is the same.

- **`--fallback-model ID` (OpenRouter only):** a second model used for a *chunk* that the
  primary model refuses with a content block (Gemini `RECITATION`/`SAFETY`, OpenRouter
  `content_filter`/`error`). Re-splitting does not clear these (morrison_47p page 23, a typed
  travel notice, is blocked even as a 1-page chunk), so without a fallback the PDF fails. With
  one, only that chunk goes to the fallback model; the file's `model` becomes
  `primary+fallback` (e.g. `google/gemini-3.8-flash+anthropic/claude-sonnet-5.5`) and
  `extraction_notes` records `pages S-E: fallback <model> after primary <model> returned
  finish_reason ERROR (RECITATION)`. A `MAX_TOKENS` on the fallback is not re-split (the PDF
  fails). The blocked call's tokens and cost are still counted. On the gold set 1 of 12 PDFs
  (1 of 18 chunks) needed it; in the full backfill 108 of 768 files (14%) did, mostly scanned
  43rd–45th-Parliament PDFs (`eval/bakeoff.md`, "Backfill actuals").
- **`source_id` / output root:** `gemini-api` and `extractions/gemini-api/` for any Gemini
  model on either transport; `openrouter-<model>` (e.g. `openrouter-gpt-6-luna`,
  `openrouter-claude-sonnet-5.5`) for other vendors, so each bake-off arm has its own tree and
  `load --source` never mixes them. `--source-id` / `--out-root` override both. The `model`
  field in each file is the id as sent (`google/gemini-3.8-flash` on OpenRouter).

### OpenRouter transport (`disclosures/openrouter.py`)
Request shape (verified against openrouter.ai/docs and live on 2026-10-02):
- The chunk is a `file` content part, `{"type":"file","file":{"filename":"chunk.pdf",
  "file_data":"data:application/pdf;base64,…"}}`, followed by a `text` part (prompt +
  preamble). `plugins: [{"id":"file-parser","pdf":{"engine":"native"}}]` pins the model's own
  PDF reading: 64% of the corpus pages have no text layer, so a text-extraction engine would
  return nothing. Only models whose OpenRouter listing has `file` in `input_modalities` work.
- `response_format: {"type":"json_schema","json_schema":{"name":"extraction","strict":true,
  "schema":…}}` with the same per-chunk schema as the Gemini path plus
  `additionalProperties: false` on every object (OpenAI/Anthropic strict modes require it).
  `provider.require_parameters: true` keeps the request off endpoints that would ignore the
  schema (e.g. Claude on Bedrock).
- `--provider-order a,b` becomes `provider.order` with `allow_fallbacks: false`. Use
  `google-ai-studio/flex` for Gemini at half price ($0.38 / $1.88 per MTok) with higher
  latency: right for an unattended backfill. (`:batch` is a separate asynchronous API; not used.)
- `--ignore-providers a,b` becomes `provider.ignore` (provider slugs OpenRouter must skip) on
  both the primary and the `--fallback-model` backend; ignored on the `gemini` transport, like
  `--provider-order`. Added 2026-10-02 because `anthropic/claude-sonnet-5.5` fallbacks routed to
  Azure failed with HTTP 400 `no_content_length_header` ("Content-Length header is required");
  other providers served the same requests. Use `--ignore-providers azure`.
- `temperature: 0` except for `openai/*` models, which reject the parameter, and `anthropic/*`
  models: on OpenRouter only the Azure endpoints of `anthropic/claude-sonnet-5.5` list
  `temperature`, so with `require_parameters` every Sonnet fallback was pinned to Azure (whose
  intermittent `no_content_length_header` 400s failed 5 PDFs) and `--ignore-providers azure`
  alone left no endpoint at all (404 "Filter by Parameters"). Found 2026-10-02 during the
  backfill; the fallback now goes to Anthropic's own endpoint.
  `--reasoning-effort` sends `reasoning: {"effort": …}`. `max_tokens` 65,536.
- `usage: {"include": true}` makes OpenRouter return `usage.cost` (USD); the extractor sums it
  per PDF and per run. `completion_tokens` already includes reasoning tokens.
- OpenRouter normalises `finish_reason`: `length` → the `MAX_TOKENS` re-split rule;
  `content_filter`/`error` fail the PDF (the raw `native_finish_reason` is in the message).
- Retries: HTTP 408/429/5xx and transport errors (timeouts, resets) use the same backoff as
  the Gemini path; 400/402/404 fail the PDF at once. An HTTP 200 whose body carries `error`
  (OpenRouter does this for some provider errors) is treated as that error's code.
- Headers: `Authorization: Bearer $OPENROUTER_KEY` and `X-OpenRouter-Title`. The key is never
  logged. Per-call timeout 600 s.

### How it works
- **Caller fields** are set by the program, never by the model: `sha256` and page count come
  from the file (PyMuPDF), and chamber/parliament come from the path (`pdfs/<NN>/x.pdf` → house;
  `pdfs/senate/<NN>/x.pdf` → senate). Other paths are rejected. Also set: `source_id="gemini-api"`,
  `model` = the resolved id, `extracted_at` (UTC, seconds), `schema_version="2.0"` and
  `pages_covered = 1..page_count`.
- **Chunks:** each PDF is split in memory into chunks of up to `--chunk-pages` pages (default 20).
  Each chunk is sent as **inline PDF bytes**. A chunk over 15 MB goes through the Files API
  instead, and the uploaded file is deleted right after the call. The shared prompt is
  followed by a chunk preamble: "pages S–E of an N-page PDF; `page` must be the absolute
  source page". Output is constrained by a per-chunk response JSON Schema
  (`extract_gemini.response_schema()`), with temperature 0 and max output 65,536 tokens.
- **Page offsets:** if a chunk starts after page 1 and *every* returned page is within
  `1..chunk_len`, the pages are treated as chunk-relative and shifted by `start-1`.
  Otherwise they are trusted as absolute. This can't misfire, because every chunk that
  starts after page 1 starts after its own length. A page still outside the chunk counts as
  an error, and the PDF fails.
- **Re-split:** a chunk that finishes with `MAX_TOKENS`, or returns unparseable or
  wrong-shaped JSON, is split in half (the first half gets the extra page). Each half is
  retried, recursively, down to 1 page. If a 1-page chunk still fails, the PDF fails: **no
  output file is written**, the PDF is listed under `Failed PDFs:` and the command exits 1
  after processing the other PDFs. Any other non-STOP finish reason (SAFETY, RECITATION,
  content_filter) is a content block: the chunk goes to `--fallback-model` if one is set,
  otherwise the PDF fails straight away.
- **Retries (both transports):** HTTP 429 and 5xx are retried with exponential backoff
  (2 s × 2^n + jitter, `--max-retries` retries, default 4 → at most 5 tries per call).
  400/401/402/403/404 are not retried.
- **Merge:** items are concatenated in page order, then de-duplicated keeping the first. The
  key is ADR-5's (section, owner, normalised entity-or-description, page), extended with the
  normalised description, subsection, change_type and lodged_date. The bare key would drop
  52 genuine gold items, such as two Westpac loans on one page (see `DECISIONS.md`).
  Name, electorate and statement date come from the first chunk that gives them. A
  `statement_date` that can't be parsed is set to null, with a note. `extraction_notes` joins
  the chunk notes, prefixed `pages S-E:`. `usage` sums input and output tokens over every call,
  re-split calls included. Output tokens include thinking tokens, which are billed as output.
- **Write:** the file is written to `<stem>.json.tmp` and checked with `validate_file`. It is
  moved into place only if valid; otherwise it is deleted and the PDF is reported failed.
  An invalid extraction is never left on disk.
- **Cost constants** (`extract_gemini.PRICE_USD_PER_MTOK_*_THROUGH_2026_12_31`): $0.75 in /
  $3.75 out per MTok for `gemini-3.8-flash`, valid **through 2026-12-31** ($1.50 / $7.50 from
  2027-01-01). Used only for the estimate on the `gemini` transport; the OpenRouter transport
  reports the provider's actual cost. Batch API pricing is 50% lower but is not used.
- **`--batch` is not implemented.** It exits 2 with a message. Synchronous calls give the same
  output. A batch path would need its own polling, and its own handling of re-split rounds.

## Arm A: Claude Code Workflow (`workflow-claude`)

`.claude/workflows/extract-disclosures.js` bundles the PDFs greedily, in the given order, into
groups of up to about 120 pages (a larger PDF gets a bundle to itself). It runs one agent per
bundle (default model `sonnet`, `opus` selectable). Each agent:
1. Reads `extract.md`.
2. Computes `pdf_sha256` and `page_count` with a Python one-liner.
3. Reads each PDF with `Read` in ranges of up to 20 pages.
4. Writes `<out_root>/<chamber>/<parliament>/<stem>.json` with `source_id "workflow-claude"`,
   `model "claude-code-<model>"`, the given `extracted_at` and `usage: null`.
5. Runs `validate`, with at most 2 fix rounds.

Each agent reports `{path, out, status: ok|invalid|failed, errors, items}` per PDF. The workflow
returns `{files, ok, invalid, failed, bundles}`; any PDF an agent fails to report counts as `failed`.

The script cannot read files or the clock, so the caller passes:

```js
args = {
  pdfs: [ /* repo-relative paths */ ],
  out_root: "extractions/workflow-claude",   // default
  model: "sonnet",                            // or "opus"
  page_counts: { "<path>": <pages> },         // optional; improves bundling (unknown = 20 pages)
  extracted_at: "2026-10-02T00:00:00+00:00",  // required ISO timestamp
  chamber: "house"                            // optional default for pdfs/<NN>/ paths
}
```

### Gold-set run (12 PDFs, 289 pages, 4 bundles of 91/72/110/16 pages; fits the default workflow size)
Invoke the Workflow tool with name `extract-disclosures` and:
```json
{"pdfs": ["pdfs/43/plibersekt_43p.pdf", "pdfs/43/royw_43p.pdf", "pdfs/44/butlerm_44p.pdf",
          "pdfs/44/thistlethwaitem_44p.pdf", "pdfs/45/husice_45p.pdf", "pdfs/45/prenticej_45p.pdf",
          "pdfs/46/morton_46p.pdf", "pdfs/46/wilkie_46p.pdf", "pdfs/47/gosling_47p.pdf",
          "pdfs/47/kingm_47p.pdf", "pdfs/47/morrison_47p.pdf", "pdfs/47/tink_47p.pdf"],
 "out_root": "extractions/workflow-claude", "model": "sonnet",
 "page_counts": {"pdfs/43/plibersekt_43p.pdf": 15, "pdfs/43/royw_43p.pdf": 14,
                 "pdfs/44/butlerm_44p.pdf": 13, "pdfs/44/thistlethwaitem_44p.pdf": 31,
                 "pdfs/45/husice_45p.pdf": 18, "pdfs/45/prenticej_45p.pdf": 34,
                 "pdfs/46/morton_46p.pdf": 14, "pdfs/46/wilkie_46p.pdf": 14,
                 "pdfs/47/gosling_47p.pdf": 10, "pdfs/47/kingm_47p.pdf": 81,
                 "pdfs/47/morrison_47p.pdf": 29, "pdfs/47/tink_47p.pdf": 16},
 "extracted_at": "2026-10-02T00:00:00+00:00"}
```
Then run `python -m disclosures validate extractions/workflow-claude`.

To generate `pdfs` and `page_counts` for any set (e.g. one parliament):
```sh
.venv/bin/python -c "import glob,json,sys,pymupdf; ps=sorted(glob.glob(f'pdfs/{sys.argv[1]}/*.pdf')); print(json.dumps({'pdfs':ps,'page_counts':{p:pymupdf.open(p).page_count for p in ps}}))" 45
```

### Backfill (only if the bake-off picks this arm, gate G2)
1. Kevin raises **"Dynamic workflow size"** in `/config` first. The full backfill is about
   110 agents (13,205 pages / 120), which is over the default size guideline.
2. Run one **wave per parliament**, roughly 2,100–3,150 pages and about 18–27 agents each
   (43rd: 150 PDFs / 2,718 pp; 44th: 153 / 2,679; 45th: 159 / 3,148; 46th: 155 / 2,078;
   47th: 157 / 2,582). Use the same `extracted_at` within a wave.
3. After each wave, run `python -m disclosures validate extractions/workflow-claude/house/<NN>`.
   Re-run only the invalid or failed PDFs, by passing just those paths.

Only the orchestrating Claude Code session or Kevin can invoke Workflow. Implementer
subagents cannot, which is why this arm was not run in Phase 2a.
