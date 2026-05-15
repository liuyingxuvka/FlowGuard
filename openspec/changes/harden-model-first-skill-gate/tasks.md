## 1. Model and Contract

- [x] 1.1 Add a local FlowGuard rollout model for the pre-implementation model-hardening gate.
- [x] 1.2 Prove the model catches known-bad variants for code-first changes, happy-path-only checks, hard-coded heavy-model skips, and peer-change overwrite risk.

## 2. Skill and Snippet

- [x] 2.1 Update `model-first-function-flow` Skill guidance with the model-hardening gate, coverage matrix, known-bad hazard rule, tiered heavy-check policy, and incremental validation loop.
- [x] 2.2 Update `docs/agents_snippet.md` with the same operational contract for downstream repositories.

## 3. Tests and Validation

- [x] 3.1 Add focused tests that pin the Skill and AGENTS snippet requirements.
- [x] 3.2 Run focused validation for the rollout model, skill validation, and tests.
- [x] 3.3 Run the strongest practical full repository validation, using background artifacts for long checks.

## 4. Release Sync

- [x] 4.1 Bump the package patch version and update the changelog.
- [x] 4.2 Sync the installed local Skill and the `FlowGuard_20260427` shadow workspace from the release source.
- [x] 4.3 Verify installed package metadata, installed Skill content, shadow workspace imports, and git repository status.
- [ ] 4.4 Commit, tag, push to GitHub, create the GitHub Release, and verify version/tag/release alignment.
