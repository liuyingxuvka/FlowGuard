## 1. Specification And Model

- [x] 1.1 Validate the OpenSpec change with strict validation.
- [x] 1.2 Add an executable FlowGuard self-model for mandatory template harvest closure.
- [x] 1.3 Run the self-model and preserve pass/fail evidence.

## 2. Core Harvest Closure API

- [x] 2.1 Add `TemplateHarvestReview`, accepted dispositions/reasons, and `review_template_harvest_closure()`.
- [x] 2.2 Extend `FlowGuardCheckPlan`, audit, and runner output with harvest closure review.
- [x] 2.3 Add CLI support for harvest closure review and route-scoped public API exports.

## 3. Templates, Prompts, And Docs

- [x] 3.1 Update model-first kernel, AGENTS snippet, modeling protocol, and product docs from soft harvest wording to mandatory closure wording.
- [x] 3.2 Update direct satellite skills that can create or deepen models so they cannot bypass harvest closure.
- [x] 3.3 Update public starter templates to demonstrate harvest closure.

## 4. Tests And Validation

- [x] 4.1 Add unit tests for harvest closure review success and failure cases.
- [x] 4.2 Add plan/runner/audit/API/CLI/template/skill-doc regression coverage.
- [x] 4.3 Run OpenSpec strict validation, FlowGuard self-model, focused pytest, broad pytest, and project audit.

## 5. Sync And Closure

- [x] 5.1 Bump version/changelog and refresh editable local install.
- [x] 5.2 Sync installed Codex skills and shadow workspace without reverting peer-agent changes.
- [x] 5.3 Record FlowGuard adoption evidence and KB postflight observation.
- [x] 5.4 Commit and tag the local git version while excluding unrelated peer-agent changes.
