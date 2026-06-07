## Context

FlowGuard already has specialist routes for model-test alignment, structure mesh, test mesh, model mesh, architecture reduction, existing model preflight, agent workflow rehearsal, and development process freshness. The gap is not a missing specialist; it is the absence of a small functional scan that helps an AI agent decide which specialists are required after a concrete project change.

The design must avoid prompt bloat. AGENTS.md and skill text should point to one thin scan rather than repeating every possible maintenance checklist.

## Goals / Non-Goals

**Goals:**
- Add a compact helper that accepts changed artifacts, evidence status, candidate/skipped routes, and claim scope.
- Return concrete maintenance actions with route ids, action strength, reason codes, and claim impact.
- Reuse existing route names and helper ownership instead of creating a new mega-route.
- Provide docs and tests that show agents how to use the scan as a router.

**Non-Goals:**
- Running tests, model checks, replay, or refactors automatically.
- Replacing Model-Test Alignment, Architecture Reduction, StructureMesh, ModelMesh, TestMesh, DevelopmentProcessFlow, or AgentWorkflowRehearsal.
- Adding long AGENTS.md prompt lists for every possible maintenance condition.

## Decisions

1. Add `maintenance_scan.py` as a reporting/helper layer.

   Rationale: this is an orchestration report over existing routes. It should not live inside one specialist route because it must route among several peers.

   Alternative considered: extend DevelopmentProcessFlow. Rejected because that route owns freshness and lifecycle ordering, not model/code/test/structure route selection.

2. Represent inputs as small rows rather than repository scanning.

   Rationale: FlowGuard helpers should stay deterministic and tool-agnostic. Agents or adapters can collect changed files, evidence rows, and skipped route candidates from git, tests, OpenSpec, or runtime logs.

   Alternative considered: scan the filesystem directly. Rejected for now because projects differ and this would make the helper heavier than the intended thin router.

3. Classify actions as `required`, `suggested`, or `optional`.

   Rationale: not every signal should block work. A missing model-test alignment for touched code/model/test is required for broad confidence, while a small structure smell can be suggested until it affects the claim.

4. Keep route ownership explicit.

   Rationale: the scan tells the agent where to go next. It does not claim the owning route has passed.

## Risks / Trade-offs

- [Risk] Agents treat scan output as validation. → Mitigation: report wording and tests require missing/required actions to keep the claim scoped or blocked until the owning route provides evidence.
- [Risk] The scan becomes another long checklist. → Mitigation: small row types, reason codes, and existing route ids; no business-specific logic.
- [Risk] It misses project-specific cues. → Mitigation: allow custom signal rows and metadata so project adapters can add signals without changing the helper.
