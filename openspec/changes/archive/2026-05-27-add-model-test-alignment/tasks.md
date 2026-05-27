## 1. Specification And Guard Model

- [x] 1.1 Create the OpenSpec proposal, design, spec, and task artifacts.
- [x] 1.2 Extend the Skill Kernel FlowGuard model so the new route is required and mesh coupling is rejected.
- [x] 1.3 Run the Skill Kernel guard model before editing package behavior.

## 2. Core Helper API

- [x] 2.1 Add `flowguard/model_test_alignment.py` with dataclasses, report formatting, decisions, and `review_model_test_alignment()`.
- [x] 2.2 Export the new helper names from `flowguard/__init__.py` as Modeling Helper APIs, not Core APIs.
- [x] 2.3 Add focused unit tests for passing alignment, missing evidence, orphan evidence, duplicate claims, stale/non-passing evidence, and missing required test kinds.

## 3. Templates And CLI

- [x] 3.1 Add a public model-test alignment starter template in `flowguard/templates.py`.
- [x] 3.2 Add `python -m flowguard model-test-alignment-template`.
- [x] 3.3 Extend public template tests for execution, CLI output, risk-purpose headers, and public-marker hygiene.

## 4. Skill And Documentation

- [x] 4.1 Update `.agents/skills/model-first-function-flow/SKILL.md` route map and helper API list.
- [x] 4.2 Add `.agents/skills/model-first-function-flow/references/model_test_alignment_protocol.md`.
- [x] 4.3 Update Skill reference docs, `docs/agents_snippet.md`, `docs/modeling_protocol.md`, `docs/api_surface.md`, `docs/productized_helpers.md`, and README.
- [x] 4.4 Extend skill documentation tests for the new route and independence from TestMesh/StructureMesh.

## 5. Validation, Sync, And Release

- [x] 5.1 Run focused unit tests and OpenSpec strict validation.
- [x] 5.2 Run practical package regression and background any slow checks if needed.
- [x] 5.3 Sync local editable install and verify import/version surfaces.
- [x] 5.4 Update version/changelog/release notes for a new GitHub release.
- [x] 5.5 Commit scoped local changes, push GitHub branch and tag, and create the GitHub release.
