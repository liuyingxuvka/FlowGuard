---
name: flowguard
description: Living, code-anchored map of a codebase plus executable models of its risky flows and 13 focused capability reviews. Use it to understand a codebase cheaply, put new code in the right owner, catch architecture drift and behavior bugs, and verify only what a change affects.
---

# FlowGuard

FlowGuard keeps, next to the code and committed to git:

1. **The map** `.flowguard/map.json`: components, what each one owns (responsibilities, state, side
   effects), files, entrypoints, dependencies, tests and models. A confirmed component stores a
   fingerprint of its files; when the code changes it becomes STALE until it is re-read and confirmed.
2. **Models**: executable `Input x State -> Set(Output x State)` models, either contract files
   `.flowguard/models/<id>.py` or model runners `.../run_checks.py` listed in a component's `models`.
   A model must pass for the intended design, FAIL for its known-bad variants, and (when it can)
   replay its traces against the real code (conformance).

Commands: `python -m flowguard read | change | release | template` and `python -m flowguard map <command>`.

## Every session

1. `python -m flowguard read` - the whole map (a few thousand tokens). Read it before opening source files. Business data stays read-only; disposable caches may update.
2. Before adding behavior: `python -m flowguard read --find <words>`; extend the existing owner. Create a
   new component only when nothing owns the responsibility.
3. Open only the files of the components you touch: `python -m flowguard read --component <id>`.

## After editing code

1. `python -m flowguard change` (check + impact).
2. Fix every ERROR; each message says what is wrong. Common: `file_unmapped` (add the file to one
   component), `dep_undeclared` (intended and layer-respecting: add to `depends_on`; otherwise move code
   or drop the import), `dep_unused` (remove that `depends_on` entry), `test_missing` (fix the `tests`
   pattern), `model_unbound` (add the runner to the owning component's `models`), `anchor_broken` /
   `flow_step_broken` / `model_anchor_broken` (update the name). BLOCKED lines name the missing binding.
3. Run exactly the tests and models it lists. Never claim a test passed unless you ran it.
4. For each REVIEW component: read the change, update `summary`/`responsibilities`/`state`/
   `side_effects` if behavior changed, then `python -m flowguard map confirm <id>`.

## Capabilities

Most edits need no capability. When a task matches a row below, read that one protocol:
`references/domains/<name>/protocol.md`. Starter files: `python -m flowguard template --list`, then
`python -m flowguard template <name> --write .`. Do not chain protocols. If none fits, use plain
modeling (`references/model_recipes.md`).

| capability | use when |
| --- | --- |
| existing-model | before changing behavior that an existing component or model may already own |
| behavior-commitment | external promises (API, CLI, UI, workflow) need one owner, a source and tests; no silent fallback paths |
| architecture-reduction | code may shrink or merge without changing behavior |
| code-structure | deciding where new code goes before writing it |
| contract-exhaustion | a finite input universe needs every bad case or combination enumerated |
| field-lifecycle | fields, schemas, defaults, aliases or replacements change |
| model-mesh | several models must fit together (parent/child, producer/consumer) |
| model-miss | a bug escaped although the model was green |
| model-test | rules, code and tests must be checked against each other |
| topology-hazard | a green model needs review for future-use hazards (shared writers, repeatable effects) |
| structure-mesh | splitting or refactoring a module while keeping its public surface |
| test-mesh | the whole test suite is too slow to run in one command (shard runner) |
| ui-flow | UI states, journeys, controls, cancel/recover, operability |

## Models for risky flows

Retries, deduplication, idempotency, ordering, caching, concurrency, money, permissions, multi-step
flows: write or update a model (`assets/model_template.py`, `references/model_recipes.md`), list it in
the component's `models`, run `python -m flowguard map models <MODEL_ID>` (runner: its directory id).
Component ids select `read --component`; model ids select `map models`. Unknown model ids fail.
`change` follows the complete caller closure; explicit `map impact --depth N` is truncated.
Static Python/relative JS/TS imports and literal lazy exports are supported.
Each declared edge needs an import, module literal or explicit debt reason; unsupported edges fail check.

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
