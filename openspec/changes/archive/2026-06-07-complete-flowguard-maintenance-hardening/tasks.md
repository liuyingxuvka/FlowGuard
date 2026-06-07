## 1. Planning And Spec Hygiene

- [x] 1.1 Validate the OpenSpec change artifacts before implementation.
- [x] 1.2 Replace active OpenSpec spec `Purpose: TBD` placeholders with useful capability purpose text.

## 2. Validation And Sync Tooling

- [x] 2.1 Add a tracked aggregate `.flowguard` model regression runner.
- [x] 2.2 Add a no-delete shadow workspace sync and verification helper.
- [x] 2.3 Add tests for model regression discovery and shadow sync verification behavior.
- [x] 2.4 Split GitHub CI into fast push validation and deep manual/scheduled validation, with Node 24 action runtime opt-in.

## 3. API, Field, And Structure Maintenance

- [x] 3.1 Add a compact `AGENT_DEFAULT_API` group and document it as the first-read agent surface.
- [x] 3.2 Add a field lifecycle inventory generator and generated field inventory documentation.
- [x] 3.3 Split Model-Test Alignment source-audit helpers into a dedicated module while preserving public imports.
- [x] 3.4 Update docs/tests for API grouping, field inventory, and structure split evidence.

## 4. Verification And Release

- [x] 4.1 Run focused tests for new scripts, API grouping, field inventory, and Model-Test Alignment compatibility.
- [x] 4.2 Run full local unit regression and aggregate FlowGuard model regression.
- [x] 4.3 Validate OpenSpec strict and FlowGuard project audit.
- [x] 4.4 Sync the shadow workspace without overwriting peer-only files, refresh/verifiy install state, and run shadow checks.
- [x] 4.5 Bump version and release materials after all maintenance tasks are complete.
- [x] 4.6 Commit, tag, push to GitHub, create a GitHub Release, and wait for GitHub CI.
- [x] 4.7 Archive the completed OpenSpec change and record FlowGuard/KB postflight evidence.
