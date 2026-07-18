# Internal Agent Workflow Protocol

`agent_workflow` is an internal `development_process_flow` route for capability
selection and sequencing across installed Codex skills, tools, plugins, or
external actions. Requests naming AgentWorkflowRehearsal or multi-capability
workflow review enter `flowguard-development-process-flow`; no separate Codex
skill, forwarding entrypoint, alias, or fallback route exists.

The route may reference OpenSpec, LogicGuard, public FlowGuard owners, browser
tools, GitHub, document plugins, or local skills as inventory entries. It does
not execute or supervise them. Each owning capability retains its own work and
validation.

## Fresh Inventory

Every invocation starts from a current-machine `SkillInventorySnapshot`.
Historical snapshots are comparison evidence only. Record each candidate's
name, description, source, trigger clues, relevance, limitations, side effects,
validation guidance, and whether its full instructions require deeper reading.

For non-trivial operations, recall same-plane `agent_operation` commitments
before selecting a new playbook. Product and process behavior remains typed
target context and never becomes an AI-operation owner.

## Plan Shape

Build an `AgentWorkflowPlan` with:

- selected and skipped candidates, reasons, consequences, accepted boundaries,
  and ordered `AgentWorkflowStep` rows;
- `behavior_plane=agent_operation` for AI steps plus separately typed target
  planes, commitment ids, and relation refs;
- prior evidence gates for side effects and irreversible actions;
- required/produced evidence, continue gates, and rework gates;
- compensating checks for weak, missing, manual-only, or external-only
  validation guidance;
- explicit UI, payload, manual, installed-skill-sync, and long-check evidence
  surfaces when applicable;
- a final evidence claim of none, scoped, full, or blocked.

If the work starts from a rough idea, the same public owner runs internal
`plan_detailing` first and projects the resulting rows into this route.

## Required Findings

Keep stale inventory, unaccounted candidates, unsupported skips, missing order,
missing evidence, side effects without gates, missing rework, weak validation,
UI/payload gaps, absent install sync, over-triggering, plane mismatch, and
missing cross-plane relations visible.

## Completion Boundary

The route passes only when the inventory is fresh, required candidates are
selected or explicitly scoped, steps and evidence gates are coherent, and the
planned final claim does not exceed downstream validation. It proves rehearsal
readiness only; native owners and the Risk Evidence Ledger still provide
terminal evidence.
