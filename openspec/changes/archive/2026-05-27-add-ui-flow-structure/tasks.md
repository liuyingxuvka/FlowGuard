## 1. OpenSpec And FlowGuard Model

- [x] 1.1 Create the `add-ui-flow-structure` proposal, design, specs, and task list.
- [x] 1.2 Add a FlowGuard adoption model for the UI flow structure skill route and known-bad hazards.
- [x] 1.3 Validate the OpenSpec change and local FlowGuard model before production edits are trusted.

## 2. Package Helper API

- [x] 2.1 Add `flowguard/ui_structure.py` with UI interaction model dataclasses, structure derivation dataclasses, reports, and reviewers.
- [x] 2.2 Export UI flow structure helpers from `flowguard/__init__.py` and API surface group constants.
- [x] 2.3 Add `tests/test_ui_structure.py` for successful and broken UI interaction/structure cases.
- [x] 2.4 Add semantic information display and same-level control redundancy checks with explicit-rationale escape hatches.

## 3. Templates And CLI

- [x] 3.1 Add UI flow structure template files in `flowguard/templates.py`.
- [x] 3.2 Add `python -m flowguard ui-flow-structure-template` in `flowguard/__main__.py`.
- [x] 3.3 Extend public template tests for execution, CLI print/write behavior, headers, and privacy markers.

## 4. Codex Skill And Kernel Routing

- [x] 4.1 Add `.agents/skills/flowguard-ui-flow-structure/` with `SKILL.md`, route reference, and `agents/openai.yaml`.
- [x] 4.2 Update `model-first-function-flow` kernel route map and references for `ui_flow_structure`.
- [x] 4.3 Update `docs/agents_snippet.md` and skill documentation tests for the expanded satellite topology.

## 5. Public Documentation And README

- [x] 5.1 Add `docs/ui_flow_structure.md` and update API/product/modeling docs.
- [x] 5.2 Rewrite README to foreground current capabilities, satellite skills, helper APIs, templates, and public boundaries while preserving accurate legacy content.
- [x] 5.3 Update CHANGELOG, release checklist, and version references.

## 6. Release Sync And Validation

- [x] 6.1 Sync repository-managed skills into the installed Codex skill directory.
- [x] 6.2 Sync the real Git checkout back to the shadow workspace after validation.
- [x] 6.3 Run skill validation, OpenSpec validation, FlowGuard model checks, focused tests, full regression, and privacy scans.
- [x] 6.4 Commit, push, tag, create the GitHub Release, and verify release/version/readme alignment.
