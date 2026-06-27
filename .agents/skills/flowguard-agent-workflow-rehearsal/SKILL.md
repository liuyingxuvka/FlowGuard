---
name: flowguard-agent-workflow-rehearsal
description: Use when explicitly requested or delegated by flowguard-development-process-flow's agent_workflow simulator mode for multi-skill/tool/plugin/external-action rehearsal. Generic multi-skill workflow routing should enter flowguard-development-process-flow first.
---

# FlowGuard Agent Workflow Rehearsal

Delegated FlowGuard mode skill for multi-skill/tool workflow planning. It
remains directly invokable when the user names AgentWorkflowRehearsal or
another route delegates `agent_workflow`; ordinary multi-skill setup enters
`flowguard-development-process-flow` first.

Return to `model-first-function-flow` when the FlowGuard route itself is unclear.
Return to DevelopmentProcessFlow for generic multi-skill process planning. This
skill rehearses before execution; it does not execute the workflow.

## First Read

- Route id: `agent_workflow_rehearsal`.
- Simulator mode: `agent_workflow`; front door: `flowguard-development-process-flow`.
- Required input: fresh `SkillInventorySnapshot`; cached skill lists are history only.
- Core helpers: `AgentWorkflowPlan`, `SkippedSkill`,
  `review_agent_workflow_rehearsal()`.
- Reference: `references/agent_workflow_rehearsal_protocol.md`.

## Hard Gates

- Verify the real package, AGENTS.md managed record, and no fake mini-framework.
- Do not present this as the generic first entry for multi-skill setup.
- Skipped candidate skills need reason, consequence, and accepted scope.
- Weak validation guidance needs a compensating check before broad confidence.
- UI click-through, real-surface artifact payload proof, manual review, and
  installed-skill sync are explicit evidence surfaces when relevant.
- Full UI claims need `ui_inventory`, `ui_source_baseline`,
  `ui_human_operability`, and `ui_implementation_validation` evidence roles.
- Workflow models need template-harvest closure.

## Minimum Workflow

1. Capture a fresh current-machine skill/tool/plugin inventory.
2. Mark required and candidate skills.
3. Rehearse selected skills, skipped candidates, order, evidence surfaces,
   side effects, and continue/rework gates.
4. For UI work, assign inventory, source-baseline, human-operability, and
   implementation-validation evidence roles before a full claim.
5. Treat blocked or scoped findings as claim boundaries.

## Snapshot

Show candidate skills, selected skills, skipped skills, continue/rework gates,
side effects, validation gaps, and final claim boundary.
Status note: inventory, selected/skipped skills, side effects, validation gaps, next gate.

## Non-Goals

- Do not execute the selected skills.
- Do not replace DevelopmentProcessFlow or route-specific validation.
- Do not treat an old inventory as current evidence.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind this FlowGuard route to one work contract, native checks, current evidence, blockers, residual_risk, and claim_boundary.
## Entry Scope
Covers flowguard-agent-workflow-rehearsal and explicitly routed local materials only; no unrelated repos, private paths, external services, publication, or release claims unless separately routed.
## Runtime Binding
SkillGuard is the contract executor around FlowGuard's native router/checker/model surface. Use native-integrated or hybrid mode when a route already exists; do not add a second execution path.
## Required Workflow
Select the FlowGuard-owned route, open or compile `.skillguard/work-contract.json`, start or update the run record, execute native model/check gates, refresh evidence, fix blockers, then close only from current checks.
## Hard Gates
Block skipped phases, stale or prose-only evidence, hollow contracts, quality downgrades, unresolved native-route conflicts, and completion claims with remaining blockers.
## Output
Report checked target, route, evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary; separate checked facts from judgment.
## Maintenance
Refresh contracts, checks, evidence, and installed copies after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
