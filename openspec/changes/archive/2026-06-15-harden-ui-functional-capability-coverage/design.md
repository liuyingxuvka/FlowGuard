## Context

The existing UI Flow Structure route already has the right staged shape:

1. work mode;
2. observed real surface;
3. UI interaction model;
4. visible surface;
5. journey coverage;
6. structure and text hierarchy;
7. human-operability;
8. implementation validation;
9. geometry, responsiveness, transition coverage, and final closure.

Recent failures show a gap before the visible-control checks. A button can be fake and get caught by functional-chain evidence, but a required function can also be missing completely. In that case there may be no button, journey, or feature contract for FlowGuard to inspect. The fix should therefore extend the existing route with a capability inventory and completeness review, not create a second UI process.

## Goals / Non-Goals

**Goals:**

- Add a generic capability inventory for user-visible UI functionality.
- Bind capabilities to existing `UIFeatureContract`, `UIUserTaskCoverageLedger`, `UIJourneyCoverage`, `UIControlFunctionalChainSet`, and `UIImplementationValidation`.
- Require output contracts for result-producing capabilities such as load, plot, refresh, export, save, generate, render, open, or delete.
- Keep greenfield, source-based, and mixed work modes intact.
- Treat missing required capabilities as blockers or explicit scoped blindspots.
- Update prompt guidance, OpenSpec specs, tests, installed skills, docs, and closure/process/risk surfaces together.

**Non-Goals:**

- Do not introduce a parallel UI route.
- Do not require source-baseline evidence for greenfield UI.
- Do not replace Model-Test Alignment, TestMesh, StructureMesh, or code-boundary routes.
- Do not require every small visual-only edit to build a capability inventory when no user-visible functionality claim is made.

## Decisions

1. Extend existing UI dataclasses rather than building a new route.

   Capability coverage is implemented inside `flowguard.ui_structure` because the owning route already controls feature contracts, task coverage, journeys, controls, functional chains, and implementation validation. A separate workflow would duplicate evidence and weaken closure.

2. Keep `UIFeatureContract` as the bridge from capability to UI model.

   New capability rows define what must exist. `UIFeatureContract` remains the existing UI-facing feature contract, but gains capability and output-contract references so it can no longer silently omit required functions.

3. Make output contracts explicit.

   For result-producing UI work, a visible chart/table/status/file container is not enough. A `UICapabilityOutputContract` records the expected result kind, display/state/data targets, assertion, evidence kind, and validation boundary.

4. Treat scoped omissions as first-class rows.

   A capability may be explicitly out of scope, deferred, blocked, manual-only, or pure UI only when the row records owner, reason, validation boundary, and rationale. Empty scoped-out lists do not satisfy completeness.

5. Reuse final closure evidence kinds.

   ClosureContract should consume a new `ui_functional_capability_coverage` report kind, while implementation validation still owns run evidence and functional chains. This preserves the distinction between capability completeness and actual runnable evidence.

## Risks / Trade-offs

- [Risk] The added inventory can feel heavy for small UI changes. -> Mitigation: require it only for non-trivial UI work or claims that say implemented, runnable, complete, release-ready, or user-visible functionality is covered.
- [Risk] Agents may create vague capabilities such as "data tools". -> Mitigation: tests and guidance require concrete user-visible capability rows, dependencies, outputs, and evidence boundaries.
- [Risk] Output contracts could duplicate tests. -> Mitigation: output contracts describe expected visible/result semantics; Model-Test Alignment or ordinary tests still prove code/test binding when needed.
- [Risk] Additive fields may create API churn. -> Mitigation: keep new fields defaulted and additive, but require them in review paths when broad UI claims invoke capability coverage.

## Migration Plan

1. Add capability dataclasses, report class, and review helper.
2. Add additive fields to `UIFeatureContract`, `UIUserTaskCoverageLedger`, and `UIImplementationValidation`.
3. Wire `review_ui_human_operability(...)` and `review_ui_implementation_validation(...)` to consume optional capability coverage and block broad claims when it is missing or failed.
4. Add closure/process/risk constants and report checks.
5. Update skills, docs, templates, OpenSpec specs, tests, version metadata, installed skill sync, shadow workspace, adoption log, and local git/tag.

## Open Questions

None for this implementation pass. Future project-specific source adapters may populate capability inventories automatically, but the generic route only needs structured rows.
