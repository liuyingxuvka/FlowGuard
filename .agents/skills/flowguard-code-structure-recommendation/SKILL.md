---
name: flowguard-code-structure-recommendation
description: Use when a FlowGuard model should drive pre-code module and function boundaries, FunctionBlock ownership, field/state/side-effect owners, facade design, adapter boundaries, or validation structure before production edits.
---

# FlowGuard Code Structure Recommendation

## Purpose
Derive a target implementation structure from a named functional model without refactoring existing production code.

## Entrypoint Scope
Route id: `code_structure_recommendation`; role: `public_owner`; native owner: `code_structure_recommendation`. This standalone FlowGuard satellite skill owns recommendation-only architecture.

## Local Material Routing
Read `references/code_structure_recommendation_protocol.md` for model inputs, recommendation shape, field ownership, leaf boundaries, and StructureMesh handoff.

## Entrypoint Acceptance Map
Accept a source model and named responsibilities; produce FunctionBlock-to-module ownership, state/field/side-effect maps, facade plan, and validation boundaries; block source-less or duplicate ownership; hand existing-code refactors to StructureMesh.

## Use When
- Use before code when module split, function ownership, facade, adapter, field reader/writer, or validation boundary is unclear.

## Do Not Use When
- Do not perform existing-code refactors, invent behavior, or replace parity/alignment evidence; return missing models to `model-first-function-flow`.

## Required Workflow
1. Name the source model, FunctionBlocks, state, fields, side effects, and public entrypoints.
2. Recommend cohesive target modules, single owners, facades, adapters, and observable leaf boundaries.
3. Record rationale plus StructureMesh, Model-Test Alignment, or FieldLifecycleMesh handoffs.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Do not invent modules before responsibilities; require one owner per state/field write, explicit public facade, and validation boundaries.
- A too-large leaf must split or remain scoped; new/deepened models require template harvest closure.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus a code structure diagram and ownership map.
- When drawing the code structure diagram, edges mean owns, calls, adapts, exposes, or validates.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard checks recommendation inputs/outputs and cannot implement the proposed structure.

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
