## Design Goals

1. Treat user tasks as the unit that connects functional capability to UI.
2. Reject technically wired but confusing UI before broad completion claims.
3. Keep the added model explicit and testable rather than relying on prose
   usability judgment.
4. Preserve existing UI Flow gates: observed surface, functional chain,
   source interaction semantics, journey coverage, text hierarchy, geometry, and
   implementation validation remain valid.

## Model Shape

Add a human-operability layer to `flowguard.ui_structure`:

- `UIUserTaskFrame`: one user task, including entry conditions, main path,
  alternate path, cancel path, error path, success state, required feedback,
  required controls/displays/dialogs, keyboard path, and evidence.
- `UIUserTaskCoverageLedger`: the task coverage total ledger. It links
  functional features to task frames, task frames to UI journeys/controls, task
  frames to functional chains, and records uncovered features, orphan primary
  controls, out-of-scope tasks, and rationale.
- `UIRegionSemanticMap`: semantic ownership of functional regions such as file
  input, action, result, status, recovery, navigation, or dialog.
- `UIAffordanceContract`: perceived role versus actual role for a visible item,
  visual/interaction cues, expected action, expected result, and mismatch
  disposition.
- `UIActionGrammar`: one semantic action row, including primary control,
  alternates, conflicts, preconditions, next state, feedback, and duplicate
  policy.
- `UIDialogWindowContract`: trigger, dialog type, modal behavior, success,
  cancel, error, focus return, feedback, and manual/native boundary.
- `UIKeyboardFocusContract`: tab order, default Enter, Escape behavior, focus
  return, disabled skip policy, error focus, and rationale.
- `UIHumanWalkthroughScenario` and `UIHumanWalkthroughStep`: structured first
  time/expert task runs with visible prompt, user action, expected feedback,
  actual feedback, confusion flag, and evidence.
- `UIHumanOperabilityAssessment`: the aggregate review input.
- `review_ui_human_operability(...)`: the gate that produces
  `UIHumanOperabilityReport`.

## Review Rules

The review should fail or scope broad human-operable confidence when:

- an in-scope user-visible feature has no user task;
- an in-scope user task lacks a task flow model;
- a task has no UI journey/control path;
- a primary UI control belongs to no user task;
- a task claims success without visible feedback;
- a visible item's perceived role conflicts with actual role;
- an actionable item lacks visible or interaction cues;
- a non-actionable item looks actionable without a safe mismatch disposition;
- two same-level primary controls express the same semantic action;
- path input and native picker options are not coordinated;
- a dialog has no cancel/error/focus return semantics;
- keyboard Tab/Enter/Escape behavior is missing for a task path;
- a functional region contains controls/displays outside its semantic role;
- a walkthrough lacks prompt, action, feedback, evidence, or reports confusion
  without mitigation.

## Route Integration

- UI Flow Structure owns the model and core review helper.
- UI Implementation Validation must require a current human-operability report
  before runnable/complete/human-operable UI claims.
- Model Miss Review must classify user-observed confusion as a UI model miss.
- PlanDetailing and DevelopmentProcessFlow must carry human-operability
  evidence types and freshness.
- RiskEvidenceLedger and ClosureContract must block broad done/release claims
  when human-operability evidence is missing, stale, planned, or scoped.
- AgentWorkflowRehearsal must add a UI evidence role for human-operability
  review in multi-agent UI work.

## Compatibility

This is an additive public API expansion. Existing UI models remain valid for
design-only or technically wired claims. Human-operable and release-ready UI
claims gain additional required evidence.

## Versioning

Use a minor version bump because this adds a new public model layer and route
surface.
