## 1. Failure-Class Coverage

- [x] 1.1 Add an observed regression for a snapshot-declared model input that exists locally but is not Git-tracked.
- [x] 1.2 Add same-class coverage for an untracked runner input and for exact annotated-tag query behavior.

## 2. Release-Gate Repair

- [x] 2.1 Implement fail-closed extraction and Git reachability checks for the selected observed snapshot input closure.
- [x] 2.2 Replace the caret-bearing remote tag query with an exact-prefix query whose parser still requires the exact peeled tag.
- [x] 2.3 Add the 49 current snapshot inputs that were ignored by Git to the committed source inventory.

## 3. Authority And Version Closure

- [x] 3.1 Update version and release records for the corrective patch release.
- [x] 3.2 Refresh observed model authority through one accepted revision and confirm all new authority inputs are Git-tracked.
- [x] 3.3 Validate OpenSpec and hand the completed change to the official archive owner without leaving a compatibility path.

## 4. Verification And Publication

- [x] 4.1 Run focused tests plus an exact clean-clone model-system and project audit.
- [x] 4.2 Run affected-only validation, one frozen full gate, and a stable zero-execute reuse plan.
- [x] 4.3 Historical release disposition: the unreleased v0.64.2 publication target is superseded by the preserving v0.65.0 release handoff; its parser and reachability intent remains integrated and separately committed.
