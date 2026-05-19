## 1. OpenSpec And FlowGuard Model

- [x] 1.1 Validate the `add-user-facing-model-diagrams` OpenSpec change.
- [x] 1.2 Add a lightweight local FlowGuard model for optional-but-expressive
  user-facing diagram guidance.
- [x] 1.3 Run the model and confirm known-bad prompt variants fail.

## 2. Skill Prompt Updates

- [x] 2.1 Add shared diagram guidance to `model-first-function-flow`.
- [x] 2.2 Add UI-specific diagram guidance to `flowguard-ui-flow-structure`.
- [x] 2.3 Add parent/child boundary diagram guidance to `flowguard-model-mesh`.
- [x] 2.4 Add staged lifecycle diagram guidance to
  `flowguard-development-process-flow`.

## 3. Documentation And Versioning

- [x] 3.1 Update public docs to mention optional user-facing Mermaid diagrams.
- [x] 3.2 Update README and CHANGELOG with the lightweight diagram guidance.
- [x] 3.3 Bump package version for a patch release.

## 4. Sync And Validation

- [x] 4.1 Sync repository-managed skills into the installed Codex skill
  directory.
- [x] 4.2 Sync the real Git checkout back to the shadow workspace.
- [x] 4.3 Run skill validation, OpenSpec validation, FlowGuard checks, focused
  tests, regression tests, editable install checks, shadow checks, and privacy
  scans.
- [x] 4.4 Commit, tag, push, and create a new source-only GitHub Release.
