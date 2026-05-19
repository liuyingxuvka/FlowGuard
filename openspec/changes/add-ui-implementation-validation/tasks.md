## 1. OpenSpec And FlowGuard Model

- [x] 1.1 Create the `add-ui-implementation-validation` proposal, design, specs, and task list.
- [x] 1.2 Extend the local UI Flow Structure FlowGuard model with feature/UI/implementation validation evidence and known-bad hazards.
- [x] 1.3 Validate the OpenSpec change and local FlowGuard model before trusting production edits.

## 2. Package Helper API

- [x] 2.1 Add UI feature contract, implementation journey run, step evidence, blindspot, validation, and report dataclasses to `flowguard/ui_structure.py`.
- [x] 2.2 Add `review_ui_implementation_validation(...)` that aligns feature contracts, UI journey coverage, and browser/manual evidence.
- [x] 2.3 Export the new helpers from `flowguard/__init__.py` and API surface groups.
- [x] 2.4 Add focused tests for passing validation and broken feature, UI ownership, missing run, missing branch evidence, stale evidence, and blindspot hazards.

## 3. Templates And CLI

- [x] 3.1 Update the UI flow structure template with feature contracts and implementation click-through evidence after journey coverage.
- [x] 3.2 Extend public template tests so generated UI implementation validation checks execute.

## 4. Codex Skill And Documentation

- [x] 4.1 Update `flowguard-ui-flow-structure` skill and protocol with the implemented/runnable UI validation gate.
- [x] 4.2 Update `model-first-function-flow`, `docs/agents_snippet.md`, API docs, and UI Flow Structure docs.
- [x] 4.3 Update README, CHANGELOG, release checklist, and version references for the new capability.

## 5. Sync And Validation

- [x] 5.1 Sync repository-managed skills into the installed Codex skill directory.
- [x] 5.2 Sync the real Git checkout back to the shadow workspace after validation.
- [x] 5.3 Run skill validation, OpenSpec validation, FlowGuard model checks, focused tests, public template tests, full regression, privacy scans, editable install checks, and shadow import checks.
- [x] 5.4 Leave GitHub push, tag, and release publication pending because the user asked to hold publication.
