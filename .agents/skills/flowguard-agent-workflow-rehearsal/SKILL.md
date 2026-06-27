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
Bind each flowguard run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-agent-workflow-rehearsal plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use workspace, skill directory, user files, or configured project paths; keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor attached to the native route/check owner: FlowGuard skill route map plus the real flowguard package/model checks. It enforces contract gates through that native owner before progress or closure; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: model preflight, process review, evidence alignment, closure.
## Use When
Use when the request matches flowguard-agent-workflow-rehearsal and needs this governed workflow, materials, checks, or handoff behavior.
## Do Not Use When
Do not use outside the domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the target-owned native route/check surface, run the SkillGuard contract gates around the native workflow, collect evidence, run checks, fix failures, then report.
## Hard Gates
Do not skip phases, do not replace required evidence with prose, do not treat stale reports as current, do not weaken validation to pass, and do not claim completion when blockers remain.
## Output Requirements
Report evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary; distinguish checked, unchecked, blocked, and uncertain.
## SkillGuard Maintenance
Keep `.skillguard` contracts, checks, evidence, and ledger current; rerun SkillGuard after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
