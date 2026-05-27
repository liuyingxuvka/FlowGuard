## 1. Template Contract

- [x] 1.1 Update the public `model-miss-template` generated model to track the observed issue, same-class generalized bad case, and known-bug holdout role.
- [x] 1.2 Make template completion fail when only the observed issue is encoded.
- [x] 1.3 Update generated notes so they state that the known bug is validation/holdout evidence, not the model target.

## 2. Checks

- [x] 2.1 Add or update focused public-template tests for observed issue plus same-class generalized bad case.
- [x] 2.2 Add a broken point-fix-only scenario or mutation that must fail before the corrected template passes.
- [x] 2.3 Run the generated `model-miss-template` checks and focused public-template tests.

## 3. Release Sync

- [x] 3.1 Update package version metadata and `CHANGELOG.md` for the template hardening release.
- [x] 3.2 Sync the installed local FlowGuard Skill from source and verify its model-miss guidance.
- [x] 3.3 Sync the configured shadow workspace and verify imports/checks from that workspace.
- [x] 3.4 Run OpenSpec validation and final version/changelog/skill/shadow alignment checks.
