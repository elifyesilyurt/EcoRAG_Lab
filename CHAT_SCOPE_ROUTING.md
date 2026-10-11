# Question-specific chat routing

All six legacy topic intents now enter the grounded answer path, including undated questions. A date-only guard did not protect questions that constrain geography, technology, product or organizational scope. Dashboard summaries remain available for their labelled inventory views; they are no longer automatic chat answers.

This deliberately favors an unavailable answer when evidence cannot establish the requested metric, period and scope. Broad undated quantitative questions may need a fiscal/calendar period before a value can be verified. Qualitative output remains literal retrieved source excerpts, not a completeness or semantic entailment guarantee.

Validation: 188 offline tests; the new cross-product routing test covers all six topic intents and seven English/Turkish scope examples, preserving math and out-of-domain routes. Seven actual Streamlit AppTest checks passed with cached production embeddings/index, including Madrid groundwater refusal, fiscal arithmetic, calendar packaging and excerpt provenance. AppTest does not certify browser pixels or every possible question.
