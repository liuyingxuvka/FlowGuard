## 1. OpenSpec And FlowGuard Model Boundary

- [x] 1.1 Validate the OpenSpec proposal, design, specs, and task checklist.
- [x] 1.2 Add an executable FlowGuard self-model for latest-schema-first upgrade policy, deterministic upgrade, blocked unknown scripts, and safety-classifier preservation.
- [x] 1.3 Run the self-model before production edits and inspect counterexamples.

## 2. Artifact Upgrade Core

- [x] 2.1 Add artifact upgrade report dataclasses for scanned, upgraded, unchanged, skipped, and blocked items.
- [x] 2.2 Add deterministic upgrade rules for known obsolete FlowGuard API aliases and current-schema artifact envelope checks.
- [x] 2.3 Add repository scan helpers for `.flowguard`, docs, tests, examples, scripts, and FlowGuard skill guidance.
- [x] 2.4 Add dry-run and apply behavior that writes only deterministic upgrades and reports blocked/manual-review items.

## 3. Project Upgrade Integration

- [x] 3.1 Extend `project-upgrade` so older adopted repositories run artifact/model/test/guidance upgrade scanning by default.
- [x] 3.2 Add a records-only option for the previous narrow AGENTS/manifest/adoption-record update behavior.
- [x] 3.3 Include upgrade report summaries in project adoption reports and adoption log entries.
- [x] 3.4 Update CLI dispatch and public API exports for the new upgrade capability.

## 4. Guidance And Cleanup Policy

- [x] 4.1 Update AGENTS snippets, API surface docs, modeling protocol, README/changelog, and public templates with latest-schema-first wording.
- [x] 4.2 Update owned FlowGuard skill guidance so agents upgrade or block old artifacts rather than preserving compatibility fields.
- [x] 4.3 Audit compatibility/legacy references touched by this change and preserve safety classifiers while marking runtime shims as cleanup candidates.

## 5. Tests And Validation

- [x] 5.1 Add focused tests for artifact upgrade dry-run/apply, blocked unknown scripts, and current-schema-only runtime policy.
- [x] 5.2 Add focused tests for project-upgrade default scan behavior and records-only behavior.
- [x] 5.3 Add docs/skill/API tests that prevent old alias guidance from returning.
- [x] 5.4 Run OpenSpec validation, FlowGuard self-model checks, focused pytest, project audit, install import checks, shadow workspace checks, and the strongest practical regression.

## 6. Sync And Release Surface

- [x] 6.1 Bump local package version and changelog for the intentional breaking cleanup policy.
- [x] 6.2 Refresh editable install and verify `flowguard.__file__`, package version, schema, and new API availability.
- [x] 6.3 Sync affected repository-managed FlowGuard skills into installed Codex skills and verify content parity.
- [x] 6.4 Sync the git repository source to the `FlowGuard_20260427` shadow workspace without reverting peer-agent changes.
- [x] 6.5 Record FlowGuard adoption evidence and KB postflight.
- [x] 6.6 Commit local git changes and create a local version tag only after validation and sync evidence pass.
