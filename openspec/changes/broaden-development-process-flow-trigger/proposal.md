## Why

DevelopmentProcessFlow is currently documented and surfaced mostly as a final
done, archive, publish, or release-readiness freshness check. That framing makes
Codex agents less likely to use the route at the start of ordinary staged
development or modification work, even when the work clearly has ordered steps
and validation evidence that can become stale.

## What Changes

- Broaden the Codex-facing trigger for `flowguard-development-process-flow` so
  non-trivial staged development or modification tasks with validation use the
  route during planning.
- Keep the route a single, direct DevelopmentProcessFlow route rather than
  introducing separate lightweight and heavyweight modes.
- Update the satellite skill metadata, default prompt, protocol guidance, Skill
  Kernel route map, agent snippet, README, and public docs so the route is not
  reserved for release/archive/publish checks.
- Add focused tests that fail if the trigger regresses back to only final
  readiness wording.
- Synchronize the installed global Codex skill copy after the repository source
  copy is updated.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `development-process-flow`: Clarifies that staged development or modification
  work with validation is enough to trigger DevelopmentProcessFlow.
- `model-first-function-flow`: Routes non-trivial staged development and
  modification tasks with validation to `development_process_flow`.

## Impact

- Codex skills: update `.agents/skills/flowguard-development-process-flow` and
  the installed global copy under `C:\Users\liu_y\.codex\skills`.
- Skill Kernel/docs: update route descriptions in
  `.agents/skills/model-first-function-flow`, `docs/modeling_protocol.md`,
  `docs/agents_snippet.md`, `docs/development_process_flow.md`, and README.
- Tests: update skill/docs tests to assert the broader trigger language.
- Local release surfaces: keep package release version, git tag, and GitHub
  Release unchanged until the next publication pass; this change only prepares
  local source and installed skill copies.
