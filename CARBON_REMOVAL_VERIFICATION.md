# Carbon removal commitments: fiscal periods and measurement basis

Sources are the exact committed PDFs: 2024 report page 19 Carbon Table 3, 2025 report page 21 Carbon Table 3, and 2026 report pages 32–33. All four source PDF versions are now hash-locked for audited-row generation.

| Contracted commitment (metric tons) | FY23 (2024 report) | FY24 (2025 report) |
|---|---:|---:|
| Total | 5,015,019 | 21,927,370 |
| In-year neutrality allocation | 3,549,242 | 1,690,940 |
| FY2030 carbon negative allocation | 1,465,777 | 2,804,056 |
| FY2031+ and historic allocation | Not separately reported | 17,432,374 |

These are commitments signed in the fiscal year, including future delivery/retirement over multiple years, not removals realized in that fiscal year. The 2026 report page 32 describes more than 45 million metric tons expected over the next three decades; page 33 labels 45 million metric tons contracted in FY25. Store the qualified disclosure, not an invented exact 45,000,000 scalar. FY25 exact totals and allocations remain missing in the numeric provider. Missing historic allocation in FY23 is not zero.

Previous technology volumes (8.54M, 4.21M, etc.) and shares (38.9%, 19.2%, etc.) have no audited support in Carbon Table 3 and are removed. The technology provider returns an empty table with an unavailable reason. Dashboard and static bilingual summaries present audited commitments and the separate FY25 disclosure. Related contextual insight no longer claims an unsupported world-largest portfolio.

Nine audited evidence rows are added at their actual source pages. The atomic index has 1,597 chunks, including 41 audited rows. Exact-content vectors from the same model were reused; new evidence was encoded using the actual cached embedding model. Retrieval checks cover FY23, FY24, FY25, a two-period comparison, and unsupported FY99. Source hash, units, exact values, allocation reconciliation, missing values, qualified disclosures and bilingual summaries are regression-tested.

Validation: 120 offline tests pass; Ruff and app syntax checks pass. Extraction prompts prohibit treating qualified disclosures as exact scalars and confusing commitments with realized removals. Prompt instructions are not a deterministic guarantee of generated-answer correctness. The remaining evaluation must exercise actual generated answers across question families, including technology shares, realized removals, qualified arithmetic, and period comparisons.
