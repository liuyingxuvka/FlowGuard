## 1. Prompt Contract

- [x] Add route-specific diagram intent guidance to `model-first-function-flow`.
- [x] Sync installed FlowGuard kernel skill.

## 2. SkillGuard Contract

- [x] Update FlowGuard source skill contracts with explicit duplicate-path wording.
- [x] Sync installed FlowGuard skill contracts.
- [x] Re-run route checks.

## 3. Version And Release

- [x] Bump package version and changelog.
- [x] Reinstall editable package and verify import path.
- [ ] Commit, tag, push, and publish the release.

## Verification Evidence

- `python -m pytest tests -q`: 935 passed, 333 subtests passed.
- `python -m pytest tests/test_skill_docs.py::SkillDocsTests::test_hot_path_prompt_budgets_are_enforced tests/test_skill_docs.py::SkillDocsTests::test_kernel_preserves_route_specific_diagram_intent -q`: passed.
- Downstream LogicGuard installed FlowGuard diagram semantic test: passed.
- `openspec validate harden-guard-simulation-readiness --strict`: valid.
- Source and installed FlowGuard SkillGuard checks: passed.
