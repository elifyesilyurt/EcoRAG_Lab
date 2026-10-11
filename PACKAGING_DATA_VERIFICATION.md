# Packaging period and source verification

Source: committed `docs/Microsoft_2026_Environmental_Data_Fact_Sheet.pdf`, page 8, Table 11 and footnotes 1–3; https://aka.ms/SustainabilityFactsheet2026.

| Metric (%) | FY22 | FY23 | FY24 | FY25 |
|---|---:|---:|---:|---:|
| Product packaging recyclability | 94.3 | 93.7 | 94.6 | 95.8 |
| Single-use plastics in primary product packaging | 4.7 | 4.6 | 5.4 | 4.2 |

These are restated fiscal-year values. Footnote 3 separately reports 0.07% single-use plastics for the calendar year ended December 31, 2025. It must not replace FY25's 4.2%, imply a FY26 actual, or support an invented 2030 deadline or packaging certification claim. Earlier static summaries incorrectly assigned 4.2% to FY24 and 0.07% to FY25/FY26 and attached unsupported certification/design claims.

Fiscal and calendar series now have separate providers. Bilingual summaries use these providers; related insight and dashboard period labels are corrected. The four regression tests verify all eight fiscal values, separate period columns, missing FY26, bilingual source/period explanations, and summary dependence on shared data rather than hardcoded numbers.

Validation: 108 offline tests pass. The existing raw source index already contains Table 11; this change adds no audited-index rows and does not rebuild embeddings. Real generated-answer accuracy for all packaging questions remains to be evaluated. Carbon removal and waste source audits are still pending; their existing hardcoded summaries are not validated by this change.
