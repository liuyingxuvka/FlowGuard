---
name: flowguard-agent-workflow-rehearsal
description: Use when a non-trivial task may require multiple installed Codex skills, tools, plugins, external actions, staged validation, unclear skill ordering, skipped skill consequences, continue/rework gates, or cross-skill evidence claims. Start with a fresh current-machine SkillInventorySnapshot for this invocation, then rehearse the selected skills, skipped candidate skills, order, validation gaps, side effects, and final evidence claim before execution.
---

# FlowGuard Agent Workflow Rehearsal

This is a standalone FlowGuard satellite skill for rehearsing how an AI agent
plans to use the skills, tools, plugins, and external actions available in the
current session. Use it directly when the risky question is "which installed
capabilities should the agent use, in what order, and what happens if it skips
one?"

Return to `model-first-function-flow` when the basic FlowGuard route is
unclear. This skill is a peer route beside the other FlowGuard satellites; it
is not a global orchestrator and does not execute the planned workflow.

Skip only for tiny read-only answers, formatting-only edits, direct command
answers, or obvious low-risk single-skill work; record the skip reason.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- For real target-project use, ensure the FlowGuard AGENTS.md managed
  block/version record exists, or record why it was not updated.
- Do not create a fake mini-framework or prose-only substitute.
- Start every invocation with a fresh current-machine `SkillInventorySnapshot`.
  Cached or historical snapshots may help comparison, but they are not current
  evidence.
- Deep-read only the candidate skills likely to affect the task; keep unrelated
  skills represented by lightweight metadata.
- A rehearsal pass is permission to proceed, not proof that the downstream task
  is complete.
- Skipped, stale, weak, missing, manual-only, or external-only validation stays
  visible in the final claim boundary.

## Workflow

1. Take a fresh skill inventory for this machine/session. Include repository
   `.agents/skills`, installed Codex skills, and plugin/tool metadata visible
   in the current context.
2. Mark candidate skills, required skills, weak validation guidance, external
   side effects, and any skill bodies that need deeper reading.
3. Draft an `AgentWorkflowPlan`: selected skills, skipped candidate skills,
   ordered steps, required evidence, produced evidence, continue gates, rework
   gates, side effects, compensating checks, and final evidence claim.
4. Use `review_agent_workflow_rehearsal(...)` when package code is available,
   or follow the reference protocol if only prose review is possible.
5. If the result is `blocked`, stop execution until the plan is repaired. If it
   is `needs_revision`, revise the sequence, skipped-skill reasons, or gates.
   If it is `scoped`, proceed only with the reported evidence boundary.
6. During non-trivial use, default to a user-facing Mermaid agent-workflow
   rehearsal diagram showing candidate skills, selected route, skipped skills,
   continue/rework gates, evidence, side effects, and claim boundaries. Tiny
   tasks may stay concise. The diagram explains, not validates.

## Owned Helpers

- `SkillInventorySnapshot`
- `AgentWorkflowPlan`
- `review_agent_workflow_rehearsal(...)`
- `references/agent_workflow_rehearsal_protocol.md`

## Non-Goals

- Do not auto-run the planned skills or tools.
- Do not install, delete, update, or reorder skill files.
- Do not hardcode one developer machine's skills as the expected inventory.
- Do not replace OpenSpec, LogicGuard, FlowGuard satellites, browser tools,
  GitHub tools, document tools, or any other owning skill.
- Do not use rehearsal approval as a Risk Evidence Ledger pass or final
  done/release/publish proof.
