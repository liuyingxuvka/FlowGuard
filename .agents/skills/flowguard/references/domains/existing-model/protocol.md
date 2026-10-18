# Existing Model Preflight
Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.
Before you change behavior, find out which component or model already owns it.
This capability catches the "parallel second owner" bug: an agent adds a new
scheduler, store, handler or model for something an existing component already
does. The result is two places that write the same state, fire the same side
effect, or expose the same action through a second UI/API/CLI path. It also
catches changed files that no component owns, and selected components whose
files changed since the last `confirm` (or that are still draft).
## Use when
- You are about to add a feature, fix a bug, or refactor inside a project that has `.flowguard/map.json`.
- Your plan creates a new module, model, workflow, handler or entrypoint.
- The change touches state, side effects, or behavior-bearing fields (config keys, schema keys, prompt fields).
- The same action is reachable from several surfaces (UI, API, CLI, alias, wrapper) and you change one of them.
- You need to pick the right next capability for the real work.
## Do not use when
- The change is a typo, formatting, or a pure read-only explanation. Skip it and say why.
- The project has no map yet. Write the map first (`python -m flowguard map scan`, describe, then `confirm`).
- You already know the owner and need to prove behavior. Use plain modeling (`references/model_recipes.md`), model-test, or model-miss.
- You need to plan a field rename or retirement. Use field-lifecycle after this preflight names the owner.

## Inputs

- The task in one sentence, and the files you expect to change.
- `python -m flowguard read --find WORDS` with words from the task, to get candidate components.
- `python -m flowguard read --component ID` for each candidate: `responsibilities`, `files`,
  `entrypoints`, `state`, `side_effects`, `depends_on`, `tests`, `models`, `status`.
- `python -m flowguard map impact <files>` to see owners, unmapped files and components to REVIEW.
- The owner's model file (first entry in `models`) and the code at its entrypoints.
- If `.flowguard/behavior/inventory/ledger.json` exists, the behavior commitments for the task.

## Steps

1. Collect the context from the map. This is the normal path:
   ```python
   from flowguard import existing_model_preflight_from_project, review_existing_model_preflight
   pre = existing_model_preflight_from_project(
       ".", "add cancel order", changed_paths=("app/orders.py",),
       mode="full")
   report = review_existing_model_preflight(pre)
   print(report.format_text())
   ```
   It selects components in this order: behavior-commitment lookup (only if that
   behavior file exists); owners of `changed_paths` and components whose `models`
   list a changed path; if nothing was selected and there are no changed paths, the
   top 3 components whose responsibilities match the task words (either mode). It
   then adds one-hop neighbours from the real import graph (not `depends_on`).
   `mode="light"` never reads model bodies. `mode="full"` (the default) also takes
   entrypoints and, without running the file, reads class names, `*State` fields and
   top-level `state_owned`, `side_effects_owned`, `fields_owned` lists from the first
   file in `models`. `downstream_routes` is optional; owner lookup alone can finish.
   `inventory_scope=PREFLIGHT_INVENTORY_BROAD` (from `flowguard.existing_model_preflight`)
   selects every component; use it only for a whole-project review.
2. Read the result. `relevant_models` (`ModelContextHit`) are the selected components:
   owners plus import neighbours. `growth_gaps` are changed files no component owns
   (paths under `tests/` and `.flowguard/` are skipped). `stale_obligations` lists
   selected components whose files changed since `confirm`, or that are still draft.
3. Decide reuse. `reuse_decision` is one of `reuse_existing`, `extend_existing`,
   `add_child_model`, `new_boundary`, `no_model_found`, `skip_with_reason`
   (constants `REUSE_DECISION_*`). The helper sets `reuse_existing` or `no_model_found`;
   change it if your plan differs. Prefer extending the owner.
4. If your plan adds a boundary, fill the plan object yourself, usually
   `dataclasses.replace(pre, ...)`. A fresh `ExistingModelPreflight(id, task, ...)` also
   needs `model_search_performed=True` and `search_paths`. Key fields:
   `proposed_new_boundaries`, `duplicate_risks` (`DuplicateBoundaryRisk(item_type, item_id,
   existing_owner_id, proposed_owner_id=, resolution=, rationale=, resolved=)`),
   `rationale`, `downstream_routes`. For fields: `behavior_field_ids`,
   `field_lifecycle_model_ids`. For multi-surface actions: `expected_surface_ids`,
   `intent_surfaces` (`ExistingIntentSurface`), `require_complete_surface_inventory=True`,
   `surface_inventory_revision`, `surface_inventory_evidence_ids`, plus
   `affected_business_intent_id`, `selected_commitment_id`, `selected_primary_path_id`
   (any surface field makes these three required), and `typed_external_difference_ids`.
5. Run `review_existing_model_preflight(...)`. `report.ok` must be true. `report.decision`
   says why it stopped (for example `duplicate_boundary_risk_blocked`).
6. Only for a new reusable check, start from the template:
   `python -m flowguard template existing-model-preflight --write .`
   It writes `.flowguard/models/owners/existing_model_preflight/model.py` (one correct
   and one broken preflight), the runner
   `.flowguard/verification/owners/existing_model_preflight/run_checks.py`
   (exit 0 only if the correct case passes and the broken case fails), and a notes file
   in `docs/`. Replace the router example with your real owner and plan.
7. Only if step 6 created or changed a persistent runner, register its path in the owner's
   `models` and run `python -m flowguard map models existing_model_preflight` (id = folder name).
8. Fix every unmapped file: add it to one component's `files`, then `python -m flowguard map confirm <id>`.

## What blocks

`behavior_lookup_primary_owner_missing` blocks related commitments with no primary owner;
an unrelated ledger only warns when the map already resolves the task owner.

| Code | Meaning |
|---|---|
| `missing_model_search` | The plan does not say a model search was done (`model_search_performed`). |
| `missing_ownership_evidence` | Full mode has a current owner but no responsibilities, state, effects, entrypoints, fields or classes recorded. |
| `duplicate_boundary_risk_unresolved` | A listed `DuplicateBoundaryRisk` has no known `resolution` with a `rationale` and is not `resolved=True`. |
| `new_boundary_without_rationale` | `new_boundary` or `add_child_model` lacks `proposed_new_boundaries` or `rationale`. |
| `same_intent_new_boundary_without_external_difference` | `new_boundary` for an intent that already has `intent_surfaces`, with no `typed_external_difference_ids`. |
| `missing_expected_intent_surface` | An id in `expected_surface_ids` is missing from `intent_surfaces`. |
| `missing_field_lifecycle_ownership` | `behavior_field_ids` are set but no field owner or field lifecycle model is recorded. |
| `layered_proof_status_unknown` | Full mode: an owner has `child_model_ids` but parent coverage or child status fields are empty. |
| `non_authoritative_model_promoted` | A selected component (owner or import neighbour) is stale or still draft. |
| `modeled_current_owner_unresolved` | A map exists, but no confirmed, fresh component was selected for the task. |
| `model_growth_unbound` | A changed file (present or deleted) belongs to no component in the map. |
| `adoption_candidate_not_current` | There is no map; found model files are candidates only. |

## Risk-specific regression examples

- A second scheduler that writes the same `pending_tasks` state as the existing router, with
  an unresolved `DuplicateBoundaryRisk` (must give `duplicate_boundary_risk_unresolved`).
- A `new_boundary` decision with an empty `rationale` (must give `new_boundary_without_rationale`).
- A plan that lists `surface:cli` and `surface:api` as expected but inventories only the CLI
  (must give `missing_expected_intent_surface`).
- A change to a source file outside `tests/` that no component lists in `files` (must give `model_growth_unbound`).

## Done when

- [ ] `review_existing_model_preflight` returns `ok` for your real plan, and the report names the owner and the reuse decision.
- [ ] Relevant business regressions remain covered by the existing owner tests.
- [ ] If a new runner was needed, register it in the owner's `models` and run it.
- [ ] The owner's `tests` in the map list the tests for the changed behavior.
- [ ] `python -m flowguard change` is clean: no unmapped files, no stale owner.
- [ ] Your report says what ran (preflight mode, models, tests), what was skipped and why, and the next capability.

## Limits

- It checks ownership as declared in the map and model files. It does not prove the new code is correct; pair it with real tests and the downstream capability.
- With no changed paths, owners are picked by matching responsibility words. These are candidates; confirm them with `read --component` and the code. A stale import neighbour blocks too: re-confirm it or explain it.
- A behavior-commitment owner id must equal a component id or a path in that component's `models`; otherwise that component is not selected.
- Hand-filled plan objects are trusted: if you omit a duplicate risk or a surface, the review cannot see it.
