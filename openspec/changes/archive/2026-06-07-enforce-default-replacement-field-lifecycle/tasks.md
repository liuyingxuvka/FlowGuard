## 1. OpenSpec And Model Setup

- [x] 1.1 Validate the new OpenSpec proposal, design, and spec deltas.
- [x] 1.2 Add a FlowGuard self-model for default replacement and field lifecycle closure.
- [x] 1.3 Add focused model checks that reject missing field coverage, missing behavior projection, unknown old-field disposition, stale model-code-test binding, and point-fix-only bug repair.

## 2. Field Lifecycle Runtime Surface

- [x] 2.1 Add `flowguard/field_lifecycle.py` with field groups, field rows, projections, dispositions, findings, reports, and review helpers.
- [x] 2.2 Export the new helper types through route-scoped public API groups and `flowguard.__init__`.
- [x] 2.3 Add field lifecycle text and JSON formatting for human and AI handoff use.

## 3. Existing Route Integration

- [x] 3.1 Extend existing-model preflight to surface field lifecycle ownership and field model gaps.
- [x] 3.2 Extend model-first guidance/helpers to require behavior-bearing field projection or scoped-out reasons.
- [x] 3.3 Extend Code Structure Recommendation to consume field reader/writer/owner maps.
- [x] 3.4 Extend Architecture Reduction and legacy disposition handling to classify and close old fields.
- [x] 3.5 Extend Model-Test Alignment to consume field projections and require model obligation, code contract, and test evidence binding.
- [x] 3.6 Extend Model-Miss Review guidance and closure rows to include field root cause, same-class field cases, and old-field disposition.
- [x] 3.7 Extend DevelopmentProcessFlow freshness rules for field lifecycle, field projection, replacement, and bug repair closure evidence.
- [x] 3.8 Extend Closure Contract to consume field lifecycle and replacement disposition evidence.

## 4. Guidance, Docs, And Templates

- [x] 4.1 Update AGENTS/docs snippets and route docs with the default replacement policy and field lifecycle layer.
- [x] 4.2 Update affected `.agents/skills/*/SKILL.md` and reference protocol files.
- [x] 4.3 Update `flowguard/template_text/*` public templates with compact field/replacement handoff guidance.
- [x] 4.4 Add or update user-facing docs for FieldLifecycleMesh and the full bug repair loop.

## 5. Tests And Validation

- [x] 5.1 Add unit tests for field lifecycle review and projections.
- [x] 5.2 Add focused integration tests for Model-Test Alignment, Architecture Reduction, legacy disposition, Model-Miss Review, DevelopmentProcessFlow, Closure Contract, API surface, template text, and skill docs.
- [x] 5.3 Run OpenSpec strict validation for the change and all specs.
- [x] 5.4 Run FlowGuard self-model checks and focused unit tests.
- [x] 5.5 Run practical regression; use background execution for long runs and consume final artifacts before confidence claims.

## 6. Sync, Version, And Adoption Evidence

- [x] 6.1 Update version/changelog records if the public API changes warrant a package increment.
- [x] 6.2 Run editable install and verify `flowguard.__file__`, package metadata version, schema version, and new feature availability.
- [x] 6.3 Sync installed Codex skill copies and verify content parity for affected skills.
- [x] 6.4 Sync the local git repository and shadow workspace as complete source sets without overwriting peer-agent work.
- [x] 6.5 Record FlowGuard adoption evidence in `.flowguard/adoption_log.jsonl` and `docs/flowguard_adoption_log.md`.
- [x] 6.6 Check final status, rerun minimum stale evidence checks, and prepare local git commit/tag evidence when safe.
