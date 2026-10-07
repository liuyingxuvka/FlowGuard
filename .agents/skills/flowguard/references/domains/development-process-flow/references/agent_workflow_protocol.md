# Internal Agent Workflow Protocol

`agent_workflow` is an internal `development_process_flow` route for capability
selection and sequencing across skills, tools, plugins, or external actions.
Requests explicitly naming AgentWorkflowRehearsal or carrying an admitted
shared-write, post-validation-invalidating-write, agent/route workflow-change,
or multiple-independent-owner irreversible-risk fact enter
`DevelopmentProcessFlow`; no public alias exists. Capability labels alone
stay `not_triggered`. An ordinary cross-owner handoff uses the existing
DevelopmentProcessFlow freshness review; shared writes, post-validation
invalidation, route changes, multiple-owner irreversible effects, and an
explicit rehearsal request still enter this route.

The route references other skills, tools, plugins, or external actions as
inventory only; it does not execute or supervise them, and each owner retains
its work and validation.

## Fresh Inventory

Every invocation starts from a current-machine `SkillInventorySnapshot`.
Historical snapshots are comparison evidence only. Record each candidate's
name, description, source, trigger clues, relevance, limitations, side effects,
validation guidance, and whether its full instructions require deeper reading.

For non-trivial operations, recall same-plane `agent_operation` commitments
before selecting a new playbook. Product and process behavior remains typed
target context and never becomes an AI-operation owner.

An invocation is one admitted bounded workflow decision, not every tool call,
file edit, progress update, or peer completion. Read the current available
capability catalog once when this decision opens; deeply read only selected
capabilities and their named dependencies. Freeze selected owners, ordered
steps, disjoint write sets, evidence dependencies, and the diagnostic boundary
for that batch. A completed step continues the same batch and does not reopen
skill discovery or rehearsal. Reopen only the affected decision when a real
capability/owner/side-effect/dependency/accepted-scope fact changes. A resumed
session must recheck current availability before relying on an old plan; an
old snapshot never becomes current merely because its id matches.

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
