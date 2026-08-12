## Why

The published FlowGuard 0.68.13 source package reports one version while its
package-owned consumer-suite authority still reports 0.68.12. That mismatch
blocks currentness checks and can make downstream projects consume an authority
that does not describe the installed package. A corrective patch is needed
before LogicWriting can safely refresh its FlowGuard project records.

## What Changes

- Regenerate the package-owned consumer-suite authority from the 0.68.14
  source package identity without changing the fifteen-member projection.
- Add a release-identity check that requires the authority version to equal the
  package version and remain readable from a non-editable installation.
- Update the FlowGuard patch release documentation and release surface to
  0.68.14, then synchronize the local consumer installation.
- Validate source, package, installed consumer projection, Git tag, and GitHub
  Release as separate identities.

## Capabilities

### New Capabilities

- `release-authority-identity`: Ties the packaged consumer authority to the
  exact package release identity while preserving its clean projection.

### Modified Capabilities

<!-- No existing behavior requirement is replaced; the new capability adds a
     release identity contract around the existing distribution authority. -->

## Impact

The FlowGuard package metadata, generated `consumer-suite-authority.json`,
release documentation, focused distribution tests, local installed consumer
projection, and GitHub patch release are affected. No skill member, route,
runtime API, compatibility reader, updater, or fallback path is added.
