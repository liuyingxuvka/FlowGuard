## 0. Current supersession and retirement preparation

- [x] 0.1 Classify the `0.68.14` package, installation, tag, and publication
  plan as superseded history; it must not be executed against the current
  repository.
- [x] 0.2 Transfer the exact version-neutral `Packaged authority carries the
  package release identity` contract and all three scenarios into the current
  `harden-currentness-validation-execution` distribution delta.
- [x] 0.3 Verify both changes strictly and verify this change's read-only
  semantic projection with `--skip-specs`; do not treat ordinary apply-specs
  projection as the retirement contract.
- [ ] 0.4 Archive this historical change once, using the OpenSpec provider's
  official `--skip-specs` operation, then compare the frozen pre-projection
  with the actual archived delta and unchanged current specs.

## Historical `0.68.14` plan (cancelled; do not execute)

The unchecked items below are retained as incident history, not as pending
current work. They must never be checked from a later version's evidence.

## 1. OpenSpec and source identity

- [ ] 1.1 Confirm the repository is clean, record active peer-owned changes,
  and validate this change's proposal, design, and spec artifacts.
- [ ] 1.2 Update the package version and every current release-facing version
  projection from 0.68.13 to 0.68.14 while preserving historical entries.
- [ ] 1.3 Regenerate `flowguard/consumer-suite-authority.json` with the official
  compiler and confirm the member/file projection did not change.

## 2. Contract and validation

- [ ] 2.1 Add or update focused tests for package-version/authority-version
  equality and the stale-authority negative case.
- [ ] 2.2 Run the focused distribution, installation, and package identity tests
  plus strict OpenSpec validation; fix failures at their source.
- [ ] 2.3 Run FlowGuard project/model/currentness checks and record separate
  source, package, and consumer-projection identities.

## 3. Installation and release

- [ ] 3.1 Prepare, activate, and read back the official local consumer
  installation; verify exact authority parity without launching a second
  semantic validation owner.
- [ ] 3.2 Freeze the final source/toolchain/release inputs, commit only owned
  paths, and confirm no peer work was overwritten.
- [ ] 3.3 Push main, create and push annotated tag `v0.68.14`, and publish a
  source-only GitHub Release.
- [ ] 3.4 Read back the remote commit/tag/release and compare them with local
  Git, package version, authority version, and installed projection.
- [ ] 3.5 Mark this change complete only after all release identities agree.
