# UI Human Operability Protocol

Use this protocol when the claim says usable, understandable, human-operable, complete, or release-ready.

Use `UIUserTaskFrame`, `UIUserTaskCoverageLedger`, `UIRegionSemanticMap`, `UIAffordanceContract`, `UIActionGrammar`, `UIDialogWindowContract`, `UIKeyboardFocusContract`, `UIHumanWalkthroughScenario`, `UIHumanWalkthroughStep`, `UIHumanOperabilityAssessment`, and `review_ui_human_operability(...)` when available.

## Required package

- Inventory every supported user-visible feature and task, not one convenient happy path.
- Link feature -> task -> journey/control/functional chain, with owner/reason/boundary for scoped tasks.
- Give each task a goal, entry state, main/alternate/cancel/error path, success state, visible feedback, required controls/displays/dialogs, keyboard contract, and evidence refs.
- Give every prominent/primary control exactly one owning task/intent in a state.
- Classify region semantics: input, action, result, status, recovery, navigation, or dialog.
- Classify visible affordances as clickable, editable, selectable, read-only, status-only, or decorative.
- Define action grammar with intent, primary/alternate controls, conflicts, preconditions, next state, feedback, and duplicate policy.
- Define native/custom dialog success, cancel, error, selected value/path, focus return, feedback, native/manual boundary, and evidence.
- Define Tab/Enter/Escape, disabled-control skip, error focus, and dialog focus return.
- Record walkthrough prompt, action, expected/actual feedback, evidence, confusion, and mitigation.

## Blockers

Block incomplete feature/task coverage, primary controls without tasks, misleading affordances, two primary controls for one intent/state, dialogs without cancel/error/focus/feedback, unreachable keyboard tasks, walkthrough confusion without mitigation, and manual/native evidence without a structured boundary.

Human-operability evidence proves only the declared tasks and revision. It does not replace implementation click-through or geometry evidence.
