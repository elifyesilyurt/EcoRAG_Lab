# Real model answer evaluation

Run a local Foundry server in a normal Terminal:

```bash
foundry server start
```

Use the printed endpoint (the port can change). No question is entered into that command. The runner sends the fixture questions to the model:

```bash
python answer_evaluation.py --base-url http://127.0.0.1:PORT --model phi-4-mini --output ../answer-evaluation-results.json
```

Run one case with `--case water-difference-en`. The model must already be available to the service. This runner does not download a Foundry model, change the default model, or substitute a mocked response. Cached embedding-model dependencies must also be installed.

The 12 cases cover two languages, water arithmetic/unit conversion, waste diversion, carbon-removal fiscal years and future-delivery basis, a qualified FY25 disclosure, an unavailable exact growth rate, unavailable technology shares, separate fiscal/calendar packaging periods, missing years and domain rejection. Expected answers are independent source transcriptions/calculations, never included in model prompts.

Narrative evaluation uses the same `build_rag_prompts` function as the app. Arithmetic uses the original app retrieval/model-call functions and the production restricted arithmetic evaluator. Results include the index SHA256, service model inventory, raw model output/code, retrieved evidence, calculated final result and individual rule verdicts. Results are saved after each case. Unavailable service preflight exits 2 with `status: blocked`; failed cases exit 1. Neither is a successful real-model run.

Limitations: this is a component integration evaluation, not the complete Streamlit UI. Turkish translation, static topic routing and streamed math-answer synthesis are excluded. Numeric/phrase rules do not prove complete semantic correctness; raw answers need review, especially extra assertions, incompatible scopes and source contradictions. Math extraction results are checked before narrative synthesis, so a successful scalar calculation does not certify the final displayed prose.

128 offline tests pass, including eight checks of evaluation scoring and shared prompts. These are not 128 model-answer evaluations. Foundry startup initially failed. After restarting with a polling file watcher, the service became reachable at port 56720, and the cached Phi-4-mini GPU model was explicitly loaded. Actual model responses now run; output artifacts distinguish the initial unloaded-model failures from the generated-answer evaluation. No general accuracy guarantee is claimed.

The first real evaluation exposed invalid generated Python, omitted unit conversion, malformed digit grouping, and false abstention despite available evidence. Prose repetition trimming must not transform model code; production/evaluation math calls now preserve raw code formatting. Generic code/unit instructions were tightened. A subsequent water arithmetic retest still returned a million-m3 result rather than requested m3: prompt changes alone did not resolve dimensional correctness. Structured, validated metric/unit selection is still required before numeric answers can be considered reliable.
