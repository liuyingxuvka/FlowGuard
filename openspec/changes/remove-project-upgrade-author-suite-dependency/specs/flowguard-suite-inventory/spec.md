## ADDED Requirements

### Requirement: Packaged consumer-suite authority has exact parity
Each FlowGuard package release SHALL contain one deterministic target-owned
consumer-suite authority declaring the current 15 member ids and exact clean
consumer file fingerprints. Maintainer validation, installation, and
installed-currentness checks SHALL require this authority to match both the
generated author-source projection and the global consumer projection by raw
content.

#### Scenario: Authority is compiled from current author source
- **WHEN** the maintainer compiles the consumer-suite authority
- **THEN** it derives exactly one kernel and fourteen satellites from the
  current author inventory
- **AND** it records the generated clean consumer files without author paths,
  `.skillguard`, contracts, receipts, or router state

#### Scenario: Package is installed non-editably
- **WHEN** FlowGuard is installed as a normal package without its repository
  checkout
- **THEN** the consumer-suite authority remains readable from package data
- **AND** no author suite map is required at runtime

#### Scenario: Source changes without authority regeneration
- **WHEN** a maintained consumer skill file changes and the packaged authority
  is not regenerated
- **THEN** author-side installation and currentness validation fail before
  activation or release

#### Scenario: Installed projection is exact
- **WHEN** every global consumer member and file matches the packaged authority
  and the installer ownership manifest names the same identity
- **THEN** installed consumer validation passes with one deterministic
  inventory hash
