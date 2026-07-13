## Why

Project-adoption reports and human adoption logs currently embed the target repository's absolute machine path in generated minimum-revalidation commands. Public repositories can therefore disclose private workstation paths even though the commands only need to run from the project root.

## What Changes

- Generate minimum-revalidation commands with the portable project-relative argument `--root .`.
- Keep the report and human adoption log on the same single command source so their portability cannot drift.
- Add regression coverage for both report evidence and the written Markdown log using a temporary absolute target path.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-adoption-version-gate`: Require generated revalidation commands and public human adoption evidence to avoid target-machine absolute roots.

## Impact

Affected surfaces are `flowguard/project_adoption.py`, focused project-adoption tests, and the existing project-adoption specification. Command behavior remains the same when run from the target project root; no API, dependency, or schema migration is introduced.
