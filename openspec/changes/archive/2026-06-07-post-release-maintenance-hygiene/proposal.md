## Why

After the v0.41.1 release, FlowGuard has a clean public release but still needs
post-release maintenance hygiene so future agents see a lighter project surface:
completed OpenSpec changes should not remain active, CI should guard the
minimum release gates, and self-maintenance review should require fewer manual
fields for the common path.

## What Changes

- Archive completed OpenSpec changes and keep the active change list empty
  after this maintenance pass.
- Add a minimal GitHub Actions workflow that runs the release-critical local
  checks on push and pull request.
- Add a self-maintenance default-plan helper so AI agents can start from
  compact child evidence instead of manually filling route profiles, API group
  ids, AI profiles, and field layers.
- Bump local package/version records to 0.41.2 for the local maintenance
  closure.

## Impact

- OpenSpec active surface and archived change inventory.
- GitHub Actions release-hygiene workflow.
- FlowGuard self-maintenance public helper API and docs/tests.
- Version, local install, shadow workspace, and local git tag.
