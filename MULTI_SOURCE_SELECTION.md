# Multiple-source excerpt selection

Problem: even valid retrieved evidence was withheld when Phi returned invalid sentence-selection syntax. Turkish policy questions could also retrieve electricity quantity tables because keyword normalization stripped Turkish characters before concept mapping, and narrative selection used a different vocabulary.

All eligible narrative source sentences now use deterministic ranking by question-concept overlap. Identical normalized sentence text is deduplicated; up to three ranked complete source excerpts are displayed with provenance. Source IDs and numeric values are not generated. Different statements including negation are not collapsed or synthesized into a conclusion. The reference validator still rejects invented/duplicate IDs and added prose, but production ranking no longer needs a language-model selector. Direct audited metric/period answers remain separate. The model argument stays in the shared API for compatibility.

Retrieval and selection share canonical concept tokens. Turkish characters are normalized before keyword tokenization; longest matching aliases win, avoiding overlap such as yenile/yenilenebilir. Repeated raw/canonical keywords contribute once to the lexical score. The original human question still controls fiscal/calendar/publication scope. This does not translate arbitrary natural language or equate electricity with all energy.

Displayed provenance for narrative answers is filtered to the evidence IDs actually selected. Session diagnostics retain status, selection method, references and candidate count. AppTest verifies that the selected reference IDs exactly match displayed provenance.

Validation: 187 offline regressions passed; 13 real-index component scenarios passed, including six new positive multi-source/language variations, two unsupported-scope refusals and five prior scenarios. Six actual Streamlit startup/chat checks passed. Real cached embeddings and the unchanged 1,590-chunk index were used. These source-binding tests do not measure generative-model accuracy.

Limits: lexical overlap is not semantic entailment. Related source excerpts do not prove a complete answer or reconcile conflicting statements. Unsupported quantities, missing periods, difficult PDF layouts and broader phrasing may still be withheld. English source quotations may remain in a Turkish answer. Browser visual layout and all static topic routes are outside these checks. The historical 500-question benchmark has not been rerun.
