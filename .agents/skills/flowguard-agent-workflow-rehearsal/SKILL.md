---
name: flowguard-agent-workflow-rehearsal
description: Use when a non-trivial task may require multiple Codex skills, tools, plugins, external actions, staged validation, unclear skill order, skipped-skill consequences, continue/rework gates, or cross-skill evidence claims. Start with a fresh current-machine SkillInventorySnapshot, then rehearse selected/skipped skills, order, gaps, side effects, and final claim before execution.
---

# FlowGuard Agent Workflow Rehearsal

Standalone FlowGuard satellite skill for multi-skill/tool workflow planning.
Use it when skill order, skipped skills, side effects, continue/rework gates,
or completion evidence can change the outcome.

Return to `model-first-function-flow` when the FlowGuard route itself is
unclear. Use this skill before execution; it does not execute the workflow.

## First Read

- Route id: `agent_workflow_rehearsal`.
- Required fresh input: `SkillInventorySnapshot`; cached skill lists are
  history only.
- Core helpers: `AgentWorkflowPlan`, `SkippedSkill`,
  `review_agent_workflow_rehearsal()`.
- Reference: `references/agent_workflow_rehearsal_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Skipped candidate skills require reason, consequence, and accepted scope.
- Weak validation guidance needs a compensating check before broad confidence.
- UI click-through, real-surface artifact payload proof, manual review, and installed-skill sync are explicit evidence surfaces when relevant.
- Full UI claims need separate evidence roles in `ui_evidence_roles`:
  `ui_inventory`, `ui_source_baseline`, and
  `ui_human_operability`, `ui_implementation_validation`. Missing one blocks full confidence.
- Multi-agent UI work should split evidence roles instead of sending every
  agent into code: visible-surface inventory, source-baseline mapping/alignment
  when applicable, implementation validation, and human-operability can be
  separate workstreams.
- Workflow models need template-harvest closure.

## Minimum Workflow

1. Capture a fresh current-machine skill/tool/plugin inventory.
2. Mark required and candidate skills for the task.
3. Rehearse selected skills, skipped candidates, order, evidence surfaces,
   side effects, and continue/rework gates.
4. For UI work, assign and record inventory, source-baseline,
   human-operability, and implementation-validation evidence roles before a full claim.
5. Treat blocked or scoped findings as claim boundaries.

## Snapshot

For non-trivial use, show candidate skills, selected skills, skipped skills,
continue/rework gates, side effects, validation gaps, and final claim boundary.

## Non-Goals

- Do not execute the selected skills.
- Do not replace DevelopmentProcessFlow or route-specific validation.
- Do not treat an old inventory as current evidence.
