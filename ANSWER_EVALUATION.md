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

126 offline tests pass, including six checks of evaluation scoring and shared prompts. These are not 126 model-answer evaluations. In this session Foundry startup failed to expose a working endpoint after an initial filesystem permission problem; its runtime log reports `GetDomainName: -1`. Real-model evaluation remains pending a working local service. No new accuracy percentage is claimed.
