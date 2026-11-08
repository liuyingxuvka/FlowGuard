# Moving from FlowGuard 3.x to 4.0

This is a major-version migration because supported execution and CLI behavior changes. It is not a major version merely because internal code was rewritten. The source comments, rule predicates, literal rows, sources and immutable owner-word records retain their original meaning and bytes. This guide describes the target 4.0 contract; release evidence belongs to its exact source commit and successful complete CI.

## What changes

| Earlier surface | 4.0 behavior and migration |
| --- | --- |
| Observation through child Python processes and nested pytest sessions | One runtime observes the current test process. Safe sensors replay at the real call; scenarios rerun a collected item in the same session with fresh function fixtures. |
| A marked guard reached its target only in a child process | That target is not observed. A missing required guard cannot claim coverage. Keep the ordinary subprocess test for its own assertions and add an appropriate same-process test for the observable owner. Do not invent child readings or reuse an old receipt. |
| An impure sensor had a passing calibration test | The test still runs normally, but a passing test does not make repeated writes safe. Unsafe sensor replay stays grey. Put events/state readings around the real effect and connect them through a Flow relation and the existing independent rule. |
| A tested project shadowed the SDK's `flowguard` namespace and relied on isolated re-import | The observer no longer launches a separate interpreter to import another SDK. Use an unambiguous test/package namespace or an ordinary external integration test; unavailable binding stays grey. |
| `check --diagnose`, diagnostic JSONL and built-in `CHECK_PIPELINE` | Retired. Normal tests report the three signals. Optional `show`, `try` and `watch` use current anchors and historical observations. A project's own rule may still use that identifier; there is no implicit built-in graph. |
| `--shard` and `--shard-report` | Retired. CI runs complete unsharded checks on Linux Python 3.11/3.13 and Windows Python 3.12. One partial run is never treated as complete evidence. |
| Default static source-path proof in a Flow check | Frozen. The verdict checks observed anchor paths and the declared finite model. Unwalked model edges stay grey and an observed forbidden path is red; unexecuted source routes remain unverified. Direct static SDK helpers retain only their explicit source scope. |
| Ordinary execution footprints, trace ledgers and batched contract cuts | Retired. One Map-owned function/file dependency summary selects a single real test session. Closed unchanged evidence retains its original result and scope; unknown inputs rerun. File-level selection can recheck more than the former call-level selector. Marked guards still require real in-memory source observations. |
| Partial pytest omitted the Flow intent item | Actual anchor events still check their Flow relations and sourced rules. This observed-only result is explicitly incomplete and does not create a full collection receipt or prove lower contracts. |
| `check --all` with collection-only or selection filters | The real pytest entry rejects an incomplete collection with its native usage-error exit, before ordinary tests can masquerade as a complete run. |
| Foreign grammars were mandatory | Python is the base map. The unchanged foreign readers are frozen behind the `languages` extra; unavailable grammars stay explicit. |
| Legacy `flowguard.intent` module entry | Use the single supported `python -m flowguard` entry. |
| Repository test helper imported as `flowguard.testing` | It belongs to the tests rather than the installed product. Keep such helpers in your own test suite; FlowGuard's copy is now `tests/route_text_support.py`. |

The safety gate is conservative, not a proof of all possible effects. It checks calls statically and rechecks the original values. Unknown operations, unavailable fixtures, ambiguous target invocations and unsupported contexts remain unverified. An unchanged result from one context does not establish every database, filesystem or concurrent state.

Direct SQLite replay supports only literal reads from an ordinary main table, optionally with a verified numeric equality parameter. It rejects visible Python callbacks, converters/adapters and unsupported SQL rather than treating any `SELECT` as pure. Numeric storage-class validation can scan the current condition column; it is not cached across changing database states. Use actual scenario readings for more complex contexts. Arbitrary extensions or hidden native hooks are outside this restricted proof scope.

## Preserve inputs, rebuild observations

1. Keep original-word files byte for byte. Keep every useful independent rule, literal row, expected result and real negative control. Full source comments continue to work; the shortest sensor comment is `# flowguard: sensor NAME`.
2. Compare each old binding with its real current function or test. A function input is varied; a context object stays with the real call. Confirm names, meanings and units. Give different policies different anchor names and a sourced `distinct` where appropriate.
3. For context-dependent sensors, name one real ordinary test in `calibrated_by`, with its parameter ID. The complete original test and cleanup must pass, and original-value checks must agree. For effects, retain the ordinary scenario and its actual readings instead of copying its answer into an adapter.
4. Rebuild generated maps and observation caches from the unchanged source inputs. Historical logs, digests and old green records are not converted into fresh evidence. `.flowguard/requests/` and old `.flowguard/models/` are not rewritten by this migration.
5. Run the ordinary tests. Review changed outcome classes, inconsistent same-name sensors and sourced rule violations. Compare every known old counterexample; a formerly unverified green must become red or grey, never silently disappear.
6. Run the complete suite with an environment outside the project, then require complete `ci.yml` success on that exact main commit before publication. Keep historical commits, tags and releases.

The default is now “run tests, read FlowGuard's few lines.” With no source change, output stays quiet unless a constraint fails. An optional session brief remembers the task baseline; `check --base COMMIT` selects another comparison baseline explicitly. Comparison reports supported classes, not every value in an open domain. Independent source words and tests still matter because code and model can share the same mistaken interpretation.

## Optional inspection

`python -m flowguard show NAME` reads a rule or recorded anchor/model observations. A model view labels actual node/edge counts, invalid paths and unobserved edges. History is never a fresh verification.

`python -m flowguard try ACCEPT days=4` checks an exact input. `--grid` prints every evaluated representative. Context comes from the real test; incomplete partitions remain grey.

`python -m flowguard watch -- python app.py` records a normal Python run and checks its declared models, retaining the target's exit status. Unsupported commands are refused without running them.

`python -m flowguard model draft PUBLISH` proposes nodes and edges from recorded paths. Review required paths, existing state transitions and reading relations; a draft is unverified. Layers have no fixed depth limit, but cycles remain grey and each layer should remain small.
