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

## Real lower decisions and structural relations

A lower contract needs a source, real Python homes and a complete supported partition before it can supply verified inputs. The upper adapter must use those inputs and call the real upper function; listing `uses` alone is not a check. FlowGuard combines all verified lower inputs jointly, including nested uses, so two details that matter only together are not checked merely one at a time. A supported closed boolean/enum domain can be exhausted. An open numeric/date domain uses all verified partition representatives, not every value in the domain; the result identifies this scope. If an upper result still depends on hidden lower detail, strengthen or split the lower contract rather than declaring it equivalent.

These relations describe actual decisions, not a model tree to maintain for every task. Put source dependency, ownership or write-location constraints in a sourced `structure_rule` at the module that owns them. Its predicate returns violating source rows or nodes from the shared Map; it does not duplicate a behavior oracle. Keep ordinary tests for behavior outside these declared relations. Constrain intentional architecture, not incidental inline syntax: when a valid refactor preserves the real behavior but breaks a shape-based rule, retire or correct that rule instead of restoring duplicated code.

## Source map coverage

Python, JS/JSX, TS/TSX, C, C++ and C# feed the same Map, fingerprints and fixed queries. Foreign readers provide declarations, call sites, dependency declarations, assignments and definite keys; grammar packages install normally and load only for files in that language. Behavior homes and real input execution remain Python only. Unknown external dependencies, dynamic/macro dispatch, overloads and build-dependent bindings retain reasons. A parse is not a compiler, runtime execution or a proof that no behavior was missed.

Inspect `graph.capabilities()` for actual files, parser errors and supported queries. `graph.query_coverage()` reports only the queries actually used, including `symbol_reads` when `calls(include_reads=True)` is requested. `functions()` tracks node coverage; assignments and keys are tracked too. Optional scopes such as `graph.handlers(language="python")` are appropriate only for requirements about Python. Unsupported language filters fail explicitly. Foreign handler, literal-set, test-discovery and complete symbol-read coverage are unavailable in this first batch. An unsupported/failed query or a predicate that queried no source cannot produce a successful structure check; it stays grey. Source contents, reader/grammar versions and project parsing configuration invalidate the same cached facts. Direct library callers can use `reset_query_coverage()` to start another predicate's scope; normal structure checks do this independently.

## Sources and execution

`owner R1` cites actual archived words stored once with `req add`. Never store this tutorial or an AI plan as owner words. Document sources require actual quoted words and an `authority_docs` entry; new jointly written sources stay visible as green*. `assumed:` and `lesson:` do not create owner authority. A valid archive proves bytes, not the correctness of an interpretation.

`check --all` runs ordinary pytest and records complete test-to-code links; local `check` refreshes selected tests. Direct pytest avoids general tracing of unmarked ordinary tests; marked guards still record their real homes. Missing dependencies select conservatively. External execution with unverified inputs remains open and reruns; package identity alone is not a purity model. Keep module initialization effects, and distinguish a referenced function identity from actually running its body. A no-change check can still rerun an open test. Links contain functions and call locations, not boundary values. Necessary collection work has a cost; current source and real execution are correctness requirements.

The CLI and initialized pytest prepare project imports automatically. For direct library use, load before project imports and treat a Model/Engine as a fixed source snapshot. Unknown preloaded project modules require a fresh verification process; live SDK objects and external dependencies are not hot-reloaded.

A project can retain its skip contract with `[tool.flowguard] skip_policy`: `platform` (default) permits effective platform skipif/xfail markers; `no_skip` refuses skipped/xfail outcomes; `forbid` also refuses XPASS and early success exits in plain pytest. An acceptance check never treats collection or an early process exit as completed testing. This is a project setting, not a step to repeat for every change.
