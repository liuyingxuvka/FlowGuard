## Context

The current FlowGuard codebase already has `RiskIntent`, `MinimumModelContract`, template reuse/harvest review, `FlowGuardCheckPlan`, summary reports, and model-hardening examples. The weak point is not missing vocabulary; it is the remaining public route that says direct `Explorer(...)` is a valid minimal FlowGuard path. That route makes it possible to produce a very small model with no declared protected error, no executable known-bad proof, and no template closure while still describing the result as FlowGuard.

This change intentionally reuses the existing flow instead of creating a parallel system. The formal entry becomes a single path: declare the risk, declare the minimum model contract, prove at least one known-bad case is caught, close template reuse/harvest, then run the unified check plan.

## Goals / Non-Goals

**Goals:**

- Make `FlowGuardCheckPlan` the only formal AI/default FlowGuard entry.
- Keep `Explorer` as an internal execution primitive used by the runner and lower-level tests, not as a documented formal entry or generated starter route.
- Add structured known-bad proof evidence and make it a hard gate for formal FlowGuard confidence.
- Convert missing risk intent, minimum contract, template closure, and known-bad proof from soft gaps into blockers or failures for formal claims.
- Update public docs, Skill guidance, templates, and tests so there is one clear path to maintain.
- Surface old direct-Explorer models as upgrade-required, not compatibility-supported.

**Non-Goals:**

- This change does not delete the low-level `Explorer` class from the Python package; the runner and internal checks still need the finite exploration engine.
- This change does not mass-rewrite every historical `.flowguard` model in one pass.
- This change does not publish a GitHub release unless separately requested.

## Decisions

1. **Formal entry is hardened in existing helpers.**
   - Use `RiskIntent`, `MinimumModelContract`, `TemplateReuseReview`, `TemplateHarvestReview`, `FlowGuardCheckPlan`, and `run_model_first_checks(...)`.
   - Avoid a second orchestration API, because the existing flow already owns summary reports, ledgers, and templates.

2. **Known-bad declaration and proof are separate.**
   - `MinimumModelContract.known_bad_cases` remains the declaration.
   - New proof rows record how each case was actually caught: model run, broken workflow, scenario, replay, or proof artifact.
   - A name-only known-bad case no longer satisfies the formal gate.

3. **Failure semantics are strict.**
   - Missing formal entry material returns blocked.
   - A known-bad case that unexpectedly passes returns failed.
   - Stale, skipped, not-run, progress-only, or mismatched proof returns blocked.

4. **API surface is contracted rather than branched.**
   - `AGENT_DEFAULT_API` points to the hard entry helpers, not `Explorer`.
   - `CORE_API` may still list `Explorer` as a primitive for advanced/internal consumers, but docs must not present it as a FlowGuard entry path.

5. **Templates become enforcement examples.**
   - Generated starter templates must use the formal plan and include a broken variant proof.
   - Public tests must fail if the default templates teach direct Explorer as the entry.

6. **Old direct models are migration inputs.**
   - Audit/reporting should identify direct-Explorer-only models as upgrade-required.
   - The rollout can inventory old models first, then update priority model scripts without preserving old semantics as a supported path.

## Risks / Trade-offs

- **Breaking docs/API expectations** -> Update API surface tests, docs, and public templates together so the break is intentional and visible.
- **Over-hardening low-level internals** -> Keep `Explorer` importable as a primitive, but remove it from the default AI entry and generated routes.
- **Existing tests expect `pass_with_gaps`** -> Update focused tests to assert blocked/failed where the formal entry is incomplete.
- **Concurrent peer work touches `flowguard/__init__.py` and API tests** -> Patch those files incrementally and preserve unrelated new exports already present in the Git worktree.
- **Long regressions consume time** -> Run broad model/test regressions in background with final exit artifacts under `tmp/flowguard_background/`.
- **Shadow and Git workspaces can drift** -> Implement in the Git repo, then sync only touched files back to the shadow workspace after validation.
