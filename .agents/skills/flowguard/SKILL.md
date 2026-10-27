---
name: flowguard
description: "Start software changes from the living map, executable models and bound tests; extend the owner and verify affected checks."
---

# FlowGuard

## Start from the model

Read `python -m flowguard read` before source. No map: `map scan`; `references/first_map.md`. Install only `git+https://github.com/liuyingxuvka/FlowGuard.git@<tag>`; tests need pytest>=8.

1. **node**: one tree rooted at system.
2. **parent**: `parent`/`PARENT`; omitted: inferred, shown by read.
3. **port**: computed from the model file; the AI writes OUTPUTS, HANDOFF, READS_PARENT, KEEPS, DISPATCH (see The tree).
4. **field**: `read --field`.
5. **rule/counterexample**: condition/breaking trace.
6. **known-bad**: must be rejected.
7. **anchor/USES**: owned/consulted code.
8. **test**: `TESTED_BY`; same tree, subtree shards.
9. **flow**: entry-to-result path.
10. **layer/dependency**: allowed calls.
11. **target**: old model → target → code; `.flowguard/target/`.
12. **locate → model → port changed? → parent and consumers**.

Models, tests and code grow together. Split a model that is too big, staged or dispatching: its stages or branches become a coarse parent with children, different aspects and shared parts become separate models; never a parent only to group models. Split a test file that is too big or mixes models along the models it tests; a file that tests only one model splits with it. map check warns at the soft limits and refuses at the hard ones; time is advice. Every model has rules and known-bad variants that must fail. It binds code once it describes code that exists (a process model with no code yet carries a model_anchor_missing debt with its reason) and binds tests once tests exercise it (a model without tests carries an unbound_models debt with its reason); a bound test feeds the model's entry seeds into the real entry and checks its exits. A test may have no model.

## The loop

1. `python -m flowguard read --find <words | path:function | path::test>` → deepest owner.
2. Code only: edit; `python -m flowguard change --run`; re-read stale owners/update changed descriptions; `python -m flowguard map confirm <ids>`; commit.
3. Model change: `python -m flowguard target start "<goal>"`, `python -m flowguard target add <model>`; edit its `.flowguard/target/models/<model>.py` copy.
4. `python -m flowguard target check`: fix ERROR; `port_changed_parent_missing`: add/receive in the parent. Before code: `EXPECTED GAP`; except `moved rules only` or `NO GAP` (no code for that rule; commit `records existing behaviour: <rule>`). Commit the target if planned.
5. Write code and bound tests; check until no TO-DO remains.
6. `python -m flowguard target promote`: one full check; its `map confirm`; commit code/models/map.

change and target promote run a test with a model only when the test is in that model's TESTED_BY or calls the changed function directly; a test that checks a model through the command line must be bound, or only CI runs it (the also reached: line counts them).

## Routes by task

`code` = loop step 2; `target` = steps 3-6 with every model the row names. A row that a printed line starts is done when that line is gone. Steps per row: `references/routes.md`.

| Task, or the line that starts it | Route | Do |
| --- | --- | --- |
| New function | target | extend, independent sibling or exclusive child; no owner: component; model-named tests |
| `large_model` (WARN over 8 rules or 2,000 sequences, ERROR over 12 or 10,000), `child_unconnected`, `parent_field_uncovered`, `keeps_not_orchestration`, `dispatch_*` | target | one target; exclusive stages/branches; one branch per call |
| `large_test_file`, `test_file_mixes_models`, `test_file_not_split` | target | move tests and `TESTED_BY` paths by model |
| `port changed ... -> verify X`, `port_changed_parent_missing`, a hub listed by read --review | target | `target add X`; receive/map; hub: add ripple |
| Rename or retire a field; `consumes`, `mentions`, `nothing produces`, `promises: -...` | target | `read --field <name>`; open sites; restore or explain each `-` |
| Move or split code | code; target if a file changes owner or an anchor moves | clear ownership/anchor errors |
| Remove a function | target | `remove:`; explain removed promises |
| Bug a green model missed | target | escaped known-bad, `EXPECTED GAP`, one bound regression |
| External promise (command, API, UI action) | target | owner, anchor or reasoned `NOT_MODELED`; no silent fallback |
| UI journey; all bad inputs of a finite boundary | target | `template ui-journey`; `template validator` |
| Model before code (a process or preset) | target | rules, known-bad, reasoned debt; anchor on `debt_stale` |
| `model_edited_outside_target` | target | `target add <model>`; redo there |

When a model or check stopped a wrong edit, add `Caught-by: <model or check>` to the commit message.

## The tree

- Node: `system`, a component in `.flowguard/map.json` or a model in `.flowguard/models/`; a failing model shows its counterexample: the trace that breaks a rule.
- Parent: `system` > component > model > child model; write `PARENT` (a component, a model id or `system`). Different aspects are separate models; a model that uses another's result names it in `HANDOFF`. Split a model when it is too big or holds one function's stages or alternatives: a coarse parent keeps the order, conditions and aggregation (alternatives: `DISPATCH` names one branch child each), each child hands its result up through `OUTPUTS`, and the parent receives every value into one of its fields (`HANDOFF`), gives each field to a child (`READS_PARENT`, `HANDOFF`) or `KEEPS` (inputs, markers, aggregates), and never re-checks a child's detail. Never create a parent only to group models. `map check` and `map models` fail on any unaccounted value or field. Tests follow the same tree (`TESTED_BY`).
- Known-bad: `broken_variants()` in every model; each one must fail, and `release` fails when a rule is broken by none.
- Real binding: `IMPLEMENTED_BY` anchors that `conformance()` replays against the real code; component `files` and `entrypoints`.
- Test binding: `TESTED_BY` names real tests for each rule; they must pass and reach the anchored code (`map models --tests`).
- Readback: `python -m flowguard read` (`--component <id>`, `--mermaid`, `--target`).
- Current vs target: `.flowguard/models/` and the components, files, dependencies, entrypoints, flows, layers and parents in `.flowguard/map.json` are the current model and change only through `.flowguard/target/` (`target start`, `target add`); every model change must show its expected gap in `target check` and becomes current only through `target promote`, which runs the one full check and prints the `map confirm` to run before the commit. The settings `ignore`, `import_roots`, `accepted_debts`, `large_model_seconds` and `large_test_seconds` are edited directly in `map.json`, with `python -m flowguard map check` before and after.

## First map, review and release

Hubs: `read --review`, `references/architecture_review.md`. `python -m flowguard release`; whole suite: `release --shards N` (hash without durations). Writing: `references/model_recipes.md`; templates: `references/node_kinds.md`.

## Honesty rules

`confirm` records description, never proof. Report actual results; never weaken checks for time or reuse verdicts. `NOT_MODELED`, process models and accepted debts need reasons. Fix `debt_stale`; review `promises:` and `moved`.
