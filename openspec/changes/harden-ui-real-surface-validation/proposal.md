## Why

FlowGuard's UI route already models visible surfaces and implementation
validation, but agents can still overclaim UI completion when the real rendered
page was never inventoried, when a button only has a label or API endpoint, or
when native source-interaction semantics were not exercised. This change
locks the final mile: every real visible UI item must be accounted for, every
enabled action must prove a real function chain, and final done claims must
stay scoped when implementation evidence is missing, planned, stale, or manual
only.

## What Changes

- Add a rendered/observed UI surface inventory gate that runs before UI modeling
  can be called complete for an existing or runnable UI.
- Require each observed button, input, select, table, display field, status
  message, native dialog trigger, and visible command to map to a `UIControl`,
  `UIDisplayElement`, or `UIVisibleSurfaceItem`, or to a scoped blindspot.
- Add an enabled-control functional chain gate:
  visible control -> UI event -> code owner -> backend/local/native function ->
  observed UI state/display update -> evidence.
- Add a generic source-baseline interaction semantics gate for native pickers,
  external opens, save/custom dialogs, no-handler controls,
  trigger/confirm/cancel/value/result/error branches, and source-based parity
  claims.
- Treat user-observed UI mismatch after green FlowGuard evidence as a Model Miss
  with previous-claim backpropagation, same-class scan, and same-class tests.
- Require OpenSpec/UI task completion to name evidence type and evidence status;
  a checkbox alone does not support a UI completion claim.
- Add a final done-claim review that downgrades full UI/release claims when
  native dialogs, manual signoff, planned evidence, missing implementation
  validation, or unmapped visible items remain.
- Add multi-agent UI evidence roles to workflow rehearsal: UI inventory,
  source-baseline mapping/alignment, and implementation validation evidence
  packets.
- Sync repository skill guidance, public templates, docs, tests, editable
  install, shadow workspace, and local Git surfaces before release confidence.

## Capabilities

### New Capabilities

- None. The change hardens existing FlowGuard UI, process, model-miss, closure,
  and skill-satellite capabilities instead of adding a separate top-level
  route.

### Modified Capabilities

- `flowguard-ui-flow-structure`: require observed real-surface inventory as the
  first hard gate for existing/runnable UI claims and add generic
  source-baseline interaction semantics for source-based parity.
- `ui-implementation-validation`: require enabled controls to prove a real
  functional chain and implementation validation before runnable/complete UI
  claims.
- `post-runtime-model-miss-review`: classify user-visible UI mismatch after a
  green claim as a model miss with same-class UI scans and tests.
- `plan-detailing-compiler`: require UI tasks to carry evidence type and status
  instead of relying on checkbox completion.
- `development-process-flow`: treat UI inventory maps, functional chains,
  native/manual boundaries, installed-skill sync, shadow sync, and Git sync as
  freshness-sensitive artifacts.
- `risk-evidence-ledger`: require final broad confidence to consume current UI
  real-surface, implementation-validation, and done-claim evidence or report a
  scoped blindspot.
- `flowguard-closure-contract`: block full done/release claims when planned
  evidence, missing manual signoff, native-dialog blindspots, unmapped visible
  items, or missing implementation validation remain.
- `flowguard-agent-workflow-rehearsal`: model UI inventory, source-baseline
  mapping/alignment, and implementation validation as distinct role evidence
  packets.
- `flowguard-codex-skill-satellites`: align installed and repository Codex
  skill prompts with the new first-gate and final-claim wording.

## Impact

- Core code: `flowguard/ui_structure.py`, `flowguard/plan_detailing.py`,
  `flowguard/development_process_flow.py`, `flowguard/risk_evidence_ledger.py`,
  `flowguard/closure_contract.py`, `flowguard/agent_workflow_rehearsal.py`, and
  `flowguard/recurring_model_miss.py`.
- Public API/docs/templates: `flowguard/__init__.py`,
  `flowguard/template_text/*`, `docs/*.md`, `README.md`, and public template
  tests.
- Skill guidance: `.agents/skills/flowguard-ui-flow-structure/*`,
  `.agents/skills/flowguard-model-miss-review/*`,
  `.agents/skills/flowguard-development-process-flow/*`,
  `.agents/skills/flowguard-agent-workflow-rehearsal/*`, and installed Codex
  skill copies.
- Validation: focused unit tests for the new gates, OpenSpec validation,
  project audit, editable-install verification, shadow-workspace verification,
  and local Git synchronization.
