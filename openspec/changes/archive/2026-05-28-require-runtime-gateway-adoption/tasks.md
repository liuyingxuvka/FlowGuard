## Implementation

- [x] Add public Runtime Gateway Adoption data models and review helper.
- [x] Export the new helper layer through the public API without changing core
  `Workflow`/`Explorer` semantics.
- [x] Add focused unit tests for green adoption, missing inventory, unmanaged
  surfaces, direct bypasses, stale/non-passing observations, gateway mismatch,
  missing evidence ids, and declared legacy bypasses.
- [x] Update public docs, README, and changelog for the new adoption level and
  runtime gateway claim boundary.
- [x] Validate OpenSpec status and focused tests before release.
- [x] Bump package version, sync local editable install, verify import from the
  local workspace and configured shadow workspace when available.
