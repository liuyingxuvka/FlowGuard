## Context

FlowGuard already exposes a thin model-first core, route-scoped helper groups,
existing-model preflight, unified summary reports, maintenance obligations,
maintenance scan, proof artifacts, and DevelopmentProcessFlow revalidation
recommendations. The current gap is not a missing high-level workflow. The gap
is that AI agents must manually translate a report into the next route,
missing input rows, proof gaps, and the safe claim boundary.

The project also has explicit prompt-budget and route-first constraints. Any
change must keep core APIs small, avoid adding another mandatory checklist,
and preserve existing satellite route ownership.

## Goals / Non-Goals

**Goals:**

- Add structured next-action metadata to existing report and route handoff
  objects.
- Let `FlowGuardSummaryReport` feed `MaintenanceScanPlan` through a small
  bridge helper.
- Keep `MaintenanceScan` a router that points to existing specialist routes.
- Make DevelopmentProcessFlow recommendations more directly usable by AI
  agents for minimum rerun decisions.
- Add a light project inventory helper for ExistingModelPreflight without
  changing the preflight review contract.
- Update compact AI guidance, templates, and tests so agents use structured
  outputs before manually inferring routes.

**Non-Goals:**

- No new FlowGuard core semantics.
- No new all-in-one session runner or new top-level mandatory workflow.
- No automatic code refactor, model split, test execution, or release publish
  inside MaintenanceScan.
- No broad rewrite of satellite skill protocols or prompt expansion.

## Decisions

1. Extend current row objects instead of adding a parallel action model.

   `FlowGuardFindingLedgerEntry`, `MaintenanceObligation`,
   `MaintenanceAction`, and `RevalidationRecommendation` are already the
   durable handoff objects. Adding route/action/proof/claim fields there keeps
   the handoff local to existing routes.

   Alternative considered: create a separate `FlowGuardSessionAction` object.
   Rejected because it would create a second orchestration layer and duplicate
   MaintenanceScan.

2. Use a SummaryReport-to-MaintenanceScan bridge rather than filesystem
   scanning in the runner.

   `run_model_first_checks(...)` should remain a check orchestrator. The
   bridge helper converts report gaps and optional changed-artifact/evidence
   rows into a maintenance scan plan. This lets project adapters provide file
   data without making the runner git-specific.

   Alternative considered: make `run_model_first_checks(...)` call
   MaintenanceScan automatically. Rejected because many model-first runs are
   not project-change scans and should not pretend they know changed files.

3. Treat proof artifacts as the evidence boundary.

   `ProofArtifactRef` already represents concrete command/replay artifacts.
   New fields should carry proof gap codes and proof requirements, not invent a
   second proof system.

4. Keep route ids stable and conservative.

   Ledger and maintenance obligation owner routes should continue using
   existing route ids such as `model_maturation_loop`,
   `development_process_flow`, `model_test_alignment`, and
   `agent_workflow_rehearsal`.

5. Project inventory is a helper, not a validator.

   `existing_model_preflight_from_project(...)` should build the existing
   `ExistingModelPreflight` shape from likely project records. The existing
   `review_existing_model_preflight(...)` remains the validator.

## Risks / Trade-offs

- [Risk] Agents may treat a structured next action as validation.
  -> Mitigation: action fields and docs must state that route actions are
  unresolved until owner-route proof evidence exists.

- [Risk] Fields duplicate free-text `next_step`.
  -> Mitigation: keep `next_step` for humans and add typed fields for agents;
  tests must assert JSON output includes both.

- [Risk] Prompt guidance grows again.
  -> Mitigation: add only compact instructions to hot paths and rely on tests
  that enforce skill-doc budgets.

- [Risk] Project inventory helper misses custom project records.
  -> Mitigation: return visible `no_model_found` or scoped context rather than
  claiming full preflight; callers may still pass explicit preflight rows.

## Migration Plan

1. Add fields with default values so existing callers continue to work.
2. Add conversion helpers and tests without changing existing decisions.
3. Update API exports and docs after unit tests prove backward compatibility.
4. Update FlowGuard self-model and OpenSpec tasks.
5. Run focused tests, model checks, OpenSpec validation, install verification,
   and project audit before claiming completion.

## Open Questions

None requiring user input. If implementation exposes a conflict with existing
route ids or public API tests, keep the route ids stable and adapt the helper
fields rather than changing the route map.
