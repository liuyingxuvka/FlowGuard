## 1. Evidence Setup

- [x] 1.1 Capture the current public facade export snapshot before code changes.
- [x] 1.2 Build a FlowGuard architecture-reduction/process model for the public facade contraction.
- [x] 1.3 Run the model checks and record candidate proof status before production edits.

## 2. Public Facade Contraction

- [x] 2.1 Replace the duplicate hand-maintained `flowguard.__all__` list with a derived export declaration from `API_SURFACE`.
- [x] 2.2 Keep explicit supplemental exports for public names outside the grouped API.
- [x] 2.3 Add or update API-surface tests covering snapshot parity and supplement exports.

## 3. Validation And Sync

- [x] 3.1 Run targeted API, CLI, and template compatibility tests.
- [x] 3.2 Refresh the editable install and verify source import metadata.
- [x] 3.3 Sync changed files to the shadow workspace and verify shadow import/tests.
- [x] 3.4 Run broad unit and FlowGuard model regressions in the background and wait for final exit artifacts.

## 4. Finalization

- [x] 4.1 Validate OpenSpec change/spec state.
- [x] 4.2 Record FlowGuard adoption evidence and KB postflight observation if reusable.
- [x] 4.3 Commit the completed reduction locally and push the branch for review.
