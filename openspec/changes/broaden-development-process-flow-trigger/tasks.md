## 1. Skill Trigger Updates

- [x] 1.1 Update the repository `flowguard-development-process-flow` satellite
  skill description and body so staged development/modification with validation
  triggers the route.
- [x] 1.2 Update the satellite `agents/openai.yaml` short description and
  default prompt.
- [x] 1.3 Update the Skill Kernel route map and modeling protocol trigger for
  `development_process_flow`.
- [x] 1.4 Update the AGENTS snippet, README, and public DevelopmentProcessFlow
  docs to reflect the broader trigger.

## 2. FlowGuard Evidence

- [x] 2.1 Run a DevelopmentProcessFlow review for this change's lifecycle
  artifacts, expected validations, install sync, local git state, and local-only
  no-publish boundary.
- [x] 2.2 Run the existing `.flowguard/development_process_flow` model checks.

## 3. Validation

- [x] 3.1 Add or update focused skill/docs tests for the staged-development
  trigger.
- [x] 3.2 Validate the OpenSpec change.
- [x] 3.3 Run focused unit tests for skill docs and DevelopmentProcessFlow.
- [x] 3.4 Run the full repository unit-test suite.

## 4. Sync And Release

- [x] 4.1 Sync the updated repository skill files into the global Codex skill
  install directory and verify matching hashes.
- [x] 4.2 Sync the git repository updates back to
  `<shadow-workspace>`.
- [x] 4.3 Keep package release version, README release table, git tag, and
  GitHub Release unchanged for this local-only pass.
- [x] 4.4 Commit or leave staged local git changes for review, but do not push,
  tag, or create a GitHub Release.
