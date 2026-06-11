## Why

AgentWorkflowRehearsal already reviews skill ordering and evidence gates before
execution, but its report should expose a compact completion ledger so agents
can see planned work, blocked work, skipped skills, required rechecks, handoff
points, and the final claim boundary without rereading all findings.

## What Changes

- Add completion-ledger fields to `AgentWorkflowRehearsalReport`.
- Populate the ledger from the plan and findings.
- Update skill and protocol guidance to require the ledger in non-trivial
  rehearsals.
- Add focused tests for ledger fields.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `flowguard-agent-workflow-rehearsal`: Reports a compact completion ledger
  alongside existing status and findings.

## Impact

- Updates `flowguard/agent_workflow_rehearsal.py`.
- Updates agent workflow rehearsal skill guidance and protocol reference.
- Updates tests and installed FlowGuard skill sync.
