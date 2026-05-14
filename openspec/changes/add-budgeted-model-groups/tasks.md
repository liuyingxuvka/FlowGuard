## 1. Model And API

- [x] 1.1 Add a FlowGuard self-model for the budgeted model-group workflow and run it before production code changes
- [x] 1.2 Add public budgeted graph/model-group configuration and report types
- [x] 1.3 Implement shard processing with a durable SQLite ledger, state deduplication, and resume
- [x] 1.4 Implement model fingerprinting and stale-ledger separation

## 2. Reporting And Compatibility

- [x] 2.1 Add whole-group complete/incomplete/failed reporting and text/JSON export helpers
- [x] 2.2 Add shard-local ten-step progress plus model-group summary progress
- [x] 2.3 Preserve existing `Explorer` progress and API behavior

## 3. Tests And Documentation

- [x] 3.1 Add tests for one-shard completion, multi-shard incomplete/complete behavior, resume, fingerprint separation, invariant failures, global labels, and duplicate prevention
- [x] 3.2 Add docs and an example showing how a FlowPilot-style model uses the budgeted model-group runner
- [x] 3.3 Update API surface tests and public API documentation

## 4. Release

- [x] 4.1 Update changelog and version for the new release
- [x] 4.2 Run focused and full validation
- [x] 4.3 Sync the editable install and the current shadow workspace
- [ ] 4.4 Commit, tag, push, and create the GitHub release
