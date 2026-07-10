# UI Implementation Evidence Protocol

Use this protocol only when claiming that a running UI is implemented, runnable, complete, or functionally wired. Model, journey, structure, and text artifacts are design evidence, not runtime proof.

Use `UIFeatureContract`, `UIImplementationValidation`, `UIImplementationJourneyRun`, `UIImplementationStepEvidence`, `UIImplementationBlindspot`, `UIRenderEvidenceSet`, `UIRenderEvidence`, `UIControlFunctionalChainSet`, and the corresponding review helpers.

## Functional chain

Every reachable enabled non-pure-UI action requires:

```text
visible control -> UI event -> code owner -> backend/local function
-> UI state update -> click/test evidence
```

Record implementation target/revision, model revision, feature/journey/control/event mappings, step source/target states, observed result/state, evidence reference, and failure/recovery/cancel/exit evidence. API/route existence and label matching are insufficient.

## Source-based and mixed semantics

Use `UISourceBaseline`, `UISourceTargetMapping`, `UIObservedSourceAlignment`, `UISourceBaselineInteractionGate`, and their reviewers. Preserve trigger, confirm, cancel, selected value, result feedback, external effect, error, navigation, command, and no-handler/no-op disposition for native pickers, saves, external opens, custom dialogs, and source controls. Greenfield work must not invent a source baseline.

## Evidence kinds

Screenshot, browser/desktop click-through, DOM text, computed style, geometry, accessibility/ARIA, runtime trace/log, test result, and manual observation require a current model/implementation revision and evidence reference. Manual/native-dialog steps need structured observed-result rows and scoped boundaries.

Block enabled controls/events without feature/pure-UI/run/blindspot ownership, capability outputs without assertions, missing implementation runs, unknown states/events/controls, stale/failed/skipped/not-run evidence, missing failure/recovery/cancel paths, or blindspots without owner/reason/boundary/rationale.

Implementation validation proves only the executed current paths. It does not prove unvisited controls, future behavior, visual quality, or semantic transition coverage.
