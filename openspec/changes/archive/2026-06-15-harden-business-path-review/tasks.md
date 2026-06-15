## 1. Preflight and Change Boundary

- [x] 1.1 Run predictive KB, OpenSpec, and FlowGuard route preflight.
- [x] 1.2 Create proposal, design, and capability delta specs.
- [x] 1.3 Validate the OpenSpec change in strict mode before implementation.
- [x] 1.4 Recheck real FlowGuard package import, package version, and project audit before production edits.

## 2. Business Path Topology Model

- [x] 2.1 Add `BusinessPathIdentity` and business-path digest serialization.
- [x] 2.2 Add business-path anchors to topology digests and inferred plans.
- [x] 2.3 Infer duplicate, conflict, unproven, and legacy-disposition business-path landmarks.
- [x] 2.4 Map business-path landmarks to existing candidate dispositions and owner routes.

## 3. Similarity and Runtime Evidence

- [x] 3.1 Add business-path ids, intents, and terminals to model similarity signatures and evidence.
- [x] 3.2 Classify same-path and false-friend sibling models using business-path overlap and divergence.
- [x] 3.3 Add optional business-path binding fields to runtime contracts and observations.
- [x] 3.4 Report wrong-path or missing-path runtime evidence as explicit review findings.

## 4. Maintenance and Risk Integration

- [x] 4.1 Add maintenance scan signals for duplicate, conflict, unproven, and legacy-disposition business-path hazards.
- [x] 4.2 Route business-path maintenance signals to existing FlowGuard owner routes.
- [x] 4.3 Ensure risk evidence and final confidence guidance can consume business-path topology/runtime evidence.

## 5. Prompts, Templates, Docs, and API Surface

- [x] 5.1 Update model-first and topology-hazard skill guidance to request business-path identity.
- [x] 5.2 Update public template text for topology hazard, model similarity, and runtime path examples.
- [x] 5.3 Update docs and API surface references for the new path metadata and exports.
- [x] 5.4 Export the new API symbols from `flowguard.__init__`.

## 6. Tests and Validation

- [x] 6.1 Add topology hazard tests for duplicate, conflict, unproven, and old/new disposition paths.
- [x] 6.2 Add model similarity tests for shared business paths and terminal divergence.
- [x] 6.3 Add runtime path tests for expected, missing, and wrong business-path bindings.
- [x] 6.4 Add maintenance scan/API/template tests for new signals and exported symbols.
- [x] 6.5 Run targeted pytest suites and fix failures.
- [x] 6.6 Run OpenSpec validation and FlowGuard project audit after implementation.

## 7. Version, Install, Shadow Workspace, and Git Sync

- [x] 7.1 Bump package/version references for the upgrade.
- [x] 7.2 Reinstall the editable local package and verify import path, package version, schema version, and exported symbols.
- [x] 7.3 Sync the shadow workspace and verify it imports the upgraded local version.
- [x] 7.4 Record FlowGuard adoption evidence and final Git status without overwriting unrelated local work.
- [x] 7.5 Run KB postflight and record any reusable lesson or route gap.
