## Why

AI agents now have many local Codex skills, plugins, and project-specific
workflows available at the same time. For non-trivial tasks, choosing the
wrong skill order, skipping a relevant skill, or claiming completion without
current evidence can break the work even when each individual skill is valid.

FlowGuard should add a peer satellite skill that rehearses the agent's planned
multi-skill workflow against the current machine's installed skills before
execution.

## What Changes

- Add a directly invokable FlowGuard satellite skill:
  `flowguard-agent-workflow-rehearsal`.
- Add a portable `SkillInventorySnapshot` step that runs fresh on every
  rehearsal invocation and captures the skills available on the current
  machine/session.
- Add an executable FlowGuard model and package helper for reviewing an
  `AgentWorkflowPlan`: selected skills, skipped candidate skills, skill order,
  continue gates, rework gates, side effects, validation gaps, and final
  evidence claims.
- Update global FlowGuard routing guidance so Codex can select this satellite
  before non-trivial multi-skill work.
- Update Codex skill topology docs/tests so the new satellite is discoverable
  beside the existing FlowGuard peer skills.
- Keep the skill as a rehearsal and validation gate only. It does not auto-run
  tasks, auto-install skills, or replace the owning skills it recommends.

## Capabilities

### New Capabilities
- `flowguard-agent-workflow-rehearsal`: Rehearse an AI agent's planned use of
  installed Codex skills and tools before execution, using a fresh current
  skill inventory and explicit continue/rework/evidence gates.

### Modified Capabilities
- `flowguard-global-routing`: Route non-trivial multi-skill workflow planning
  to `flowguard-agent-workflow-rehearsal` before execution.
- `flowguard-codex-skill-satellites`: Include
  `flowguard-agent-workflow-rehearsal` as a directly invokable FlowGuard
  satellite skill and require installed-skill synchronization coverage.

## Impact

- New package module: `flowguard/agent_workflow_rehearsal.py`.
- New example model and runner under
  `examples/flowguard_agent_workflow_rehearsal/`.
- New Codex skill under
  `.agents/skills/flowguard-agent-workflow-rehearsal/`.
- Updates to `docs/agents_snippet.md`,
  `.agents/skills/model-first-function-flow/SKILL.md`, skill docs tests, and
  package exports where needed.
- New tests for the rehearsal model, skill topology, and prompt guidance.
