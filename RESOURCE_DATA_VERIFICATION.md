# Water and energy verification — stage 3

Source edition: 2026 Environmental Data Fact Sheet, reporting FY25.
Source: https://aka.ms/SustainabilityFactsheet2026
The independent fixture `tests/fixtures/resource_metrics_2026.json` records
source SHA-256 hashes, page/table references, 31 numeric values and one
unreported baseline percentage. Relevant pages were checked as rendered images
as well as extracted text. The fixture is not generated from application tables.

## Problems, causes, and corrections

| Problem | Cause | Correction |
|---|---|---|
| Water volumes inflated | ML values mislabeled as million m3; values also differed from the current source edition | Use Table 8 p.7 and convert ML / 1000 to million m3 |
| Invented water targets and achievement | Hardcoded 9,500/7,800 million m3 and 82.1% lacked source support | Remove these rows; show annual withdrawal, consumption, discharge and realized replenishment |
| Lifetime benefits treated as annual outcome | Contracted benefits conflated with realized volumes | Report p.25 annual FY25 replenishment is 14,278,782 m3; >133 million m3 is lifetime expected benefit, not annual realization |
| Unsupported regional project allocation | Hardcoded project counts/shares/billion-m3 volumes | Preserve the function/schema but return an empty frame marked unavailable, not zero observations |
| Electricity consumption inflated | Static approximations (43.8M / 41.6M MWh) substituted for reported values | Table 5 p.6: electricity 37,026,353 MWh; matched renewables 34,534,392 MWh; total energy 37,461,476 MWh |
| Renewable accounting conflated | Matched renewables / electricity and hourly CFE treated as the same percentage | Keep Table 5 matched volumes distinct from Table 6 direct renewable percentage, which includes grid mix; FY25 is 100% |
| False baseline precision | FY20 direct renewable percentage invented | Source shows a dash; retain missing and render an em dash, not zero |
| UI and ingestion repeat wrong numbers | Independent hardcoded summaries, insight card, KPI and injected water context | Read the audited table in summaries/cards/KPI and share a source-aware context builder with future ingestion |

FY24 has a source discrepancy: Table 8 reports withdrawals of 11,590 ML,
while the report p.25 graphic shows 11,589,000 m3 (1 ML lower). We deliberately
use Table 8 for the inventory and disclose the discrepancy. Historical inventory
values are restated in the 2026 publication. Do not mix editions silently.

The annual replenishment numbers for the retained years are independently
transcribed from report p.25: FY20 746,937; FY23 2,745,825; FY24 6,610,656;
FY25 14,278,782 m3. Global replenishment exceeding global withdrawals does not
establish achievement in every priority watershed.

## Validation

```bash
python -m unittest test_dynamic_math test_baseline_regressions test_resource_metrics -v
```

28 tests: **25 pass, 3 expected failures**. The first 7 resource tests failed
against the prior implementation before changes. Checks now cover conversion,
source values, missing baseline, removal of unsupported project allocations,
TR/EN summaries, changed input values, dashboard wiring, water insight, and
shared ingestion context. Full modified Python files also compile.
CI runs all three test modules on every push and PR.

## Practical limits and remaining work

The ingestion code is corrected for future builds, but no existing vector DB
was rebuilt in this environment. Use a separate output DB when validating a
rebuild: the existing ingestion script drops the documents table. Atomic safe
rebuilds and real retrieval integration remain part of the ingestion stage.
A full Foundry/Streamlit/model session has not been run.

Existing legacy benchmark answers still contain old water/energy expectations.
They are not part of the validated offline suite and require an independent
benchmark audit; old scores do not prove these changes correct. Water/energy
metric names/rows now reflect the source, so downstream consumers must match
metric names and units rather than old row positions.

The broad intent router still selects a fixed FY25 summary for many specific
year/calculation/commitment questions; routing and requested-year handling are
not certified by this data audit. The three tracked unresolved bugs remain
partial math success, water calculator routing, and Xbox domain rejection.
Carbon removal, waste, packaging, site-specific electricity claims and unrelated
ESG insight branches still need source audits.
