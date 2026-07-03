## 1. Public Skill-Suite Onboarding

- [x] 1.1 Update README English hero, What FlowGuard Is, Quick Start, another-project integration, and CLI sections so skill-suite loading is first and executable checks are check scripts/compatibility commands.
- [x] 1.2 Update README Chinese mirror with the same skill-suite-first and check-script wording.
- [x] 1.3 Update AGENTS.md and docs/agents_snippet.md so the primary agent surface is `.agents/skills/`, with `model-first-function-flow` as the default entrypoint.

## 2. Kernel And Integration Guidance

- [x] 2.1 Update `.agents/skills/model-first-function-flow/SKILL.md` to identify the FlowGuard skill suite entrypoint, sibling skills, and the difference between skill availability and executable check evidence.
- [x] 2.2 Update `docs/project_integration.md` and `.agents/skills/model-first-function-flow/references/project_integration.md` so project setup separates skill-suite availability from check execution and project-record commands.
- [x] 2.3 Keep executable check commands available but label `python -m flowguard` and editable install paths as compatibility/check execution details, not the skill installation.
- [x] 2.4 Update `flowguard/project_adoption.py` so generated AGENTS blocks use skill-suite and check-engine wording.

## 3. Tests And Static Verification

- [x] 3.1 Add `scripts/verify_skill_suite_markers.py` to verify README, AGENTS, integration docs, repository skills, and optionally installed skill markers.
- [x] 3.2 Update `tests/test_project_integration.py` to assert skill-suite-first setup and stop requiring `pip install -e` as the integration proof.
- [x] 3.3 Update `tests/test_skill_docs.py` to assert the kernel and reusable snippet expose the skill-suite entry and avoid stale package-first wording.
- [x] 3.4 Update `tests/test_project_adoption.py` to pin the generated AGENTS template wording.

## 4. Validation

- [x] 4.1 Run `openspec validate reframe-flowguard-as-skill-suite --strict` and fix artifacts if needed.
- [x] 4.2 Run focused docs/skill tests from the verification contract.
- [x] 4.3 Run the job-matching check-script smoke test.
- [x] 4.4 Run the static skill-suite marker verifier against the repository.
- [x] 4.5 Run the project adoption template tests from the verification contract.

## 5. Local Sync And Git Source Sync

- [x] 5.1 Refresh affected FlowGuard installed Codex skill directories under the active user's Codex skills root without deleting unrelated skills.
- [x] 5.2 Run the installed-skill marker verifier.
- [x] 5.3 Sync this change to the formal Git checkout without reverting unrelated peer work.
- [x] 5.4 Verify formal Git checkout status and focused checks after sync.
