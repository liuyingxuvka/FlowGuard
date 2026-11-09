# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[中文说明](./README.zh-CN.md)

FlowGuard helps a coding AI compare real behavior before asserting requirements. Ordinary tests show three signals: what changed, which copies should have changed together, and which independent rule was violated. The generated code map helps find an existing owner before adding another implementation.

Run the project's tests and read the few FlowGuard lines. A source change reports supported old/new outcome classes; same-name sensors must agree; a sourced rule supplies the intended answer. No source change stays quiet unless a constraint fails. Rules and optional small models retain important decisions across later sessions. This does not establish general productivity or token savings; the earlier optional-use trial did not demonstrate a benefit. See [4.0 migration](./docs/upgrade-4.0.md) for the changed execution boundary.

## Start

Install from this repository; the similarly named PyPI project is different. Python 3.11 or newer is required.

```bash
python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git"
cd your-project
python -m flowguard init
python -m pytest
```

`init` enables the pytest plugin and adds the collection sentinel, CI fragment and four project rules. It does not build a model of the development task. Source navigation uses `show "what it decides"`; optional model views load the requested model. Preserve original words once only when a rule cites them, byte for byte.

## One rule, every necessary copy

A rule states an expectation independently of the implementation. A source anchor connects the real function. A literal row preserves a known regression. The [local rule guide](./.agents/skills/flowguard/references/rules.md) contains a complete two-anchor example and is copied with the skill.


The shortest anchor is `# flowguard: sensor NAME` above a real function. Parameters are inferred as inputs or context; confirm their meaning and units. Necessary copies use the same name. A missing function or contradictory declared signature is red; unavailable readings stay grey. A newly written authority document may be green*; it is not independent confirmation. The original full comment syntax and literal rows still work.

## Source map and language boundaries

The base installation maps Python without foreign grammar packages. For the frozen readers below, install the optional extra: `python -m pip install "flowguard[languages] @ git+https://github.com/liuyingxuvka/FlowGuard.git"`. A parser loads only when its language is present; a missing grammar reports that reader as unavailable. Mapping source does not execute or compile it.

| source | map facts | executable behavior anchors |
| --- | --- | --- |
| Python | Declarations, calls, dependencies, reads/writes and fixed queries | Python functions |
| JS/JSX, TS/TSX | Declarations, call sites, imports/reexports, assignments, definite keys, Prisma writes and reads, catch fallbacks, decision literals and compared constant names, table lookups, declared value sets and body shapes | Minimal, vitest only (ESM): module-level functions; jest projects get static checks only |
| Prisma schema, SQL files | Models, tables, columns (`@map`, `@@map`, `[bracketed]` names), relations with `onDelete`, `CHECK (col IN (...))` sets | Not code |
| C, C++ | Declarations, calls, includes, assignments and definite keys | Unavailable |
| C# | Declarations, calls, using declarations, assignments and definite keys | Unavailable |

`capabilities()` reports actual files, parser errors and query support. External dependencies, dynamic dispatch, macros and ambiguous bindings stay explicit; a parsed grammar is not full semantic coverage. In a TS/JS project, `python -m flowguard check --static` runs the map checks without pytest and prints them as an ordinary test run would: the fallback ledger, writes outside a data owner, registered pairs, values outside a declared set, deletes that leave restricting children, columns one description lacks, new label spellings, old values still spelled elsewhere and unchanged look-alikes of a changed function; it exits 1 on red. `init` with a `package.json` writes a vitest (or jest) test that runs it, so the result appears in `npm test`. For vitest, `init` also writes `flowguard.vitest.mjs` and adds two lines marked `flowguard: vitest` to the vitest config (delete them to undo). With no TS/JS change against the task baseline it adds nothing; otherwise vitest wraps the module-level functions marked `// flowguard: sensor NAME` and the functions this change edited, records their calls, replays each call on representative values (the constants the function compares with, also through constant names and imports, and the keys of the tables it looks up), runs the baseline source and same-name copies on the same inputs, and prints the same changed classes, copy and rule reds as pytest after the summary. A replay refuses file writes, processes, network and threads; a function whose code or arguments involve a database client is never replayed. jest, CommonJS configs, class methods and async results stay static or grey. Outside a vitest run TS/JS code is never executed; its calls are resolved by name. Foreign literal-set, test-discovery and full symbol-read queries are not yet supported; the C, C++ and C# readers stay frozen. A structure rule using an unavailable query, a failed source, or no source query is grey. Use an explicit language scope only when it matches the requirement; do not exclude inconvenient files to obtain green. Source, reader/grammar versions and project parser configuration invalidate cached facts. See the [intent guide](./docs/intent-guide.md) for a small source query.

## Daily commands

| command | purpose |
| --- | --- |
| `python -m pytest` | Run normal tests and read the three FlowGuard signals, at most ten lines. |
| `python -m flowguard` | Read a brief of at most ten lines and remember this task's baseline commit; run no tests. |
| `python -m flowguard show "what it decides"` | Find a decision owner and static candidates before adding another copy. |
| `python -m flowguard show WINDOW` | Read a rule or recorded anchor/model observations; history is labelled as history. |
| `python -m flowguard try ACCEPT days=4` | Explore one source-bound input; context comes from its real test. |
| `python -m flowguard try ACCEPT days=4 --grid` | Print every evaluated representative; incomplete partitions remain grey. |
| `python -m flowguard watch -- python app.py` | Record a real Python run and check its models. |
| `python -m flowguard model draft PUBLISH` | Propose nodes and edges from observed paths; requirements still need review. |
| `python -m flowguard check` | Recheck affected rules and tests with ordinary pytest. |
| `python -m flowguard check --all --deep` | Run all intent and ordinary project tests, decision probes and mutation checks in CI. |
| `python -m flowguard req list` | List preserved owner messages; `show R1` reads the original. |

Without rules, a check is quiet:

```text
FlowGuard check: no intent rules.
```

Cases remain literal and do not silently shrink. Supported partitions are evaluated in full, without a fixed class cap. A single runtime observes real calls, replays safe input classes in the same context and rechecks the original values. Scenarios rerun their collected ordinary test in the same session with fresh function fixtures. Observation does not start child Python processes or nested test sessions. A calibration test does not make writes safe to replay. Keep effectful business behavior in the ordinary test and connect its actual readings with a flow relation. Function fingerprints support incremental selection; unresolved imports, external inputs or unavailable fixtures cause conservative reruns or grey findings. A changed anchor's comparison is computed once and then reused while its fingerprint stays the same: the function's body and the project functions it calls, the values of the constants they read, the call's arguments and the baseline; a function that reads anything the map cannot see is compared again on every run. Similarity is a clue, not equality evidence.

## Boundaries and migration

Rules check declared inputs and real bindings, not factual truth or every behavior of the application. Grey findings explain what was not verified. Keep ordinary tests and review. Use `distinct` for similar decisions that must differ, `supersedes` for a replacement, and `uses` only where a lower decision genuinely simplifies the upper rule.

For real decomposition, a scenario relation connects actual lower and upper readings; the engine derives the binding and supplies verified lower inputs. Checks combine all verified lower inputs jointly, including nested uses. Closed boolean/enum domains can be finite and complete; open domains use supported partition representatives, not every value. Put dependency or ownership constraints in a sourced `structure_rule` at their existing owner. There is no requirement to model the whole application or add another hierarchy layer.

The old flow machines, background jobs, pictures and release test runner are retired. `status`, `where`, `draft`, `decide` and `release` have no compatibility aliases. Version 4 also retires the diagnostic/shard CLI and its separate check-pipeline recorder. Child-only guard execution is no longer observed. Keep original requests, useful rules and rows; rebuild generated observations from real tests. See the [intent guide](./docs/intent-guide.md) and [4.0 migration](./docs/upgrade-4.0.md).

## Repository

- `flowguard/structure/`: generated code map and fixed source queries.
- `flowguard/intent/`: rules, anchors, small flows and the pytest integration.
- `flowguard/map/`: shared source and immutable original-word readers.
- `.agents/skills/flowguard/`: the single public skill.
- `tests/`: ordinary controls and the project's own intent rules.

License: MIT

Source anchors replace `.home` and custom adapters. Small layered models relate nodes, edges, state transitions and real readings. Missing or unsupported paths remain grey; a model can share an AI's mistaken interpretation, so keep independent tests and source words.
