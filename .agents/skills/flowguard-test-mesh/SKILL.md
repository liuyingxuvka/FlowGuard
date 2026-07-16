---
name: flowguard-test-mesh
description: Use when tests, checks, transition cells, payload cases, or evidence are large, slow, layered, stale, skipped, backgrounded, release-only, or require parent/child ownership and freshness proof.
---

# FlowGuard Test Mesh

## Purpose
Govern parent/child test hierarchy, validation partitions, results, and freshness.

## Entrypoint Scope
This is a standalone FlowGuard satellite skill; `test_mesh_maintenance` owns evidence structure, not semantics, process optimization, or test execution.

## Local Material Routing
Read `references/test_mesh_protocol.md` for split, ownership, diagnostic accounting, reuse, matrices, and release scope.

## Entrypoint Acceptance Map
Review a model-derived parent/child validation mesh; block stale, skipped, incomplete, or unowned evidence; hand semantics and lifecycle/risk to typed owners.

## Use When
- Use for large/slow/background child test scripts, stale/reused evidence, release gates, artifact-payload matrices, or diagnostic boundaries.

## Do Not Use When
- Do not split code/models, choose DPF process shape, group root causes, decide semantics, or execute tests; return small tests to `model-first-function-flow`.

## Required Workflow
1. Define the parent gate and derive child suites/scripts from a FlowGuard validation-structure model.
2. Declare an independent inventory revision and every required surface, obligation, member, cell, case, and shard; map each id to one owner.
3. Attach status, freshness, artifacts, reuse tickets, skips/timeouts, terminal identity, fingerprint, covered ids, and versions. Diagnostics add `diagnostic_boundary`, planned/executed/failed/not-run counts, not-run reason, campaign id, and stable Finding Ledger ids. Provider checks preserve session/consumer and receipt identity.
4. Review routine/release scope and return child evidence plus typed handoffs.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Use the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- PID/log/running/progress proves liveness only; reuse requires current `TestResultReuseTicket` and `ProofArtifactRef`.
- One receipt may fan out but cannot be copied or counted as several executions.
- Require `planned = executed + not_run`, `failed <= executed`, no not-run under `declared_complete`, visible reasons elsewhere, and stable finding ids for failures.
- Locally green subsets cannot prove an independently declared complete inventory.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, a validation mesh diagram, and child freshness.

## SkillGuard Maintenance
- Edit contract source and regenerate; SkillGuard cannot turn liveness into pass.

<!-- BEGIN MANAGED VALIDATED TEMPLATE PACK -->
## Validated Template Pack Routing

- Target families: `flowguard`; native owner: `flowguard.file-template-router`.
- Current catalogs: `flowguard.file-template-packs` revision `1`.
- Resolve the task through this Guard's native router first, then ask the target-owned adapter for a current neutral projection; never infer a template from wording or a skill name.
- Preserve the adapter's complete candidate and rejection accounting. Zero candidates may use only the declared validated base; one candidate gets a read-only preview; many candidates require complete dependencies, pairwise compatibility, one field owner, and target-authored dominance or must block as ambiguous.
- Recompute the projection immediately before applying a preview. A stale request, catalog, route, builder, validator, or content identity blocks all writes.
- Hand the selected preview to the target-declared builder and consume every target-native validator receipt. Template structure is not domain validity, completion, installation, release, or publication evidence.
- Record a harvest disposition after creating or materially deepening a reusable model, and keep no-match evidence visible.
- Declared validated bases: `flowguard.template.base-project`.
- Template inventory: `flowguard.risk.artifact-payload-real-surface`, `flowguard.risk.completion-requires-evidence`, `flowguard.risk.partial-failure-consistency`, `flowguard.risk.side-effect-at-most-once`, `flowguard.risk.stale-result-overwrite`, `flowguard.template.base-project`, `flowguard.template.behavior-commitment-ledger`, `flowguard.template.closure-contract`, `flowguard.template.code-structure-recommendation`, `flowguard.template.development-process-flow`, `flowguard.template.existing-model-preflight`, `flowguard.template.field-lifecycle`, `flowguard.template.layered-boundary-proof`, `flowguard.template.maintenance-scan`, `flowguard.template.maintenance-workflow`, `flowguard.template.model-angle-deliberation`, `flowguard.template.model-miss-review`, `flowguard.template.model-miss-review-full`, `flowguard.template.model-similarity-consolidation`, `flowguard.template.model-test-alignment`, `flowguard.template.model-test-alignment-full`, `flowguard.template.model-topology-hazard-review`, `flowguard.template.plan-detailing`, `flowguard.template.primary-path-authority`, `flowguard.template.project`, `flowguard.template.project-adoption`, `flowguard.template.risk-evidence-ledger`, `flowguard.template.risk-intent-check-plan`, `flowguard.template.risk-template-library`, `flowguard.template.runtime-path-evidence`, `flowguard.template.spec-work-package`, `flowguard.template.structure-mesh`, `flowguard.template.test-mesh`, `flowguard.template.ui-flow-structure`, `flowguard.template.ui-flow-structure-full`, `flowguard.template.workflow-step-contracts`.
- Native validator inventory: `validator:flowguard:template-pack-native`.
- Claim boundaries: FlowGuard file templates are starter artifacts only; current executable models and checks remain required for behavior, closure, release, or installation claims.
<!-- END MANAGED VALIDATED TEMPLATE PACK -->
