## Why

FlowGuard v0.64.0 passed local model-authority and release validation, but the
same commit failed project audit in GitHub Actions because 49 inputs referenced
by the current observed snapshot existed only in the ignored local
`.flowguard/` tree. A release must prove that its authoritative model can be
reconstructed from the committed tree, not only from the maintainer's working
copy.

## What Changes

- Require every file in the current observed model-system input inventory to be
  reachable from the exact Git release tree.
- Block local release verification when an authority input is ignored,
  untracked, absent from the commit, or has different committed content.
- Add observed and same-class regression coverage for missing model and runner
  inputs.
- Commit the 49 currently missing model-authority inputs and verify project
  audit from a clean clone.
- Publish the correction as an immutable patch release without moving the
  existing `v0.64.0` tag.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `authoritative-model-system`: Current observed authority must be
  reconstructable from the committed source tree used by a release.
- `project-adoption-version-gate`: Release-critical validation must fail before
  publication when current model-authority inputs are not Git-reachable.

## Impact

The change affects release verification, model-authority audit helpers,
focused unit tests, the current `.flowguard/` model inventory, CI clean-clone
evidence, version records, and patch-release metadata. It does not add a
fallback authority, compatibility reader, or automatic test rerun.
