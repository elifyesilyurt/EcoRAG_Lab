# Ingestion reliability — stage 8

## Problems and correction

The former table converter used `cell or ''`, losing reported zero values.
`zip(headers, row)` silently discarded extra cells; short rows could lose period
associations. A 200-character narrative threshold discarded real short tables.
Fixed eight-row batches could grow without a safe context boundary. Chat then
cut each evidence chunk at 500 characters, potentially removing the fiscal year,
unit or value while still displaying that source as provenance.

`ingestion_core.table_row_evidence` retains the original metric, first-column
header (including units), column labels and values. Missing values remain
explicitly missing, not zero. Complete column/value pairs are split with metric
and header repeated. Ragged rows, missing/merged headers or metrics, numeric-only
header fragments and oversized cells are flagged unresolved; they are retained
for inspection but excluded from numeric answer evidence. No units or merged
headers are inferred. Multi-level table layouts still require source auditing.

Chat uses whole evidence chunks within a 12,000-character budget. Omitted chunks
are omitted from displayed answer provenance too. If the budget removes a
required comparison period/publication, the system returns no evidence instead
of an incomplete comparison. Retrieval reads documents and index metadata in one
SQLite snapshot, avoiding mixed old/new views during rebuild.

Relevant source-audited metric rows have priority over explanatory references.
This requires a stored audited type plus two matching metric/unit tokens, with
TR/EN metric aliases, and retains the minimum relevance floor. A marker in plain
PDF text cannot confer audited status. Generic policy wording does not promote
unrelated rows. Multi-period duplicate chunks no longer leave evidence slots
unused; each requested period remains covered.

## Sources and legacy injections

Handwritten chart tables on 2026 report pages 6 and 54 were not audited source
values and have been removed. The former water context appended to report page
25 mixed inventory data from the data fact sheet with report data; it has also
been removed. Legacy `[VERIFIED TABLE]` chunks and their continuation chunks on
2026 report pages 6/25/54 are blocked until replaced by the versioned rebuild.
Visual/unresolved numeric fragments are excluded from answer context.

The original 2026 data fact sheet PDF was added to `docs/`, matching SHA-256
`0fd180837df00b3427c3eae484a492224b8f18c381e82a2aed98b04553a197f6`.
Its official source is https://aka.ms/SustainabilityFactsheet2026.
Audited carbon values are attached to fact sheet page 3, energy to page 6, and
water inventory to page 7. Annual water replenishment is attached separately to
2026 report page 25, not the fact sheet. Source hash mismatches prevent reuse of
these audited values. Values share the source-verified ESG table providers;
existing independent source fixtures continue to verify them. CI also compares
the committed index's complete audited-row content/provenance against the current
providers, and checks every source hash against the stored manifest. A UI-table
change cannot silently leave stale audited rows in the committed index.

Each stored chunk retains its publication year, document/page, type and source
PDF SHA-256. Index metadata records source manifest, model name, vector dimension,
corpus count and schema version. These fields do not assert that every raw PDF
extraction is independently source-audited.

## Transactional rebuilding

All PDFs must produce evidence. All embeddings must be present, nonempty, finite,
nonzero and dimensionally consistent; chunk provenance must match the manifest.
Validation happens before the existing DB is changed. Documents, index and
metadata are replaced inside an explicit `BEGIN IMMEDIATE` transaction, with
commit only after all inserts and count validation. Source, embedding, insert
or commit failures keep the previously committed corpus/schema. Concurrent
readers see a committed old or complete new index.

```bash
python ingest_all_reports.py
```

Production dependencies are in `requirements.txt`. The heavyweight embedding
model is imported only for a real rebuild, so offline safety tests do not load
model weights. A consistent local pre-rebuild backup was taken during this run;
backups and model caches are not committed.

## Validation and rebuilt corpus

104 offline tests pass. Coverage includes zero/missing values, short/ragged
rows, numeric/missing headers, safe splits, oversized cells, whole-row context,
comparison coverage after budgeting, legacy injection rejection, manifest/hash
checks, embedding/count failures, mid-transaction DB failure/rollback,
concurrent-reader visibility and repeated rebuilds. Orchestration tests use a
stub embedder; real-model validation was also run separately.

All four actual PDFs were extracted successfully:

| Source | Pages | Chunks |
|---|---:|---:|
| 2024 sustainability report | 88 | 488 |
| 2025 sustainability report | 90 | 486 |
| 2026 sustainability report | 66 | 298 |
| 2026 environmental data fact sheet | 28 | 309 |
| Total | 272 | 1,581 |

The index was rebuilt with the cached real `nomic-ai/nomic-embed-text-v1.5`
model, not stub vectors. All 1,581 vectors have 768 dimensions, finite values
and unit norms within `1e-5`. SQLite integrity check passes. The new corpus
contains 25 source-audited rows and zero legacy `[VERIFIED TABLE]` injections.
Actual real-embedding retrieval was exercised separately for fiscal metrics,
fiscal comparisons, a publication-scoped narrative and an unavailable fiscal
period. These checks validate retrieval/evidence constraints, not generated
answer correctness.

The committed `rag_storage.db` contains this rebuilt corpus. Local model weights,
module caches, logs and the old-index backup remain outside the repository.

## Remaining limits

Not all PDF text/table extraction is source-audited. Visual exclusion can reduce
coverage; unsupported layouts need reviewed evidence rather than guessed cells.
Numbers are not recovered from charts automatically. Multi-period labels inside
one chunk do not prove every metric-to-period association is correct. Automatic
metric selection, corpus conflict handling, retrieval relevance and real Foundry
answer faithfulness still require evaluation. Legacy benchmark scores have not
been rerun and do not validate the new corpus. Carbon-removal, packaging and
waste figures/summaries remain separate source-audit work.
