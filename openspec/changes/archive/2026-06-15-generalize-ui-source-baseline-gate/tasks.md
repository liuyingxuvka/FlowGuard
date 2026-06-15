## 1. Generic UI Source-Baseline Model

- [x] 1.1 Add generic UI work-mode, source-baseline, source interaction, target mapping, difference disposition, and observed-source alignment objects.
- [x] 1.2 Replace the source-specific UI interaction review helper with a generic source-baseline interaction review helper and remove old public API exports.
- [x] 1.3 Add source-baseline alignment review logic that catches missing source inventory, unapproved target drift, missing branch semantics, and no-handler controls without source-specific names.

## 2. Process And Risk Gates

- [x] 2.1 Replace source-specific DevelopmentProcessFlow artifact/evidence constants, stale reasons, templates, docs, and tests with generic source-baseline names.
- [x] 2.2 Replace source-specific RiskEvidenceLedger gate constants, finding codes, templates, docs, and tests with generic source-baseline interaction names.
- [x] 2.3 Update closure, model-miss, plan-detailing, and agent-workflow guidance/spec surfaces to consume source-baseline evidence generically.

## 3. Skills, Templates, And Public Guidance

- [x] 3.1 Update FlowGuard UI Flow Structure skill text and protocol so work mode is first and generic source-baseline gates apply only to source-based or mixed UI scope.
- [x] 3.2 Update installed Codex skill copies and repository skill/templates so active generic guidance contains no source-specific hard-gate wording.
- [x] 3.3 Update public templates, starter examples, README, API docs, and route docs to use generic source-baseline terminology.

## 4. Tests And Counterexamples

- [x] 4.1 Update UI structure tests for greenfield, source-based, mixed, unapproved source drift, missing source mapping, no-handler disposition, and generic interaction branch cases.
- [x] 4.2 Update development-process, risk-ledger, API-surface, public-template, and skill-doc tests for generic naming and removed old public API names.
- [x] 4.3 Add a guard test that active generic skills/templates/docs do not hard-code source-specific UI technology names while allowing historical logs.

## 5. Version, OpenSpec, And Validation

- [x] 5.1 Bump FlowGuard version metadata and changelog to 0.47.0.
- [x] 5.2 Validate the OpenSpec change and all current specs strictly.
- [x] 5.3 Run focused tests for UI/process/risk/API/templates/skill docs, then run the full regression.

## 6. Install, Shadow Sync, And Local Git

- [x] 6.1 Reinstall/editable-sync the local package and verify import path/version.
- [x] 6.2 Sync installed Codex FlowGuard skills and verify installed copies.
- [x] 6.3 Sync the local shadow workspace and verify import/version there.
- [x] 6.4 Record FlowGuard adoption evidence, perform KB postflight, commit local git changes, and tag the local version.
