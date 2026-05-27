## 1. Specification and model refresh

- [x] 1.1 Capture maintenance/release boundary in OpenSpec.
- [x] 1.2 Refresh FlowGuard maintenance models so completed candidates are not
  reported as active ready work.
- [x] 1.3 Record the shadow duplicate cleanup as local sync evidence, not
  package behavior evidence.

## 2. Implementation and release metadata

- [x] 2.1 Update only the necessary FlowGuard model/docs/version artifacts.
- [x] 2.2 Keep public API, CLI command, and source behavior unchanged.
- [x] 2.3 Refresh release metadata for the new patch version.

## 3. Verification and sync

- [x] 3.1 Run OpenSpec strict validation.
- [x] 3.2 Run affected FlowGuard model checks.
- [x] 3.3 Run focused and full Python regression suites.
- [x] 3.4 Refresh editable install and verify installed version.
- [x] 3.5 Sync the local shadow workspace and remove stale duplicate artifacts
  only after path-bounded checks.

## 4. Repository release preparation

- [x] 4.1 Review final diff and repository status.
- [x] 4.2 Prepare commit, tag, and GitHub release notes from current evidence.
