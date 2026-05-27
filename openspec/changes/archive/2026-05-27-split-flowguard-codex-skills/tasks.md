## 1. Skill Topology

- [x] 1.1 Create seven repository-managed standalone FlowGuard satellite skill directories.
- [x] 1.2 Give each satellite skill concise trigger, hard-gate, workflow, non-goal, and validation guidance.
- [x] 1.3 Copy or link only the route-specific reference material needed for standalone use.
- [x] 1.4 Update the kernel skill to route to standalone satellites while preserving kernel ownership.

## 2. Global Prompt And Documentation

- [x] 2.1 Update the reusable AGENTS/global prompt snippet for the 1 + 7 skill topology.
- [x] 2.2 Update README, API/product docs, and changelog to describe the new Codex skill architecture.
- [x] 2.3 Keep helper APIs and CLI templates documented as helpers, not skills.

## 3. Validation Coverage

- [x] 3.1 Add or update tests that verify all eight Codex skills exist and contain required trigger language.
- [x] 3.2 Add or update tests that verify the global prompt mentions the satellite topology and support protocols.
- [x] 3.3 Validate all repository-managed skills with the skill creator validator.

## 4. Release Sync

- [x] 4.1 Bump the package version and changelog for the release.
- [x] 4.2 Sync repository skill directories into the installed Codex skills directory.
- [x] 4.3 Sync the real git checkout back to the shadow workspace and verify imports from both paths.
- [x] 4.4 Run FlowGuard model checks, OpenSpec validation, targeted tests, and full regression.
- [x] 4.5 Run release boundary checks, commit, push, tag, and create a GitHub Release.
