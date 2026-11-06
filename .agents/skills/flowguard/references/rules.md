# One rule and its real homes

Read this when writing the first rule. Ordinary edits do not need a model. Start with `show "what it decides"` and reuse an existing owner where possible.

## A complete small example

Use a throwaway project to try the example. Here `policy.txt` is the project's agreed policy; writing it with the rule produces green*, not independent confirmation.

`policy.txt`:

```text
At most three days.
```

`pyproject.toml`:

```toml
[tool.flowguard]
authority_docs = ["policy.txt"]
```

`orders.py`:

```python
def accept(days):
    return days <= 3


def preview_accept(days):
    return days <= 3
```

`tests/intent/window.py`:

```python
from flowguard.intent import rule, row

@rule("WINDOW", decides="acceptance window", fields={"days": int},
      source='doc policy.txt "At most three days."')
def WINDOW(days):
    """Accept at most three days, including the third day."""
    return days <= 3

WINDOW.rows(row(days=4, expect=False, why="the fourth day was incorrectly accepted"))

@WINDOW.home("orders:accept")
def api(c, fn):
    return fn(c.days)

@WINDOW.home("orders:preview_accept")
def preview(c, fn):
    return fn(c.days)
```

Run `python -m flowguard init`, then `python -m flowguard check`. Change only `preview_accept` to accept four days: the same check must turn red. The adapter builds inputs and calls real code; it does not calculate the expected answer. Keep each necessary copy bound to the same rule.

## Inputs and results

`rule` needs an ID, a `decides` key, typed `fields`, a `source` and an independent predicate. A row has literal inputs, `expect` and `why`; do not generate it from the implementation. Use `retired` to explain a case that no longer applies. A rule returning `None` has no opinion; `total=True` makes a decision gap an error. `Refused(ValueError, contains="...")` expects a real exception.

Booleans, closed enums, optionals, numbers, dates and durations have explicit cell handling. Supported linear expressions are exhausted; unsupported calls or nonlinear continuous boundaries remain grey. Green covers the declared domain and actual bindings. It does not prove factual truth, omitted requirements or every behavior of the program. `distinct` explains similar decisions that must differ; `supersedes` replaces a rule without silently losing applicable rows. Use `uses=[LOWER]` and `c.witness(LOWER)` only for a real lower decision.

## Sources and execution

`owner R1` cites actual archived words stored once with `req add`. Never store this tutorial or an AI plan as owner words. Document sources require actual quoted words and an `authority_docs` entry; new jointly written sources stay visible as green*. `assumed:` and `lesson:` do not create owner authority. A valid archive proves bytes, not the correctness of an interpretation.

`check --all` runs ordinary pytest and records complete test-to-code links; local `check` refreshes selected tests. Direct pytest avoids general tracing of unmarked ordinary tests; marked guards still record their real homes. Missing dependencies select conservatively. Links contain functions and call locations, not boundary values. Necessary collection work has a cost; current source and real execution are correctness requirements.

The CLI and initialized pytest prepare project imports automatically. For direct library use, load before project imports and treat a Model/Engine as a fixed source snapshot. Unknown preloaded project modules require a fresh verification process; live SDK objects and external dependencies are not hot-reloaded.

A project can retain its skip contract with `[tool.flowguard] skip_policy`: `platform` (default) permits effective platform skipif/xfail markers; `no_skip` refuses skipped/xfail outcomes; `forbid` also refuses XPASS and early success exits in plain pytest. An acceptance check never treats collection or an early process exit as completed testing. This is a project setting, not a step to repeat for every change.
