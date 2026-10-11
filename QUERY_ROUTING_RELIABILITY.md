# Query routing reliability — stage 5

## Problem, cause, and correction

The original router checked broad topic keywords before arithmetic intent.
Water differences went to the fixed water summary; carbon-removal growth,
Scope comparisons, PPA ratios and packaging percentage-point calculations could
likewise return topic tables without performing the requested calculation.

Routing now follows: **domain gate → numeric operation → narrative comparison
→ topic summary → general report retrieval**. The existing domain gate remains
first. A water target is checked in its own topic before generic 2030/carbon
commitment keywords, so a 2030 water question does not become a carbon question.
Zero-waste goal questions similarly keep their topic.

`is_mathematical_query()` recognizes explicit calculation/counting verbs,
ratios and percentage points. Broad compare/total/difference/growth words need
numeric context. Policies/strategies alone remain narrative, including dated
comparisons; their comparisons use general RAG rather than fixed FY25 tables.
Definitions such as "what does renewable share mean" are not calculations.
Empty/null mathematical queries are handled safely.

Short domain tokens (`su`, `ul`, `rec`, `cop`) now match whole words. Previously
`ul` inside `calculate` and `su` inside `sum` could falsely accept unrelated
arithmetic as an ESG question. Other domain rules were retained for the next
coverage stage; Xbox sustainability still has a tracked rejection bug.

The actual domain/classifier functions moved to `query_routing.py`, imported
by the app and directly by tests. This removes UI initialization from routing
tests without copying their implementation. The baseline comparison fixture
now intentionally expects arithmetic for FY20/FY25 Scope comparison instead of
its previous generic carbon summary.

## Examples

| Question | Before | After |
|---|---|---|
| FY25 water withdrawal minus consumption | Water summary | Math route |
| Calculate FY25 PPA matching ratio | Carbon commitments summary | Math route |
| FY24/FY25 carbon-removal percentage growth | Carbon removal summary | Math route |
| Packaging percentage-point reduction | Packaging summary | Math route |
| Compare water policies in 2024 and 2025 | Unqualified compare could select math | Narrative report retrieval |
| 2030 water positive target | Carbon commitments summary | Water topic |
| Calculate 10 minus 4 | Accepted via `ul` substring | Out of domain |

## Validation

```bash
python -m unittest test_dynamic_math test_baseline_regressions test_resource_metrics test_math_response test_query_routing -v
```

50 tests: **49 pass, 1 expected failure**. The first five routing tests were
run against the prior router and exposed 14 failed assertions plus the null
query error. The final independent routing fixture covers 28 TR/EN questions
across math, narratives, domain rejection and topic goals. Additional checks
cover short domain tokens and the app's actual shared-classifier import/use.
The original water-route regression is now an ordinary passing test. CI runs
all five offline modules on every push and PR.

## Limits and next steps

This fixes route selection, not source-number extraction or final model answer
quality. No real model session, live UI or vector DB rebuild was run. The keyword
classifier remains heuristic and ambiguous questions need broader independent
evaluation. Specific-year lookups and narrative target questions can still
reach fixed FY25 summaries; requested-year handling and source-grounded answer
selection remain pending. Unverified legacy benchmark scores are not used as
validation. The one remaining tracked regression is Xbox domain rejection.
