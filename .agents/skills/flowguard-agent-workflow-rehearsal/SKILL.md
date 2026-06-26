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

Use this skill for its declared flowguard workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed flowguard-agent-workflow-rehearsal skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: model preflight, process review, evidence alignment, closure.

## Use When

Use when the user request matches the flowguard-agent-workflow-rehearsal activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
