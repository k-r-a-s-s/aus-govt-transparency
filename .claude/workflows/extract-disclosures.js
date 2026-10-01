export const meta = {
  name: 'extract-disclosures',
  description: 'Extractor A (workflow-claude, ADR-5): transcribe register PDFs into validated ADR-2 extraction JSON, one agent per <=120-page bundle.',
  phases: [{ title: 'Extract' }],
};

// args = { pdfs: [repo-relative paths], out_root?: "extractions/workflow-claude",
//          model?: "sonnet"|"opus", page_counts?: {path: n}, extracted_at: ISO string,
//          chamber?: "house" }
// No filesystem or clock access here: the caller passes extracted_at (and ideally page_counts).
const BUNDLE_PAGES = 120;
const UNKNOWN_PAGES = 20; // assumed size when page_counts is not supplied
const pdfs = (args && args.pdfs) || [];
const outRoot = (args && args.out_root) || 'extractions/workflow-claude';
const model = (args && args.model) || 'sonnet';
const pageCounts = (args && args.page_counts) || {};
const extractedAt = args && args.extracted_at;
if (!pdfs.length) throw new Error('args.pdfs must list at least one repo-relative PDF path');
if (!extractedAt) throw new Error('args.extracted_at (ISO 8601 string) is required');
if (model !== 'sonnet' && model !== 'opus') throw new Error('args.model must be "sonnet" or "opus"');

function target(path) {
  const senate = path.match(/^pdfs\/senate\/(\d+)\/[^/]+\.pdf$/i);
  const house = path.match(/^pdfs\/(\d+)\/[^/]+\.pdf$/i);
  const chamber = senate ? 'senate' : (args.chamber || 'house');
  const parliament = senate ? senate[1] : house ? house[1] : null;
  if (!parliament) throw new Error(`cannot infer parliament from ${path} (expected pdfs/<NN>/x.pdf)`);
  const stem = path.split('/').pop().replace(/\.pdf$/i, '');
  return { pdf: path, chamber, parliament: Number(parliament), pages: pageCounts[path] || null,
           out: `${outRoot}/${chamber}/${parliament}/${stem}.json` };
}

// Greedy bundling in the given order; a PDF bigger than the cap gets a bundle of its own.
const bundles = [];
let cur = [], curPages = 0;
for (const t of pdfs.map(target)) {
  const n = t.pages || UNKNOWN_PAGES;
  if (cur.length && curPages + n > BUNDLE_PAGES) { bundles.push(cur); cur = []; curPages = 0; }
  cur.push(t); curPages += n;
}
if (cur.length) bundles.push(cur);

const BUNDLE_RESULT_SCHEMA = {
  type: 'object',
  required: ['files'],
  properties: {
    files: {
      type: 'array',
      items: {
        type: 'object',
        required: ['path', 'out', 'status', 'errors', 'items'],
        properties: {
          path: { type: 'string' },
          out: { type: 'string' },
          status: { type: 'string', enum: ['ok', 'invalid', 'failed'] },
          errors: { type: 'array', items: { type: 'string' } },
          items: { type: 'integer' },
        },
      },
    },
  },
};

function prompt(bundle) {
  const list = bundle.map((t) =>
    `- PDF \`${t.pdf}\` -> write \`${t.out}\` (chamber "${t.chamber}", parliament ${t.parliament}` +
    (t.pages ? `, ${t.pages} pages` : ', page count unknown: compute it') + ')').join('\n');
  return `You are the extractor for the Australian Register of Members' Interests (Disclosures v2).
Work from the repo root. Use .venv/bin/python for every python command.

1. Read \`disclosures/prompts/extract.md\` in full first. It is your instruction set; follow it exactly,
   including the conventions C1-C11 and the checklist.
2. For EACH PDF below, one at a time:
   a. Compute the caller fields: \`.venv/bin/python -c "import sys,hashlib,pymupdf;p=sys.argv[1];print(hashlib.sha256(open(p,'rb').read()).hexdigest(), pymupdf.open(p).page_count)" <pdf>\`.
   b. Read the PDF with the Read tool in page ranges of at most 20 pages (pages: "1-20", "21-40", ...)
      until EVERY page 1..page_count has been read. Many pages are scans or handwriting: read the image.
   c. Write the JSON file with: schema_version "2.0", source_id "workflow-claude",
      model "claude-code-${model}", extracted_at "${extractedAt}", pdf_path (the repo-relative path
      exactly as listed), pdf_sha256 and page_count from step a, pages_covered = [1..page_count],
      chamber and parliament as listed, usage null, plus member_name_as_printed,
      electorate_or_state, statement_date, items and extraction_notes from the PDF.
      Item "page" is the 1-based page of the source PDF.
   d. Run \`.venv/bin/python -m disclosures validate <out file>\`. If it reports INVALID, fix the
      file (re-reading pages as needed) and validate again, at most 2 fix rounds. If it is still
      invalid, leave it and report status "invalid" with the validator's messages.
   e. If a PDF cannot be read at all, report status "failed" with the reason and write no file.
3. Never modify anything in eval/gold, pdfs/, src/ or disclosures.db, and touch no files other than
   the output files listed below. Do not git commit.

PDFs in this bundle:
${list}

Return, for every PDF listed: path (the PDF), out (the JSON path), status ok|invalid|failed,
errors (validator messages or the failure reason; [] when ok) and items (item count, 0 if none).`;
}

phase('Extract');
log(`extract-disclosures: ${pdfs.length} PDFs in ${bundles.length} bundles, model ${model}, out_root ${outRoot}`);

const jobs = bundles.map((bundle, i) => ({ bundle, i }));
const results = await pipeline(jobs, (job) => agent(prompt(job.bundle), {
  label: `bundle ${job.i + 1}/${bundles.length}: ${job.bundle.map((t) => t.pdf.split('/').pop()).join(', ')}`,
  phase: 'Extract',
  model,
  schema: BUNDLE_RESULT_SCHEMA,
}));

// Match reports to PDFs by path (independent of result order); unreported PDFs count as failed.
const reported = [].concat(...(results || []).map((r) => (r && r.files) || []));
const files = [];
bundles.forEach((bundle, i) => {
  let ok = 0;
  for (const t of bundle) {
    const r = reported.find((f) => f.path === t.pdf);
    const entry = r || { path: t.pdf, out: t.out, status: 'failed', errors: ['agent did not report this PDF'], items: 0 };
    if (entry.status === 'ok') ok += 1;
    files.push(entry);
  }
  log(`bundle ${i + 1}/${bundles.length}: ${ok}/${bundle.length} ok`);
});

const count = (s) => files.filter((f) => f.status === s).length;
const summary = { files, ok: count('ok'), invalid: count('invalid'), failed: count('failed'), bundles: bundles.length };
log(`extract-disclosures done: ${summary.ok} ok, ${summary.invalid} invalid, ${summary.failed} failed`);
return summary;
