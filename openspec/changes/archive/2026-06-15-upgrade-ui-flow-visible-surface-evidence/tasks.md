## 1. Core UI Route Helpers

- [x] 1.1 Add visible-surface dataclasses, report shape, and `review_ui_visible_surface()` in `flowguard/ui_structure.py`.
- [x] 1.2 Add render evidence dataclasses, report shape, supported evidence kinds, and `review_ui_render_evidence()` in `flowguard/ui_structure.py`.
- [x] 1.3 Add geometry/layout evidence dataclasses, report shape, and `review_ui_geometry_layout_evidence()` in `flowguard/ui_structure.py`.
- [x] 1.4 Add responsiveness contract dataclasses, report shape, and `review_ui_responsiveness_contract()` in `flowguard/ui_structure.py`.
- [x] 1.5 Export the new helpers through `flowguard/__init__.py` and the modeling helper API without adding them to `CORE_API`.

## 2. Templates And Skill Prompts

- [x] 2.1 Update the compact UI Flow Structure template with visible-surface and evidence-kind fields while keeping it short.
- [x] 2.2 Update the full UI Flow Structure template notes/examples with visible surface, render evidence, geometry evidence, and responsiveness contracts.
- [x] 2.3 Update `.agents/skills/flowguard-ui-flow-structure/SKILL.md`, its protocol reference, and `agents/openai.yaml`.

## 3. Documentation

- [x] 3.1 Update `docs/ui_flow_structure.md` with the new helper surfaces and route workflow.
- [x] 3.2 Update `docs/api_surface.md`, `docs/agents_snippet.md`, and `README.md` routing summaries.
- [x] 3.3 Keep screenshots documented as a normal evidence type and keep map/canvas specialty rules out of the default route.

## 4. Tests

- [x] 4.1 Add `tests/test_ui_structure.py` coverage for visible surface, render evidence kinds, geometry/layout evidence, and responsiveness contracts.
- [x] 4.2 Update `tests/test_public_templates.py` for compact/full template coverage.
- [x] 4.3 Update `tests/test_skill_docs.py` for visible surface and normal screenshot evidence guidance.
- [x] 4.4 Update `tests/test_api_surface.py` for new public helper placement and `CORE_API` exclusion.

## 5. Validation And Sync

- [x] 5.1 Run focused tests for UI structure, public templates, skill docs, and API surface.
- [x] 5.2 Validate the OpenSpec change strictly.
- [x] 5.3 Run project audit and any focused FlowGuard model/template regressions required by touched artifacts.
- [x] 5.4 Sync installed local package/skill surfaces and any real local git source mirror if present.
- [x] 5.5 Re-run import/version checks from the active workspace and synced locations.

Notes:
- `python -m pytest tests/test_public_templates.py -q` was attempted in full and exceeded the tool timeout; the UI template subset passed, and the remaining public-template node group passed separately.
- `.flowguard/ui_flow_structure_skill/run_checks.py` was attempted and exceeded 180 seconds; it was not counted as passing evidence. Closure evidence is the focused UI/API/docs/template tests, compileall, OpenSpec strict validation, import/version checks, and project audit in both workspaces.
