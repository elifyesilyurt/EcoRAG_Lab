# Reliability baseline — stage 1

Branch: `fix/ecorag-reliability`  
Baseline source: `2413b4d5011c74ddfb2e773b6f643fc4cd3dd140`

## Run the offline checks

```bash
python -m pip install -r requirements-test.txt
python -m unittest test_dynamic_math test_baseline_regressions -v
```

PowerShell uses the same install and test commands.

No Foundry server, model weights, PDF files, vector database, or Streamlit process
is required. The tests compile selected, unchanged function bodies from `app.py`
with their actual math and table dependencies. They do not copy the router rules
into a separate implementation. This temporary extraction approach will be
replaced with direct imports when the query engine is separated from the UI.

## Current status after stage 2

17 tests: **14 pass, 3 expected failures**. FY24 display regressions are fixed.
See `CARBON_DATA_VERIFICATION.md` for the source-backed 51-value carbon audit.
Water/energy/waste, retrieval and model integration remain unverified.

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
3. Run both offline modules and the relevant new regression tests.
4. Record passing checks, unresolved defects, and any integration limitations.
5. Run model/PDF/retrieval integration checks when those layers change.

CI runs this offline suite on every branch push and every pull request. It does
not run legacy model-dependent tests or certify end-to-end RAG quality. Later
stages will add PDF-grounded data validation and an independent answer benchmark.
