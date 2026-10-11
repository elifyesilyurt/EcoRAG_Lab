# Temporal answer reliability — stage 7

## Problem and cause

Topic-specific chat routes called fixed FY25 summaries without reading the
question's dates or the UI report filter. Search inferred fiscal year from
publication year, accepted a report filter that disagreed with the question,
and fell back to other years when a target year had fewer than two chunks.
A strong score in an unrelated year could also suppress requested evidence.

## Shared correction

`temporal_scope.py` provides one temporal contract for chat routing, retrieval
and model instructions, covering every dated static topic: carbon, energy,
removal, water, waste and packaging. Dated or UI-filtered questions use retrieval
instead of fixed summaries. Undated summaries and the explicitly FY25 dashboard
remain unchanged; legacy removal/waste/packaging source audits are still pending.

Fiscal year and publication year are independent dimensions. FY24/FY 24/FY2024
spellings and hyphenated fiscal ranges are recognized. Fiscal data can be
restated in later reports; FY24 is not automatically mapped to the 2025 report.
Fiscal retrieval requires labelled evidence for every requested period. Report
requests constrain SQLite metadata; missing or conflicting scopes return no
evidence instead of answering with another year. A single valid chunk is enough.
Publication comparisons retain evidence from each requested publication, with
score thresholds computed per group. Fiscal comparisons retain both periods.
A UI filter cannot silently discard one side of a requested report comparison.

Bare calendar years trigger a TR/EN clarification about fiscal versus publication
year. Corporate 2030/2050 goal years do not implicitly select publications.
Unavailable explicitly named publications are rejected. Translation uses the
original question's temporal scope. Math and narrative prompts explicitly require
labelled periods/units, reject substitution, distinguish targets from actuals,
and require acknowledgement when evidence is missing or ambiguous.

## Validation

```bash
python -m unittest test_dynamic_math test_baseline_regressions test_resource_metrics test_math_response test_query_routing test_temporal_scope -v
```

73 tests pass, including 19 temporal tests. Parameterized coverage exercises
all six static routes across fiscal years, ranges, publication years and the UI
filter. Tests use the actual `search_context_hybrid` function with a temporary
SQLite database and a deterministic embedding stub, not a second search
implementation. They verify missing years, comparisons, later restatements,
conflicting filters, translation drift, and one-chunk scopes. Source tables and
existing routing/math regressions continue to pass.

## Limits and next work

This prevents fixed FY25 substitution and cross-period retrieval fallback; it
is not a proof that every possible natural-language answer is correct. Fiscal
labels must exist in chunks; table-header splitting can therefore produce a
safe no-evidence response until ingestion preserves row/period associations.
A chunk containing several fiscal labels is not a validated metric-to-year
mapping. The model must still interpret the actual rows correctly. Relevance,
report-year metadata accuracy, units, complete source coverage and model answer
faithfulness require corpus and real-model evaluation. Prompts constrain model
behavior but do not guarantee compliance. Real Foundry/Streamlit execution and
vector DB rebuild were not run in this stage. The original benchmark scores do
not substitute for these checks.
