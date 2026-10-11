# Carbon inventory verification — stage 2

## Source and scope

Verified against the **2026 Environmental Data Fact Sheet**, page 3, Table 1A:
https://aka.ms/SustainabilityFactsheet2026

The 2026 Environmental Sustainability Report directs readers to this fact sheet
for comprehensive metrics (report pages 62–63). Publication year 2026 covers
FY25; these are historical FY20/FY24/FY25 values restated in that publication,
not a mixture of values from earlier report editions.

All 17 rows × 3 years (51 values) in `get_carbon_emissions_df()` were compared
with extracted text and the rendered source page. They match. The source PDF's
SHA-256 is recorded in `tests/fixtures/carbon_emissions_2026.json`; the fixture
was transcribed independently from Table 1A, not generated from the app table.

Units are metric tons CO2 equivalent. Total emissions use market-based Scope 2.
Location-based Scope 2 must not be added a second time. Source footnotes state
that Scope 3 subtotals and total emissions are rounded to the nearest thousand;
category sums therefore need not equal published subtotals exactly.
Table 1B applies management's criteria and is a different inventory; do not
replace Table 1A totals with its values.

## Fixed behavior

The TR/EN summary used a hardcoded FY25 total in the FY24 column. All displayed
totals and introductory numbers now come from their respective table columns.
FY24 displays 16,693,000; FY25 displays 21,121,000 mtCO2e. Category 1/2 lookup
now uses exact metric names so Category 11 cannot be selected as Category 1.
Scope 2's growth-rate cell is numeric. The summary identifies its source and
accounting basis; unsupported portfolio/energy claims were removed from this
emissions-only summary rather than attributed to Table 1A.

## Validation

```bash
python -m unittest test_dynamic_math test_baseline_regressions -v
```

17 tests: **14 pass, 3 expected failures**. The two FY24 tests are now ordinary
passing regressions. Added checks cover all 51 source values, changed input
totals (to catch hardcoding), reordered Category 11 rows, and source/basis notes.
CI exercises these on every push and PR without downloading a mutable external
PDF. A future source update requires deliberate fixture/provenance review.

To recheck the source manually, download the URL above and compare page 3 with
the fixture. Validate its SHA-256 against `source_pdf_sha256` before treating it
as the same edition used here. The source PDF is not duplicated in this commit.

## Remaining work

This verification covers the carbon emissions inventory and its trend summary.
It does not certify carbon removal, water, energy, waste, other hardcoded app
summaries, ingestion, retrieval, or model-generated answers. During inspection,
energy/water tables showed discrepancies requiring their own source and unit
audit; they remain explicitly unverified. The three remaining tracked bugs are
partial math success, water calculation routing, and the Xbox domain filter.
