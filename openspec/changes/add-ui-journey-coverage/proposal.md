## Why

UI Flow Structure can currently validate that a declared UI interaction model is
internally coherent, but it does not prove that an app-level UI has been modeled
from launch through every declared feature journey. This leaves room for agents
to claim "complete UI design" while omitting startup branches such as creating a
new project, loading an existing project, opening a recent project, cancelling,
recovering, or exiting.

## What Changes

- Add an app-level UI journey coverage surface that sits between the UI
  interaction model and downstream structure/text derivation.
- Add public helper objects for launch states, entry points, feature journeys,
  required path states/events, terminal states, recovery/cancel paths, and
  residual blindspots.
- Add `review_ui_journey_coverage(...)` so FlowGuard can reject incomplete
  launch-to-terminal coverage instead of only validating declared local states.
- Require complete app-level coverage to account for every reachable
  visible/enabled control branch and modeled event, so visible buttons do not
  become silent no-ops or unowned implementation work.
- Update the UI Flow Structure template, docs, Codex skill, README, and release
  materials so "complete UI" requires explicit journey coverage evidence.
- Preserve existing UI interaction, structure, and text hierarchy APIs for
  local/component-level modeling.

## Capabilities

### New Capabilities
- `ui-journey-coverage`: App-level UI journey coverage from launch state through
  declared entry points, feature paths, terminal or recovery states, and
  residual blindspots.

### Modified Capabilities
- `flowguard-ui-flow-structure`: Complete app-level UI work now requires journey
  coverage review before claiming that all declared UI functionality is modeled.

## Impact

- Affected package helper APIs in `flowguard/ui_structure.py` and exports in
  `flowguard/__init__.py`.
- Affected UI template generation in `flowguard/templates.py`.
- Affected tests in `tests/test_ui_structure.py` and public template/skill docs
  tests.
- Affected Codex skill guidance under
  `.agents/skills/flowguard-ui-flow-structure/` and reusable agent docs.
- Affected README, API docs, UI Flow Structure docs, CHANGELOG, version, release
  validation, installed skill sync, shadow workspace sync, and GitHub release.
