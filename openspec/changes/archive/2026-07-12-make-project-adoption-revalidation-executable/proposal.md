## Why

Project adoption reports currently recommend a source-repository helper command that does not exist in ordinary adopted projects. This makes a passing `project-audit` handoff contain an impossible required revalidation step and can force agents either to skip the stated gate or to invent a project-local fallback.

## What Changes

- Remove the redundant source-layout-only `scripts/verify_skill_suite_markers.py` command from generated project-adoption revalidation guidance.
- Keep the installed-package-owned `python -m flowguard project-audit --root . --json` command as the single portable project and skill-suite audit entrypoint.
- Require every generated executable revalidation command to run successfully from a valid adopted target that has no FlowGuard source-repository `scripts/` directory.
- Add a regression for the observed target-project failure and the same-class family of generated source-layout-only commands.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-adoption-version-gate`: Generated required revalidation commands must be package-owned and executable from the adopted target project, not merely relative or privacy-safe strings.

## Impact

- Affects `flowguard/project_adoption.py`, its focused project-adoption tests, and the existing project-adoption FlowGuard model/spec evidence.
- Does not remove the repository-internal marker script or add a new CLI route.
- Existing adoption reports and logs are historical evidence; new audit/adopt/upgrade reports emit the corrected single portable command.
