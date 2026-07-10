---
name: flowguard-agent-workflow-rehearsal
description: Use only when explicitly requested or delegated by flowguard-development-process-flow's agent_workflow mode to rehearse a multi-skill, tool, plugin, or external-action workflow from a fresh inventory; generic workflow planning enters flowguard-development-process-flow first.
---

# FlowGuard Agent Workflow Rehearsal

## Purpose
Rehearse capability selection, order, side effects, evidence gates, and rework before execution; never execute or supervise the selected tools.

## Entrypoint Scope
Route id: `agent_workflow_rehearsal`; role: `delegated_mode`; native owner: `development_process_flow`. Direct use requires an explicit request; generic multi-skill work enters `flowguard-development-process-flow` first.

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
2. Rehearse ordered steps, skipped consequences, prior evidence gates, side effects, compensating checks, and rework paths.
3. Return selected/skipped skills, candidate skills, continue/rework gates, validation gaps, and final claim scope.

## Hard Gates
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Require explicit delegation/direct request, current inventory, accepted skip boundaries, and evidence before every irreversible side effect.
- Progress, weak guidance, or missing UI/payload/manual/install evidence cannot satisfy a full claim.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, including selected/skipped skills and side effects.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard validates this native delegated route and cannot create an alternate executor.
