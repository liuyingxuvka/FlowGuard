## Why

UI Flow Structure can now prove that a complete app UI is modeled from launch
through visible control branches, but it still treats browser QA, frontend
implementation, and real click-through evidence as downstream notes. That
leaves a gap where agents can claim an implemented UI is complete while the
feature model, UI journey model, and actual running interface have not been
checked against each other.

## What Changes

- Add a UI implementation validation surface that consumes a user-visible
  feature inventory, the reviewed UI interaction model, and reviewed UI journey
  coverage before accepting real UI completion claims.
- Add public helper objects for user-visible feature contracts, implementation
  journey runs, implementation step evidence, and residual implementation
  blindspots.
- Add `review_ui_implementation_validation(...)` so FlowGuard can reject
  feature-model gaps, UI-only controls with no functional owner, missing
  click-through evidence, stale or incomplete evidence, and unbounded manual or
  browser validation gaps.
- Update the UI Flow Structure skill, protocol, template, docs, and release
  checklist so "UI model complete" remains separate from "running UI verified".
- Preserve the current model-first route for design-only work: real UI
  click-through evidence is required only when a user or release claim says the
  implemented UI is complete or runnable.

## Capabilities

### New Capabilities
- `ui-implementation-validation`: Real UI implementation validation that aligns
  user-visible feature contracts, UI journey coverage, and browser/manual
  click-through evidence.

### Modified Capabilities
- `flowguard-ui-flow-structure`: Complete implemented UI claims require a
  downstream implementation validation gate after model, journey, structure,
  and text hierarchy evidence.

## Impact

- Affected package helper APIs in `flowguard/ui_structure.py` and exports in
  `flowguard/__init__.py`.
- Affected UI template generation in `flowguard/templates.py`.
- Affected tests in `tests/test_ui_structure.py`, `tests/test_api_surface.py`,
  and public template tests.
- Affected Codex skill guidance under
  `.agents/skills/flowguard-ui-flow-structure/` and reusable agent docs.
- Affected UI Flow Structure docs, API docs, README, release checklist, local
  FlowGuard self-model, installed skill sync, local editable install, and shadow
  workspace verification.
