---
name: flowguard
description: "Use for software codebases: one living model tree of the software (map, executable models and tests bound to the real code), with a current model and a target model for planned changes; put new code in the right owner and verify only what a change affects. Not for story, trip or world models; use worldguard."
---

# FlowGuard

The current model is `.flowguard/map.json` plus `.flowguard/models/`: owners, files, responsibilities, state, side effects, dependencies, tests and executable contracts. Confirmed components store file fingerprints; changed code becomes STALE until re-read and confirmed.
The target is `.flowguard/target/`: one planned change at a time, committed beside the code; git keeps history. Existing user-written `.../run_checks.py` runners stay registered in component `models`.
Commands: `python -m flowguard read | change | release | template | target` and `python -m flowguard map <command>`.
Install the engine only from GitHub: `python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@<tag>"`; the PyPI package named `flowguard` is a different project.

## Every session

1. `python -m flowguard read` before opening source. Business data stays read-only; disposable caches may update.
2. Before adding behavior, `python -m flowguard read --find <words>`; extend the owner it names. Create a new component only when none owns the responsibility; give each new source file exactly one owner.
3. `python -m flowguard read --component <id>` to read that node's five facets; open only the files of the components you touch.
4. Does the task change behavior (a rule, input or external promise) or structure (components, file ownership, dependencies or layers)? Yes: target first below. No: follow **Change code only**.

## Change behaviour or structure: target first

1. `python -m flowguard target start "<goal>"`.
2. `python -m flowguard target add <id>` for each changed node. Write new nodes directly in `.flowguard/target/map.json` or `.flowguard/target/models/`; use the merged `.flowguard/models/` paths for model references. Target format: `references/map_format.md`.
3. Edit the target until `python -m flowguard target check` has no ERROR and only code/test TO-DO remains: the design is ready.
4. Write the code and tests until `python -m flowguard target check` has no TO-DO either.
5. `python -m flowguard target promote`, then `python -m flowguard map confirm <listed components>`; run `python -m flowguard change`, run its listed tests/models, and commit.
While working, `change` marks replaced nodes `moving to target`; other breakage stays ERROR. A green model that missed a bug follows this same route: `python -m flowguard target add <model>`, then add the escaped case as a known-bad variant; see "When a green model missed a bug" in `references/model_recipes.md`.

## Change code only

1. Edit the code, then `python -m flowguard change` (check + impact).
2. Fix every ERROR and BLOCKED binding. Common: `file_unmapped` (give the file one owner); `dep_undeclared` (declare a real layer-respecting dependency, otherwise move code or drop the import); `dep_unused` (remove it); `test_missing` (fix the tests pattern); `model_unbound` (register the runner with its owner); `anchor_broken` / `flow_step_broken` / `model_anchor_broken` (fix the name); `model_anchor_missing` / `model_conformance_missing` (bind the model; see The tree).
3. Run exactly the tests and models it lists; never claim a test passed unless you ran it.
4. For each REVIEW component, read the change, update `summary`/`responsibilities`/`state`/`side_effects` when needed, then `python -m flowguard map confirm <id>`.

## The tree

- Node: `system`, a component in `.flowguard/map.json` or a model in `.flowguard/models/`; a failing model shows its counterexample: the trace that breaks a rule.
- Parent: `system` > component > model; a model's `PARENT` names its parent model, else it sits under the component whose code it anchors.
- Known-bad: `broken_variants()` in every model; each one must fail, and `release` fails when a rule is broken by none.
- Real binding: `IMPLEMENTED_BY` anchors that `conformance()` replays against the real code; component `files` and `entrypoints`.
- Test binding: `TESTED_BY` names real tests for each rule; they must pass and reach the anchored code (`map models --tests`).
- Readback: `python -m flowguard read` (`--component <id>`, `--mermaid`, `--target`).
- Current vs target: `.flowguard/map.json` and `.flowguard/models/` are the current model; `.flowguard/target/` is the target, and `target promote` makes it current once `target check` shows no error and no to-do.

Nodes nest as `system` > component > model > child model. Each has purpose, rules, known-bad, code and tests: `read --component` prints them; `map models` prints the real rule and known-bad names.
Root `system` is the code-derived component graph: unaccepted cycles, upward layer imports and duplicate owners violate its invariants; `python -m flowguard map models system` generates bad edges, and `map check` is its conformance.
Anchors/`COMPONENTS`, `PARENT` and imports determine placement. `parent_unknown`, `parent_cycle`, `parent_import_mismatch`, `child_outside_parent` and `duplicate_child_owner` are ERRORs. A child slicing parent state declares `project_parent_state`; independent grouped checks need no projection.
`python -m flowguard read --mermaid` draws the tree (append `--component ID` to focus); `python -m flowguard read --target` shows target changes. `change` selects changed models, importers, ancestors and review children.
For retries, deduplication, idempotency, ordering, caching, concurrency, money, permissions or multi-step flows, model the behavior with known-bad variants and real conformance (`assets/model_template.py`, `references/model_recipes.md`); add models only when needed. `MODEL_ID` selects contract models, runner directory ids select runners; component ids select `read --component`. Unknown model ids fail.

## What you want to do

Most edits need none of these; each row is reached through the same tree and target flow.

| capability | use when | lives here now |
| --- | --- | --- |
| behavior-commitment | external promises need one owner, source and tests; no silent fallback | `references/domains/behavior-commitment/protocol.md` |
| architecture-reduction | shrinking or merging code without behavior changes | `references/domains/architecture-reduction/protocol.md` |
| code-structure | placing new code or splitting a module with its public surface intact | `references/domains/code-structure/protocol.md` |
| contract-exhaustion | enumerating every bad case or combination in a finite universe | `references/domains/contract-exhaustion/protocol.md` |
| field-lifecycle | changing fields, schemas, defaults, aliases or replacements | `references/domains/field-lifecycle/protocol.md` |
| model-mesh | fitting parent/child or producer/consumer models together | `references/domains/model-mesh/protocol.md` |
| model-test | checking rules, code and tests against one another | `references/domains/model-test/protocol.md` |
| topology-hazard | reviewing shared writers, repeated effects and future-use hazards | `references/domains/topology-hazard/protocol.md` |
| test-mesh | sharding a suite too slow for one command | `references/domains/test-mesh/protocol.md` |
| ui-flow | UI states, journeys, controls, cancel/recover and operability | `references/domains/ui-flow/protocol.md` |

Read only the matching protocol, not a chain of them. `python -m flowguard template --list`, then `python -m flowguard template <name> --write .` supplies starters; otherwise use plain modeling in `references/model_recipes.md`.

## First map of an existing project

Old `.flowguard/project.toml` integrations: follow `references/upgrade.md` first.
Use `references/first_map.md`: scan -> digest -> describe -> deps -> check -> confirm -> lint. `scan` bounds draft grouping; `python -m flowguard map discover` separately shows routes, commands, effects and state writers. Read digests, not whole files.

## Architecture review and release

Use `python -m flowguard map lint` (`references/architecture_review.md`). Routine checkpoints run the affected tests/models from `change`. At final release, freeze source and run `python -m flowguard release` and the full suite once on that revision; same-SHA CI can provide this evidence.

## Honesty rules

Keep `draft` when unsure; never invent anchors, owners or results; report what ran, failed and was skipped. The current model describes today's code; planned code belongs in the target, and history lives in git.
