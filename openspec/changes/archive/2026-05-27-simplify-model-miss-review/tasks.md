## 1. Model and Contract

- [x] 1.1 Add a lightweight FlowGuard rollout model for the revised post-runtime model-miss review.
- [x] 1.2 Prove the rollout model catches point-fix-only repair, over-detailed category expansion, and heavyweight default process variants.

## 2. Skill and Documentation

- [x] 2.1 Update `model-first-function-flow` Skill guidance to use the five miss types and one same-class generalized bad case.
- [x] 2.2 Update `docs/agents_snippet.md` and `docs/modeling_protocol.md` with the same lightweight model-miss behavior.
- [x] 2.3 Keep adoption-note guidance compact with `Miss type` and `Generalized case`, without adding a default evidence-level field.

## 3. Tests and Validation

- [x] 3.1 Add focused tests that pin the simplified categories, generalized-case rule, and omitted heavyweight defaults.
- [x] 3.2 Run OpenSpec validation, the rollout model, focused docs tests, and relevant FlowGuard review checks.
- [x] 3.3 Run full repository validation in background artifacts and inspect completion evidence.

## 4. Release Sync

- [x] 4.1 Bump the patch version and update the changelog.
- [x] 4.2 Sync the installed local Skill and local shadow workspace from the release source.
- [x] 4.3 Verify installed package metadata, installed Skill content, shadow workspace imports, git status, and version alignment.
- [x] 4.4 Commit, tag, push to GitHub, create the GitHub Release, and verify version/tag/release alignment.
