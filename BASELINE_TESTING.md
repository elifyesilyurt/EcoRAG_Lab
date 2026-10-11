# Reliability baseline — stage 1

Branch: `fix/ecorag-reliability`  
Baseline source: `2413b4d5011c74ddfb2e773b6f643fc4cd3dd140`

## Run the offline checks

```bash
python -m pip install -r requirements-test.txt
python -m unittest test_dynamic_math test_baseline_regressions test_resource_metrics test_math_response test_query_routing test_temporal_scope test_ingestion_reliability test_answer_evaluation -v
```

PowerShell uses the same install and test commands.

No Foundry server, model weights, PDF files, vector database, or Streamlit process
is required. Routing functions are imported directly from `query_routing.py`. Other checks
compile selected function bodies from `app.py` with their actual math and table
dependencies. They do not copy the router rules
into a separate implementation. This temporary extraction approach will be
replaced with direct imports when the query engine is separated from the UI.

## Current status after stage 8

126 tests: **126 pass, no expected failures**. FY24 display, partial math execution,
and water calculator routing regressions are fixed. See
`MATH_EXECUTION_RELIABILITY.md` and `QUERY_ROUTING_RELIABILITY.md` for execution
and routing contracts. Xbox environmental questions now pass the domain gate;
generic gaming and explicit exclusions remain rejected.
See `CARBON_DATA_VERIFICATION.md` for the carbon audit and
`RESOURCE_DATA_VERIFICATION.md` for water/energy source checks and units.
Requested-year routing and temporal retrieval constraints are now tested; see
`TEMPORAL_RELIABILITY.md`. Waste source data, retrieval relevance, corpus rebuild
and real answer-model integration still require validation.
See `INGESTION_RELIABILITY.md` for transactional rebuild, source provenance
and real embedding checks.

## Recorded initial baseline

- Existing math suite: 4 tests pass.
- New working-behavior checks: 4 tests pass; 6 fixed queries cover language/routing.
- Known regressions: 5 expected failures (4 defects, including both UI languages).
- Total: **8 passed, 5 expected failures**. Expected failures are unresolved bugs,
  not evidence of application correctness.

| Defect | Expected behavior | Current behavior |
|---|---|---|
| Partial math execution | Failed final calculation returns failure | `a=10` survives and `success=True` |
| Water difference routing | Use mathematical query route | Uses generic water summary route |
| Xbox sustainability domain | Packaging question is accepted | `xbox` blacklist rejects it |
| FY24 total, TR and EN | Display FY24 value from emissions table | Displays FY25 value |

The table consistency checks do **not** certify the values against source PDFs.
The arithmetic fixture uses synthetic values to isolate calculator behavior.
The query fixture records existing behavior, not gold-standard answers.

## Reproduce failures without expected-failure marking

Bash:

```bash
ECORAG_STRICT_REGRESSIONS=1 python -m unittest test_baseline_regressions.TestKnownRegressions -v
```

PowerShell:

```powershell
$env:ECORAG_STRICT_REGRESSIONS = "1"
python -m unittest test_baseline_regressions.TestKnownRegressions -v
Remove-Item Env:ECORAG_STRICT_REGRESSIONS
```

This command must currently exit with failures. Once a defect is fixed, remove
its `@known_defect` marker in the same change. An unexpected success fails normal
CI so fixes cannot silently leave outdated markers behind.

## Checks for every subsequent change

1. Reproduce the defect before changing its implementation.
2. Fix it and remove only its expected-failure marker.
3. Run all offline modules and the relevant new regression tests.
4. Record passing checks, unresolved defects, and any integration limitations.
5. Run model/PDF/retrieval integration checks when those layers change.

CI runs this offline suite on every branch push and every pull request. It does
not run legacy model-dependent tests or certify end-to-end RAG quality. Later
stages will add PDF-grounded data validation and an independent answer benchmark.
