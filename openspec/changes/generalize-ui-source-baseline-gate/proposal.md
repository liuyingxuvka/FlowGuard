## Why

FlowGuard UI currently has strong implementation, visible-surface, and human-operability checks, but one migration-specific source profile leaked into generic UI skill guidance, public APIs, templates, and risk/process gates. That makes a general UI skill look as if every source-based UI job depends on one particular legacy tool instead of first classifying whether the job is greenfield, source-based, or mixed.

This change restores the generic boundary: UI work must first declare its work mode, source-based work must compare Source Baseline -> Target UI -> Observed UI, and greenfield work must not be forced through a legacy-source gate.

## What Changes

- Add a generic UI source-baseline capability for source-based and mixed UI work.
- Require UI work to classify `greenfield`, `source_based`, or `mixed` before applying source-baseline gates.
- Require source-based UI work to map source pages/regions/items/interactions/tasks to target UI items and record every preserve/move/rename/merge/split/replace/hide/delete/defer/new disposition.
- Require observed UI validation for source-based scopes to compare both the target model and the approved source-baseline mapping, preventing target-model self-consistency from hiding source drift.
- **BREAKING**: Remove generic public API, process evidence, risk gate, template, docs, and installed-skill wording that names a specific legacy UI technology. Replace it with generic source-baseline interaction names and generic interaction kinds.
- Update OpenSpec, FlowGuard route guidance, template starters, tests, API docs, installed Codex skills, local install, shadow workspace, local git, and version metadata.

## Capabilities

### New Capabilities
- `ui-source-baseline-validation`: Generic UI source-baseline modeling, source-target mapping, approved difference dispositions, and observed-source alignment for source-based and mixed UI work.

### Modified Capabilities
- `flowguard-ui-flow-structure`: Add work-mode routing and source-baseline hard gates for source-based UI without requiring those gates for greenfield UI.
- `development-process-flow`: Replace specific source-profile artifact/evidence freshness with generic UI source-baseline freshness.
- `risk-evidence-ledger`: Replace specific source-profile risk gate naming with generic UI source-baseline interaction evidence.
- `flowguard-closure-contract`: Require source-baseline alignment evidence for final source-based UI claims.
- `plan-detailing-compiler`: Require UI plans to name work mode, source scope, target differences, evidence types, and must-fail counterexamples.
- `post-runtime-model-miss-review`: Classify user-reported page/region/task/source drift after green UI evidence as a source-target model miss.
- `flowguard-agent-workflow-rehearsal`: Generalize multi-agent UI evidence roles to source-baseline inventory, task-flow review, and implementation validation roles.
- `flowguard-codex-skill-satellites`: Ensure installed FlowGuard UI skills present generic source-baseline guidance and do not hard-code a legacy source technology in the general route.

## Impact

- Public Python API names for UI source interaction semantics and source-baseline review.
- DevelopmentProcessFlow artifact/evidence constants and freshness reasons.
- RiskEvidenceLedger gate constants and finding codes.
- UI Flow Structure templates, public template tests, and API-surface tests.
- Codex skill text under `.agents/skills` and installed skill copies under the user Codex skills directory.
- Docs, README, changelog, OpenSpec specs, and local adoption records.
- Version metadata, editable install, shadow workspace sync, local git commit/tag.
