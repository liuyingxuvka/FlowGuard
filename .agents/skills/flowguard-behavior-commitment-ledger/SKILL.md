---
name: flowguard-behavior-commitment-ledger
description: Use for external behavior registration, bidirectional source coverage, exactly one primary owner model, change-mode accounting, internal Primary Path Authority handoff, or broad done/release/archive/publish confidence.
---

# FlowGuard Behavior Commitment Ledger

## Purpose
Maintain one plane-partitioned `BehaviorCommitmentLedger` with source evidence, one owner, typed relations, and path authority.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns route/native owner `behavior_commitment_ledger` (`public_owner`) and the internal PPA handoff.

## Local Material Routing
Read `references/behavior_commitment_ledger_protocol.md` for fields, modes, lookup, PPA, and projections.

## Entrypoint Acceptance Map
Accept a bounded inventory/mode; register one owner per commitment; block coverage, relation, freshness, or PPA gaps; hand evidence downstream.

## Use When
- Use for the six ledger modes: bootstrap, add, change, remove/replace, gap backfill, or miss check.

## Do Not Use When
- Do not inventory helper internals or replace sibling evidence owners; return ordinary modeling to `model-first-function-flow`.

## Required Workflow
1. Define boundary/mode; query canonical JSON lightly, then do mode-required bidirectional discovery.
2. Set one `product_runtime`, `agent_operation`, or `development_process` plane plus `actor_kind`; kind is form, not plane.
3. Give each exact same-plane intent one stable id/active commitment; equivalent surfaces map to it, never a delegate row.
4. Set one owner, typed variants/relations with cross-plane rationale, lookup binding, lifecycle, and evidence.
5. Bind one current-green `primary_path_id`; run `review_behavior_commitment_ledger()` and project DCAR/TestMesh/risk evidence.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Use the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework or second success path.
- Duplicate exact promises, owner overlap, source/freshness/PPA/shard gaps, unknown or disallowed relations, and missing cross-plane rationale block broad confidence.
- Cross-plane language never merges owners. `unclassified`, legacy dependencies, and ambiguous plural paths are upgrade-only blockers.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, and commitment/source/owner/lookup/PPA status.

## SkillGuard Maintenance
- Edit contract source, regenerate; SkillGuard cannot manufacture native evidence.

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
