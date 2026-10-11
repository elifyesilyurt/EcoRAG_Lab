# Math execution reliability — stage 4

## Problem and cause

Previously `success` meant only that at least one variable survived. For example,
`a = 10; result = a / 0` could report success and expose `a` as though the requested
calculation had completed. Invalid assignment targets were silently skipped.
The UI then formatted whatever survived; anonymous `_result` expressions were
filtered out. On execution failure it fell back to an unrestricted RAG response,
allowing the model to guess the arithmetic anyway.

## Changed contract

`execute_code_lines()` parses the complete code before evaluating it. Only
single-name assignments and arithmetic expressions are allowed. Finite numeric
inputs and numeric lists are accepted; booleans, strings, functions and non-finite
numbers are rejected. Lists can be inputs, but the final statement must produce
a finite scalar. Multiline lists, comments and a single Python Markdown fence
are supported. Keyword arguments are rejected rather than silently ignored;
use positional arguments such as `round(value, 2)`.

Any syntax/evaluation/validation error stops execution and returns:

- `success=False`
- `environment={}`, `result=None`, `result_name=None`
- `errors` with line, type and message; `trace` is diagnostic only

Successful runs preserve the original `environment` and `trace` keys and add
`result`, `result_name` and an empty `errors` list. Zero and negative scalars are
valid results. Anonymous final expressions use `_result` and are included in
synthesis input. Values are not prematurely rounded to two decimal places.
Error line numbers refer to the cleaned code (outer fence/blank padding removed).

The app's actual math-response handler now passes only completed executions to
model synthesis. Failure produces a static TR/EN calculation-failure message,
with no model fallback and no partial numeric answer. The prompt also tells the
model to preserve calculated numbers and not invent units or strategic claims.

## Validation

```bash
python -m unittest test_dynamic_math test_baseline_regressions test_resource_metrics test_math_response -v
```

42 tests: **40 pass, 2 expected failures**. Nine new executor checks were run
against the prior implementation first and exposed the failures. Added result
presentation checks and integration tests exercise the real app handler with
stubbed model streaming: failed arithmetic makes zero model calls; successful
anonymous expressions reach synthesis. The original partial-math regression
is now a normal passing test. CI includes all four offline modules.

## Scope and remaining work

Success certifies completion of this restricted arithmetic program, not that
the model selected correct source values, units, fiscal year or formula. This
uses Python numeric arithmetic, including floating point; it does not promise
unlimited decimal precision. Execution time/resource limits remain a separate
hardening task. A single numeric assignment can be a valid result; semantic
correctness against the question requires independent evaluation.

No real Foundry model session, UI launch or vector DB rebuild was performed.
The two tracked unresolved regressions are the broad water route overriding
calculator routing and the Xbox domain blacklist. Requested-year routing,
source extraction, benchmark independence and ingestion safety remain pending.
