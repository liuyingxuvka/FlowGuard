## Context

FlowGuard already has UI-visible-surface and UI-implementation-validation
helpers, plus RiskEvidenceLedger and ClosureContract gates for broad claims.
The remaining failure mode is narrower: agents can still start from their
declared model instead of the real rendered UI, prove labels or API existence
instead of click-to-effect behavior, and convert OpenSpec checkboxes into done
claims without current implementation evidence.

The change must fit the current route architecture. It should extend
`flowguard-ui-flow-structure`, `ui-implementation-validation`,
`post-runtime-model-miss-review`, lifecycle freshness, risk ledger, closure
contract, and skill guidance without creating a parallel UI route.

## Goals / Non-Goals

**Goals:**

- Make observed real UI inventory the first hard gate for existing/runnable UI
  claims.
- Require each observed visible item to map to the UI model or an explicit
  scoped blindspot.
- Require each enabled actionable control to prove a real function chain from
  visible control through owner code and observed UI result.
- Add MATLAB baseline callback semantics for migration parity.
- Make user-observed UI mismatch after green evidence a model miss, not a local
  patch-only bug.
- Ensure OpenSpec task completion records evidence type and status.
- Add a final done-claim review that blocks broad UI/release claims when
  evidence is planned, stale, manual-only, native-dialog-only, or unmapped.
- Keep installed skill copies, editable install, shadow workspace, and local
  Git surfaces synchronized for final confidence.

**Non-Goals:**

- Do not add a new top-level FlowGuard route for UI last-mile validation.
- Do not require browser automation for every native desktop flow; structured
  manual/native evidence remains allowed when declared and scoped.
- Do not require every project to run the heaviest UI rollout model before
  making a small scoped claim.
- Do not replace Model-Test Alignment, TestMesh, or ClosureContract.

## Decisions

### Observed inventory extends UI Flow Structure

Add observed inventory dataclasses and review helpers under
`flowguard.ui_structure` instead of a separate module. This keeps visible
surface, journey coverage, implementation validation, geometry evidence, and
real-surface inventory in one route.

Alternative considered: add a new route such as `ui-real-surface-gate`.
Rejected because the risk is part of UI Flow Structure, and splitting the route
would make agents choose between model UI and observed UI instead of requiring
both.

### Functional chains extend implementation validation

Add a first-class functional chain helper that binds observed control, UI event,
code owner, runtime/local/backend/native function, observed UI result, and
evidence reference. Implementation validation remains the owning runnable-UI
gate.

Alternative considered: rely on existing step evidence and `code_contract_id`
fields. Rejected because those fields are too implicit; API existence and label
matching can still be mistaken for real click-to-effect behavior.

### MATLAB semantics are a specialized UI baseline gate

Represent MATLAB migration parity as a UI baseline semantics gate with known
callback families: `uigetfile`, `uigetdir`, `winopen`, no-callback buttons,
choose/cancel/path/error/load-result branches, and manual/native boundaries.

Alternative considered: put MATLAB rules only in docs. Rejected because the
previous failure class is behavioral and needs executable bad-case tests.

### Done-claim review consumes sibling evidence

Add a focused final UI done-claim review that can be consumed by
RiskEvidenceLedger and ClosureContract. It should not inspect every sibling
route internally; it should record whether required evidence ids are current,
passing, scoped, stale, planned, or missing.

Alternative considered: embed final checks only in DevelopmentProcessFlow.
Rejected because risk-ledger and closure claims need a reusable decision object,
while DevelopmentProcessFlow owns freshness ordering.

### OpenSpec checkbox completion gains evidence metadata

Do not change OpenSpec's core file format. Instead, require FlowGuard task rows,
process rows, and skill guidance to treat UI checkboxes as unsupported unless
the row names evidence type, evidence status, and evidence reference or scoped
boundary.

## Risks / Trade-offs

- More required rows for UI work -> keep the compact route starter scoped and
  require the full gates only for existing/runnable/complete UI claims.
- Native dialogs may be hard to automate -> allow structured manual evidence
  but block broad claims when it is only planned or prose-only.
- Background regressions may still be running -> treat them as liveness only
  until final exit/result artifacts exist.
- Two local source roots exist in this machine -> validate both the current
  shadow workspace and the editable Git root before claiming sync.
- Other agents may write concurrently -> use narrow file scopes, avoid reset or
  checkout, and re-check touched-file status before synchronization.

## Migration Plan

1. Add OpenSpec deltas and tasks for the new hard gates.
2. Add UI inventory, functional chain, MATLAB callback, and UI done-claim
   helpers with focused bad-case tests.
3. Update Model Miss, plan detailing, development process, risk ledger,
   closure contract, agent workflow, public templates, docs, and Codex skills.
4. Run focused tests first, then broader regression commands.
5. Sync installed skill copies and editable install state.
6. Copy or apply the same changes to the local Git root only after checking
   current file status, then verify Git status and import paths.

## Open Questions

- Whether the next release should bump from `0.43.2` to a new public version is
  a release-management decision. This implementation can keep metadata aligned
  locally and report if no version bump was made.
