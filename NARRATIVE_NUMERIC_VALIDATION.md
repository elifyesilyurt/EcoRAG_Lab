# Numeric narrative output gate

Problem: a generated numeric sentence can use a valid number from the wrong metric/year. Finding that number somewhere in the retrieved context is insufficient validation.

The production general-RAG branch and evaluation runner now share `generate_grounded_narrative`. An unambiguous audited core metric name with explicit fiscal/calendar periods produces a literal source-bound answer with metric, period, unit, page and qualifications. Model-generated values are not used. Qualified disclosures remain literal; exact-value requests, absent periods, duplicate metric/period candidates, incompatible requested units and unsupported scope produce an unavailable response. Arithmetic/conversions remain the audited calculation route.

Other narrative requests now use deterministic extractive ranking. Candidate complete source sentences preserve wording/negation apart from PDF whitespace normalization, satisfy concept overlap and scope checks, and exclude measured numerical claims. A named uppercase framework version may be retained literally. Question-concept coverage determines rank; duplicate sentence text is removed and at most three excerpts are selected. Typed source references are validated before display. No generated narrative or model-owned source IDs are accepted in this production path. See MULTI_SOURCE_SELECTION.md for the current policy.

This validates source fidelity, not complete semantic entailment or answer completeness. Lexical relevance may be insufficient; PDF extraction can interleave columns. Missing whole sentences or unlabelled prose for explicit fiscal/calendar requests is withheld. Numeric narrative facts only present in raw prose, dates and indirect metric questions remain unsupported. Original English source labels/quotations may appear in Turkish responses. Static topic paths are outside this gate; the full 500-question benchmark is still historical.

Regression tests cover source wording/negation, fabricated extra prose, malformed/unknown/duplicate/boolean references, numeric or visual fragments, altered source IDs/text, unsupported fiscal inference, bounded repair and actual app wiring before display.

Core metric matching normalizes singular/plural plastics and accepts omitted generic descriptors such as product/primary/operational only when there is one matching source metric. The displayed metric and qualifications retain the actual source scope. Explicit secondary/shipping/all-packaging and unsupported regional requests are rejected. This lexical resolver remains conservative and is not a general semantic entailment system. Explicit calendar-year-ended dates are recognized separately from fiscal periods.

Validation: 164 offline tests and Ruff passed. Four real-index source-bound narrative scenarios passed (historical contracted removal, qualified FY25 removal, operational waste and fiscal/calendar packaging comparison). The missing technology-share case abstained in the separate generated-draft run. These checks are not five correct generative-model answers.

Streamlit validation: actual app startup and four chat/widget flows passed with real cached embeddings and the current index. This found and fixed an unsupported `st.space` call and missing CY-aware topic routing. AppTest uses a list representation workaround for its single-select ButtonGroup serializer while preserving each real selection. It does not verify browser pixels. See `run_ui_smoke.py` for the opt-in production-dependency check.

One eligible source sentence binds directly; multiple candidates use deterministic ranking. Compact labels optionally enclosed in brackets are accepted only as a complete reference-only response. Added prose, unknown labels and duplicate references remain rejected.
