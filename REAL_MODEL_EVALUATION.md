# First actual Phi-4-mini answer evaluation

The local server was successfully started at port 56720 and the cached Phi-4-mini GPU variant loaded. The 12-case component integration run completed: 5 rule checks passed, 7 failed. This is not a general accuracy estimate. The successful checks were the FY25 waste amount, missing technology share abstention, unsupported FY99/FY26, and domain rejection.

Failures included invalid generated Python, missing m3 conversion, malformed digit grouping, false abstention with available carbon-removal evidence, unsuitable exact-growth extraction, and a wrong fiscal packaging value. After code-format preservation and unit-prompt changes, the isolated water retest still returned 5.096 instead of the requested 5,096,000 m3. These changes do not establish correctness of the full pipeline.

The repetition cleaner performed repeated regex normalization within nested n-gram scans, delaying long narrative responses. It now normalizes once and tracks earliest occurrences while retaining non-overlapping repeat semantics. Raw math code bypasses prose trimming. CI now explicitly installs Pydantic used by extraction-prompt tests. 128 offline tests pass; they are distinct from the failed actual-model checks.

Next: structured metric/year/scope/unit selection validated against audited source rows, deterministic unit conversion, rejection of qualified inputs for exact arithmetic, and source-backed numeric output rendering. Add the already audited packaging series to retrieval evidence. Re-run every question family after these changes. Prompt changes alone are insufficient.

The evaluation excludes Streamlit UI, translation, static topic routes and math-result prose synthesis. Phrase/number rules are partial correctness signals, with raw answers requiring human review. Actual artifacts are saved in the task outputs directory, outside the repository.
