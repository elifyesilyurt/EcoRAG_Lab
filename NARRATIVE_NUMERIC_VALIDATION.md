# Numeric narrative output gate

Problem: a generated numeric sentence can use a valid number from the wrong metric/year. Finding that number somewhere in the retrieved context is insufficient validation.

The production general-RAG branch and evaluation runner now share `generate_grounded_narrative`. An unambiguous audited core metric name with explicit fiscal/calendar periods produces a literal source-bound answer with metric, period, unit, page and qualifications. Model-generated values are not used. Qualified disclosures remain literal; exact-value requests, absent periods, duplicate metric/period candidates, incompatible requested units and unsupported scope produce an unavailable response. Arithmetic/conversions remain the audited calculation route.

Other narrative requests still call Foundry. The draft is buffered before display; digit/percentage and common English/Turkish number-word claims are rejected instead of being streamed to the user. Page/year numbers are deliberately not exempted. A number appearing elsewhere in context does not make that draft acceptable. Rejected drafts remain in evaluation diagnostics, never the displayed answer. No retry or unchecked fallback republishes them.

This is a conservative output gate, not a complete semantic proof. Qualitative model prose is marked `qualitative_unverified` in diagnostics. Common number-word detection is not an exhaustive natural-language quantity parser. Broad/ambiguous metric names, numeric narrative facts present only in raw text, target dates and citations in generated prose may be withheld. Direct source text keeps original English metric labels/qualifications even in a Turkish answer. Full UI behavior and all static topic routes are not certified by the component evaluation. These limitations must not be described as universal accuracy.

Regression tests use altered IDs/values, calendar/fiscal separation, missing periods, qualified versus exact values, regional scope, duplicate evidence, requested-unit mismatches, injected numeric prose and actual app wiring before display. CI runs these tests without a model.

Core metric matching normalizes singular/plural plastics and accepts omitted generic descriptors such as product/primary/operational only when there is one matching source metric. The displayed metric and qualifications retain the actual source scope. Explicit secondary/shipping/all-packaging and unsupported regional requests are rejected. This lexical resolver remains conservative and is not a general semantic entailment system. Explicit calendar-year-ended dates are recognized separately from fiscal periods.

Validation: 164 offline tests and Ruff passed. Four real-index source-bound narrative scenarios passed (historical contracted removal, qualified FY25 removal, operational waste and fiscal/calendar packaging comparison). The missing technology-share case abstained in the separate generated-draft run. These checks are not five correct generative-model answers.
