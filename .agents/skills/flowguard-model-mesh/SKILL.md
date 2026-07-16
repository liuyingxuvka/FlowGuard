---
name: flowguard-model-mesh
description: Use when a FlowGuard project has three or more local models, an oversized model, stale child evidence, parent/child partitioning, target split derivation, child reattachment, affected siblings, or whole-flow mesh closure risk.
---

# FlowGuard Model Mesh

## Purpose
Govern parent/child model ownership, evidence freshness, reattachment, and closure without expanding every child state graph into the parent.

## Entrypoint Scope
Route id: `model_mesh_maintenance`; role: `public_owner`; native owner: `model_mesh_maintenance`. This standalone FlowGuard satellite skill owns model hierarchy, not test or code splits.

## Local Material Routing
Read `references/model_mesh_protocol.md` for inventory, target split derivation, partition rules, Child Reattachment Gate, mesh closure, and evidence tiers/freshness.

## Entrypoint Acceptance Map
Accept a parent and bounded children; derive/verify partitions and current receipts; block overlap, stale/unconsumed child evidence, missing closure/liveness, or incomplete leaf boundaries; hand test/alignment/closure gaps to typed owners.

## Use When
- Use for 3+ models, oversized/incomplete model groups, changed child boundaries, stale child evidence, coverage receipts, affected siblings, or parent whole-flow claims.

## Do Not Use When
- Do not split tests or code, trust child-local green as parent proof, or use for ordinary single-model work; return that work to `model-first-function-flow`.

## Required Workflow
1. Inventory parent/children, risk boundaries, target split derivation, ownership partitions, evidence tiers, and freshness.
2. Review disjointness, reattachment, siblings, receipts, leaf boundaries, and closure/liveness. Portable claims require current parent/child fingerprints and an explicit `flowguard.portable_refinement.v1` binding.
3. Preserve scoped/stale gaps and project cases/receipts to Model-Test Alignment, TestMesh, and closure owners.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Parent confidence requires complete partition ownership, legal overlap, current child evidence/receipts, and current parent consumption.
- Portable refinement requires complete reachable child mappings (or legal stutter), no stronger assumptions, and no weaker guarantees; prose edges are insufficient.
- Background progress is liveness only; missing closure feedback/bounds or template harvest closure blocks broad mesh confidence.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus a mesh diagram, reattachment, siblings, and receipt status.
- In the mesh diagram, edges mean delegates, reattaches, consumes output, or blocks the parent claim boundary.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard checks the native mesh contract and cannot reattach children or manufacture receipts.

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
