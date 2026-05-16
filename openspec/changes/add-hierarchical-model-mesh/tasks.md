## 1. FlowGuard Preflight

- [x] 1.1 Add a FlowGuard self-model for hierarchical mesh rollout and run it before production code changes
- [x] 1.2 Record the risk intent and adoption evidence for the implementation and release

## 2. Helper API And Review Logic

- [x] 2.1 Add hierarchy helper types for coverage items, child evidence, partition maps, mesh findings, and mesh decisions
- [x] 2.2 Implement partition coverage checks, sibling overlap checks, and ownership conflict checks
- [x] 2.3 Implement model-count and large-model activation triggers plus split-review decisions
- [x] 2.4 Implement legacy model classification and compatibility-contract review
- [x] 2.5 Export the new helper APIs and include them in API surface metadata

## 3. Examples And Documentation

- [x] 3.1 Add a nested hierarchy example with root, children, grandchildren, and required bad variants
- [x] 3.2 Document hierarchical mesh concepts, partition maps, overlap handling, large-model triggers, and legacy compatibility
- [x] 3.3 Update README, modeling protocol, model mesh protocol, and changelog/version notes

## 4. Tests And Validation

- [x] 4.1 Add unit tests for coverage gaps, allowed shared reads, duplicate ownership, stale/skipped evidence, quantity triggers, large-model triggers, and legacy review
- [x] 4.2 Run focused tests, example checks, compile checks, and full test suite
- [x] 4.3 Run or inspect background model/regression checks and fix failures

## 5. Release And Sync

- [x] 5.1 Sync editable local install and verify installed/imported package version
- [x] 5.2 Sync the shadow workspace and verify imports/tests from both workspaces
- [x] 5.3 Commit, tag, push, and create the new GitHub release
