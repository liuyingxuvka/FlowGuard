# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[中文说明](./README.zh-CN.md)

FlowGuard helps a coding AI find an existing decision and keep necessary copies consistent across later changes. The code map is generated. Write a rule only when a decision has copies, the owner says "everywhere", or a bug was fixed. Ordinary edits use ordinary tests.

## Start

Install from this repository; the similarly named PyPI project is different. Python 3.11 or newer is required.

```bash
python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git"
cd your-project
python -m flowguard show "who may accept an order"
python -m flowguard init
python -m flowguard req add owner-message.txt --id R1
```

`show` reads source without importing the application. Reuse an existing owner where possible. `init` adds the pytest sentinel, a CI fragment and four project rules; it does not build a model of the task. Preserve actual owner words once, byte for byte.

## One rule, every necessary copy

A rule states an expectation independently of the implementation. A source anchor connects the real function. A literal row preserves a known regression. The [local rule guide](./.agents/skills/flowguard/references/rules.md) contains a complete two-anchor example and is copied with the skill.


After either copy changes, `check` executes ordinary pytest against the current source. A disagreement is red. An unverified boundary is grey. A newly written authority document may be green*; it is not independent confirmation.

## Source map and language boundaries

The same generated map and fixed queries read the first languages below. Normal installation includes their grammar packages; a parser loads only when its language is present. Mapping source does not execute or compile it.

| source | map facts | executable behavior anchors |
| --- | --- | --- |
| Python | Declarations, calls, dependencies, reads/writes and fixed queries | Python functions |
| JS/JSX, TS/TSX | Declarations, call sites, imports/reexports, assignments and definite keys | Unavailable |
| C, C++ | Declarations, calls, includes, assignments and definite keys | Unavailable |
| C# | Declarations, calls, using declarations, assignments and definite keys | Unavailable |

`capabilities()` reports actual files, parser errors and query support. External dependencies, dynamic dispatch, macros and ambiguous bindings stay explicit; a parsed grammar is not full semantic coverage. Foreign handler, literal-set, test-discovery and full symbol-read queries are not yet supported. A structure rule using an unavailable query, a failed source, or no source query is grey. Use an explicit language scope only when it matches the requirement; do not exclude inconvenient files to obtain green. Source, reader/grammar versions and project parser configuration invalidate cached facts. See the [intent guide](./docs/intent-guide.md) for a small source query.

## Daily commands

| command | purpose |
| --- | --- |
| `python -m flowguard` | Read a short cached screen when the project has rules; run no tests. |
| `python -m flowguard show "what it decides"` | Find a decision owner and static candidates before adding another copy. |
| `python -m flowguard show WINDOW` | Read the rule, sources, anchors and complete findings. |
| `python -m flowguard show --draft orders:accept` | Locate an existing calibration test; do not invent its expected answer. |
| `python -m flowguard check` | Recheck affected rules and tests with ordinary pytest. |
| `python -m flowguard check --all` | Run all intent and ordinary project tests in CI. |
| `python -m flowguard req list` | List preserved owner messages; `show R1` reads the original. |

Without rules, a check is quiet:

```text
FlowGuard check: no intent rules.
```

Cases remain literal and do not silently shrink. Sources, helpers, data and implementation changes invalidate dependent results. Necessary copies are bound explicitly; candidate similarity alone never proves equivalence. `check --all` records test-to-code links for the complete suite; local `check` refreshes selected tests. These links support affected-test selection and point anchors to existing calibration tests. With plain pytest, unmarked ordinary tests avoid general tracing; marked guards still record their code links. When links are missing, source dependencies select conservatively. Complete collection does more work to preserve those real links. Ordinary checks reuse results within their supported closed input boundary. Unverified external imports or calls rerun; an installed package version alone does not establish purity. Module initialization remains a dependency, while retaining a function object does not by itself execute its body. Open inputs can require a rerun even when source files have not changed.

## Boundaries and migration

Rules check declared inputs and real bindings, not factual truth or every behavior of the application. Grey findings explain what was not verified. Keep ordinary tests and review. Use `distinct` for similar decisions that must differ, `supersedes` for a replacement, and `uses` only where a lower decision genuinely simplifies the upper rule.

For real decomposition, a scenario relation connects actual lower and upper readings; the engine derives the binding and supplies verified lower inputs. Checks combine all verified lower inputs jointly, including nested uses. Closed boolean/enum domains can be finite and complete; open domains use supported partition representatives, not every value. Put dependency or ownership constraints in a sourced `structure_rule` at their existing owner. There is no requirement to model the whole application or add another hierarchy layer.

The old flow machines, background jobs, pictures and release test runner are retired. `status`, `where`, `draft`, `decide` and `release` have no compatibility aliases. Keep the original request archive; retain useful contracts as rules and rows; this release leaves `.flowguard/models/` unchanged. See the [intent guide](./docs/intent-guide.md) and [migration guide](./docs/upgrade-3.0.md).

## Repository

- `flowguard/structure/`: generated code map and fixed source queries.
- `flowguard/intent/`: rules, anchors, small flows and the pytest integration.
- `flowguard/map/`: shared source and immutable original-word readers.
- `.agents/skills/flowguard/`: the single public skill.
- `tests/`: ordinary controls and the project's own intent rules.

License: MIT

Source anchors replace `.home` and custom adapters in 3.0. Pure judgments execute directly; effects use an ordinary calibration test and actual readings. Small layered flow models check supported source paths and observed order. Missing or unsupported paths remain grey. See the [3.0 migration](./docs/upgrade-3.0.md).
