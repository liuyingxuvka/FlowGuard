## ADDED Requirements

### Requirement: Affected skill changes close through one author unit
When one or more registered FlowGuard skills change, SkillGuard SHALL supervise the frozen affected owner plan, author projections, consumer projection, installation projection, and exact current checks as one maintenance unit.

#### Scenario: One satellite prompt changes
- **WHEN** a registered satellite `SKILL.md` or its declared reference changes
- **THEN** only the affected semantic owners and their declared downstream projections SHALL become stale during development
- **AND** the final release SHALL validate the complete author unit once after all source changes are frozen

#### Scenario: Consumer installation is synchronized
- **WHEN** the final author source is current
- **THEN** shadow, consumer, and editable package projections SHALL be synchronized from the frozen source
- **AND** consumer projections SHALL contain no author receipts, router state, or private maintenance authority

### Requirement: Patch release identity closes source, model, installation, and GitHub separately
A patch release SHALL publish only when source version, model authority, installed projection, final validation receipt, Git commit, immutable tag, and GitHub Release target are separately current and mutually consistent.

#### Scenario: Version changes after an older receipt
- **WHEN** the package version changes from 0.68.7 to 0.68.8
- **THEN** version-bound release owners SHALL not reuse 0.68.7 release evidence as 0.68.8 evidence
- **AND** the final plan SHALL select the minimum stale owner set for one final release parent

#### Scenario: Published release is verified
- **WHEN** a v0.68.8 tag and GitHub Release are created
- **THEN** the published receipt SHALL compare commit, branch, tag, release target, draft/prerelease state, asset policy, and final parent receipt
- **AND** it SHALL not rerun product tests merely to check publication identity
