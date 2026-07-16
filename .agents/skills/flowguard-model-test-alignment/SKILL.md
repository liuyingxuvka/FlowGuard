---
name: flowguard-model-test-alignment
description: Use when model obligations, owner external CodeContracts, source audits, transition cells, boundary observations, payload cases, closure targets, or ordinary test evidence need direct current comparison.
---

# FlowGuard Model-Test Alignment

## Purpose
Compare model obligations, owner external `CodeContract`, and current tests for the same behavior and coverage.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns `model_test_alignment` (`public_owner`) rows and hands large evidence to TestMesh.

## Local Material Routing
Read `references/model_test_alignment_protocol.md` for contracts, audits, matrices, targets, and bindings.

## Entrypoint Acceptance Map
Accept obligations/contracts/evidence; compare bindings/freshness; block missing/stale/orphan rows and hand gaps to owners.

## Use When
- Use for model-code-test coverage, cells, field projections, code boundaries, targets, or payload evidence.

## Do Not Use When
- Do not split tests/code/models or use TestMesh as a parallel semantic owner; return undefined obligations to `model-first-function-flow`.

## Required Workflow
1. List obligations, stable plane/intent/commitment/path ids, fields, `ArtifactPayloadContract`, owner/delegating contracts, similarity, and evidence kinds.
2. Materialize similarity/exhaustion rows into obligations, owner contracts, targets, tests, or typed scoped dispositions; consume current source/runtime/family evidence.
3. Classify gaps and hand them to TestMesh, maturation, risk, or closure owners.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Use the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework. Full confidence requires each obligation to bind one owner contract and current same-plane test.
- One intent cannot align to two primary paths; facades delegate with current no-independent-success evidence.
- Opaque family/similarity ids and missing/stale/skipped/audit/payload/target evidence do not count; delegate large evidence explicitly.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, binding gaps, and a diagram whose edges mean covers, partially covers, or does not cover.

## SkillGuard Maintenance
- Edit contract source, regenerate; SkillGuard cannot manufacture proof.

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
