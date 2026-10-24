---
name: flowguard
description: "Use for software codebases: one living model tree of the software (map, executable models and tests bound to the real code), with a current model and a target model for planned changes; put new code in the right owner and verify only what a change affects. Not for story, trip or world models; use worldguard."
---

# FlowGuard

The current model is `.flowguard/map.json` plus `.flowguard/models/`: owners, files, responsibilities, state, side effects, dependencies, tests and executable contracts. Confirmed components store file fingerprints; changed code becomes STALE until re-read and confirmed.
The target is `.flowguard/target/`: one planned change at a time, committed beside the code; git keeps history.
Commands: `python -m flowguard read | change | release | template | target` and `python -m flowguard map <command>`. Templates: `adoption`, `behaviour`, `ui-journey`, `validator`.
Install the engine only from GitHub: `python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@<tag>"`; the PyPI package named `flowguard` is a different project.

## Every session

1. `python -m flowguard read` before opening source. Business data stays read-only; disposable caches may update.
2. Before adding behavior, `python -m flowguard read --find <words>`; extend the owner it names. Create a new component only when none owns the responsibility; give each new source file exactly one owner.
3. `python -m flowguard read --component <id>` to read that node's five facets; open only the files of the components you touch; add --budget N to see more.
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
2. Fix every ERROR and BLOCKED binding. Common: `file_unmapped` (give the file one owner); `dep_undeclared` (declare a real layer-respecting dependency, otherwise move code or drop the import); `dep_unused` (remove it); `test_missing` (fix the tests pattern); `runner_model` (a retired runner file: move its real checks into a contract model and delete the old file); `anchor_broken` / `flow_step_broken` / `model_anchor_broken` (fix the name); `model_anchor_missing` / `model_conformance_missing` (bind the model; see The tree).
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

Components can nest using an optional `parent`; models can nest under other models. Each node has purpose, rules, known-bad, code and tests: `read --component` prints them; `map models` prints the real rule and known-bad names.
Root `system` is the code-derived component graph: unaccepted cycles, upward layer imports and duplicate owners violate its invariants; `python -m flowguard map models system` generates bad edges, and `map check` is its conformance.
Anchors/`COMPONENTS`, `PARENT` and imports determine placement. `parent_unknown`, `parent_cycle`, `parent_import_mismatch`, `child_outside_parent` and `duplicate_child_owner` are ERRORs. A child slicing parent state declares `project_parent_state`; independent grouped checks need no projection.
`python -m flowguard read --mermaid` draws the tree, declared dependencies and flows (append `--component ID` to focus); `read --component` names dependency symbols and shows coverage; `python -m flowguard read --target` shows target changes. `change` selects changed models, importers, ancestors and review children.
For retries, deduplication, idempotency, ordering, caching, concurrency, money, permissions or multi-step flows, model the behavior with known-bad variants and real conformance (`python -m flowguard template behaviour --write .`, `references/model_recipes.md`); add models only when needed. `MODEL_ID` selects contract models; component ids select `read --component`. Unknown model ids fail.

## What you want to do

Most edits need none of these; each row is reached through the same tree and target flow. Templates are `adoption`, `behaviour`, `ui-journey`, `validator`.

| capability | use when | lives here now |
| --- | --- | --- |
| behavior-commitment | external promises need one owner, source and tests; no silent fallback | component `entrypoints` + a model's `IMPLEMENTED_BY` or `NOT_MODELED` (`entrypoint_owner`, `entrypoint_unmodeled`), recipe `references/tree_operations.md#External promise (no silent fallback)` |
| architecture-reduction | shrinking or merging code without behavior changes | tree operation `references/tree_operations.md#Remove or merge a node` (target `remove` + `CodeFacts.unreferenced`; `owner_dropped` stops a silent loss) |
| code-structure | placing new code or splitting a module with its public surface intact | tree operation `references/tree_operations.md#Add or split a component` (target components; `duplicate_owner` and `owner_dropped` keep one owner and every public entrypoint) |
| contract-exhaustion | enumerating every bad case or combination in a finite universe | node kind `validator` (`python -m flowguard template validator`; `references/model_recipes.md#Validator`) |
| field-lifecycle | changing fields, schemas, defaults, aliases or replacements | tree operation `references/tree_operations.md#Rename or retire a field` (target model state + `CodeFacts.absent` / `present`) |
| model-mesh | fitting parent/child or producer/consumer models together | tree operation `references/model_recipes.md#Split a model` (`PARENT` / `project_parent_state`; nesting errors `parent_unknown`, `duplicate_child_owner`, `child_outside_parent`; `flowguard.closure` for handoffs between children) |
| model-test | checking rules, code and tests against one another | the tests facet (`python -m flowguard read --component <id>`) and `python -m flowguard map models --tests` (`invariant_untested`, `tested_by_failed`, `tested_by_misses_anchor`); `references/model_recipes.md#Run the bound tests` |
| topology-hazard | reviewing shared writers, repeated effects and future-use hazards | computed facet: `hazard:` lines under each model in `python -m flowguard map models` (`references/model_recipes.md#Hazards`) |
| test-mesh | sharding a suite too slow for one command | tool: `python -m flowguard release --shards 4` (whole suite in parallel shards; every collected test runs exactly once within that suite) |
| ui-flow | UI states, journeys, controls, cancel/recover and operability | node kind `ui-journey` (`python -m flowguard template ui-journey`; checklist `references/model_recipes.md#UI journey`) |

`python -m flowguard template --list`, then `python -m flowguard template <name> --write .` supplies starters; otherwise use plain modeling in `references/model_recipes.md`.

## First map of an existing project

Old `.flowguard/project.toml` integrations: follow `references/upgrade.md` first.
Use `references/first_map.md`: scan -> digest -> describe -> deps -> check -> confirm -> lint. `scan` bounds draft grouping; `python -m flowguard map discover` separately shows routes, commands, effects and state writers. Read digests, not whole files.

## Architecture review and release

Use `python -m flowguard map lint` (`references/architecture_review.md`). Routine checkpoints run the affected tests/models from `change`. At final release, freeze source and run `python -m flowguard release --shards 4` once on that revision, or use successful CI for that exact source SHA.

## Honesty rules

Keep `draft` when unsure; never invent anchors, owners or results; report what ran, failed and was skipped. The current model describes today's code; planned code belongs in the target, and history lives in git.
