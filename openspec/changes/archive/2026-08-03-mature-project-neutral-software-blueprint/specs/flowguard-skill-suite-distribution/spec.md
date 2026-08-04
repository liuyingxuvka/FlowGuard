## ADDED Requirements

### Requirement: Blueprint-related skill changes remain target-owned and cleanly projected
Changes to affected FlowGuard skill prompts and protocols SHALL remain inside the existing FlowGuard maintenance unit and SHALL be validated by each target skill's native checks under SkillGuard author-side supervision. Consumer installation SHALL contain only the clean target skill projection and SHALL NOT include SkillGuard receipts, author registries, execution-owner metadata, or a new `DNA` skill.

#### Scenario: A blueprint prompt changes in one maintained skill
- **WHEN** the frozen impact plan maps the changed component to one or more affected skill owners
- **THEN** only those exact native owners and consuming projections require affected revalidation before the final full gate
- **AND** an unmapped prompt change blocks instead of falling back to an indiscriminate run-all

#### Scenario: Consumer projection is installed
- **WHEN** all affected target-owned checks and the singular frozen maintenance-unit gate pass
- **THEN** installation projects the current consumer files transactionally
- **AND** no SkillGuard author evidence or alternate runtime route is copied into the consumer tree

#### Scenario: A new DNA skill appears in the projection
- **WHEN** source or installed inventory contains a standalone DNA skill or duplicate blueprint route
- **THEN** distribution validation reports an unexpected consumer member and ownership conflict
- **AND** installation or release closure is blocked

### Requirement: Source installation Git and release identities close independently
Distribution SHALL preserve separate current evidence for the authoritative source skill inventory, package source, editable installation, installed consumer skill inventory, local repository commit, remote branch, tag, and GitHub Release. Synchronization or success in one identity domain SHALL NOT imply success in another.

#### Scenario: Source checks pass before installed projection sync
- **WHEN** target-owned source checks pass but an affected installed consumer file has a different fingerprint
- **THEN** source validation remains reported separately and installation parity remains incomplete
- **AND** Git or release publication is not reported ready

#### Scenario: Final source changes after the frozen full gate
- **WHEN** any maintained source or toolchain component changes after the singular final validation receipt
- **THEN** the affected source and projection evidence becomes stale
- **AND** the old receipt cannot authorize installation, tag, or release

#### Scenario: Patch release closes every identity
- **WHEN** the authorized patch release has current target-owned checks, SkillGuard unit closure, clean install parity, exact package version, committed source, pushed commit, matching tag, and matching GitHub Release
- **THEN** distribution MAY report release closure for those exact identities
- **AND** empirical reconstruction remains independently `not_run` unless separately requested and evidenced
