---
name: flowguard-agent-workflow-rehearsal
description: Use only when explicitly requested or delegated by flowguard-development-process-flow's agent_workflow mode to rehearse a multi-skill, tool, plugin, or external-action workflow from a fresh inventory; generic workflow planning enters flowguard-development-process-flow first.
---

# FlowGuard Agent Workflow Rehearsal

## Purpose
Rehearse capability selection, order, side effects, evidence gates, and rework before execution; never execute or supervise the selected tools.

## Entrypoint Scope
Delegated FlowGuard mode skill; route `agent_workflow_rehearsal`, role `delegated_mode`, native owner `development_process_flow`. Generic multi-skill work enters `flowguard-development-process-flow` first.

## Local Material Routing
Read `references/agent_workflow_rehearsal_protocol.md` for `SkillInventorySnapshot`, plan rows, finding codes, and completion decisions.

## Entrypoint Acceptance Map
Accept a fresh current-machine inventory and explicit/delegated scope; produce an `AgentWorkflowPlan`; block stale inventory, unsafe side effects, or unsupported full claims; return execution and final evidence to DevelopmentProcessFlow.

## Use When
- Use for delegated `agent_workflow` planning where selected/skipped skills, plugins, tools, external actions, or continue/rework gates change confidence.

## Do Not Use When
- Do not use as a generic router, execute the workflow, or replace route-native validation; return unclear routing to `model-first-function-flow`.

## Required Workflow
1. Capture a fresh `SkillInventorySnapshot` and mark required/candidate skills.
2. Keep rehearsed steps in `agent_operation`. When a step invokes or validates product/process behavior, reference its commitment id, target plane, and typed BCL relation; do not copy that behavior into the AI step.
3. Rehearse ordered steps, skipped consequences, prior evidence gates, side effects, compensating checks, receipts, and rework paths.
4. Return selected/skipped skills, candidate skills, continue/rework gates, validation gaps, and final claim scope.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Require explicit delegation/direct request, current inventory, accepted skip boundaries, and evidence before every irreversible side effect.
- Progress or missing real-surface artifact payload proof, UI/manual/install evidence cannot satisfy a full claim.
- Registered same-plane behavior should be recalled for non-trivial matching operations, but this route does not force every trivial action through a model or turn related product rows into AI instructions.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, selected/skipped skills, and side effects.

## SkillGuard Maintenance
- Edit contract source, regenerate; SkillGuard cannot create an executor.

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
