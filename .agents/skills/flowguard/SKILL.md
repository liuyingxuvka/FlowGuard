---
name: flowguard
description: "Use for software codebases: a living code-anchored map, executable models bound to the real code for risky flows, and 10 capability reviews, to put new code in the right owner and verify only what a change affects. Not for story, trip or world models; use worldguard."
---

# FlowGuard

FlowGuard keeps, next to the code and committed to git:

1. **The map** `.flowguard/map.json`: components, what each one owns (responsibilities, state, side
   effects), files, entrypoints, dependencies, tests and models. A confirmed component stores a
   fingerprint of its files; when the code changes it becomes STALE until it is re-read and confirmed.
2. **Models**: executable `Input x State -> Set(Output x State)` models, either contract files
   `.flowguard/models/<id>.py` linked by their literals, or runners `.../run_checks.py` registered in `models`.
   A model must pass for the intended design, FAIL for its known-bad variants, and stay bound to the
   real code (see Binding).

Commands: `python -m flowguard read | change | release | template` and `python -m flowguard map <command>`.
Install the engine only from GitHub: `python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@<tag>"`; the PyPI package named `flowguard` is a different project.

## Every session

1. `python -m flowguard read` - the whole map (a few thousand tokens). Read it before opening source files. Business data stays read-only; disposable caches may update.
2. Before adding behavior: `python -m flowguard read --find <words>`; extend the owner it names (it lists
   that owner's files, state and side effects). Create a new component only when nothing owns the
   responsibility; for a new file, `change` names the component that owns the files next to it.
3. Open only the files of the components you touch: `python -m flowguard read --component <id>`.

## After editing code

1. `python -m flowguard change` (check + impact).
2. Fix every ERROR; each message says what is wrong. Common: `file_unmapped` (add the file to one
   component), `dep_undeclared` (intended and layer-respecting: add to `depends_on`; otherwise move code
   or drop the import), `dep_unused` (remove that `depends_on` entry), `test_missing` (fix the `tests`
   pattern), `model_unbound` (add the runner to the owning component's `models`), `anchor_broken` /
   `flow_step_broken` / `model_anchor_broken` (update the name), `model_anchor_missing` /
   `model_conformance_missing` (bind the model, see Binding). BLOCKED lines name the missing binding.
3. Run exactly the tests and models it lists. Never claim a test passed unless you ran it.
4. For each REVIEW component: read the change, update `summary`/`responsibilities`/`state`/
   `side_effects` if behavior changed, then `python -m flowguard map confirm <id>`.

## Capabilities

Most edits need no capability. When a task matches a row below, read that one protocol:
`references/domains/<name>/protocol.md`. Starter files: `python -m flowguard template --list`, then
`python -m flowguard template <name> --write .`. Do not chain protocols. If none fits, use plain
modeling (`references/model_recipes.md`). A bug escaped a green model: follow "When a green model
missed a bug" in `references/model_recipes.md`.

| capability | use when |
| --- | --- |
| behavior-commitment | external promises (API, CLI, UI, workflow) need one owner, a source and tests; no silent fallback paths |
| architecture-reduction | code may shrink or merge without changing behavior |
| code-structure | deciding where new code goes, or splitting a module while keeping its public surface |
| contract-exhaustion | a finite input universe needs every bad case or combination enumerated |
| field-lifecycle | fields, schemas, defaults, aliases or replacements change |
| model-mesh | several models must fit together (parent/child, producer/consumer) |
| model-test | rules, code and tests must be checked against each other |
| topology-hazard | a green model needs review for future-use hazards (shared writers, repeatable effects) |
| test-mesh | the whole test suite is too slow to run in one command (shard runner) |
| ui-flow | UI states, journeys, controls, cancel/recover, operability |

## Models for risky flows

Retries, deduplication, idempotency, ordering, caching, concurrency, money, permissions, multi-step
flows: write or update a model (`assets/model_template.py`, `references/model_recipes.md`), set its
COMPONENTS (and PARENT when needed; register runners in `models`), run `python -m flowguard map models <MODEL_ID>` (runner: its directory id).
Component ids select `read --component`; model ids select `map models`. Unknown model ids fail.
`change` follows the complete caller closure; explicit `map impact --depth N` is truncated.
Static Python/relative JS/TS imports and literal lazy exports are supported.
Each declared edge needs an import, module literal or explicit debt reason; unsupported edges fail check.

## Binding

Every model has five abilities: a state model of its concern, counterexamples, known-bad variants, code and test binding.
Only the meta-capabilities (model-mesh, topology-hazard, model-test) inspect other models and tests and keep runners.
L0 is the map (one owner per file, STALE when its code changes). L1: `IMPLEMENTED_BY` (`path:Symbol`) and
`TESTED_BY` anchors resolve; `REPLACE_ME`, missing or renamed anchors are ERRORs, and `change` reselects the model and its tests.
Conformance is required: replay the real code (L2, only for risky flows) or compare it as code facts.
`DESIGN_ONLY = "<reason>"` only while the code does not exist. Build a model only when the task touches it.

## First map of an existing project

Old `.flowguard/project.toml` integrations: follow `references/upgrade_from_0_69.md` first.

`references/first_map.md` (scan -> digest -> describe -> deps -> check -> confirm -> lint). `scan`
bounds draft grouping; `python -m flowguard map discover` separately shows routes, commands, effects and state writers. Read digests, not whole files.

## Architecture review and release

`python -m flowguard map lint` (`references/architecture_review.md`). Routine checkpoints use the
affected tests/models from `change`. At final release freeze the source: run `python -m flowguard
release` and the full suite once on that revision; same-SHA CI can provide this evidence.

## Honesty rules

Keep `draft` when unsure; never invent anchors, owners or results; report what you ran, failed and
skipped. The map describes the current code; history lives in git.
