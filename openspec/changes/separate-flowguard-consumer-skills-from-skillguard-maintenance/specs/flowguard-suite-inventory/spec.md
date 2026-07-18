## MODIFIED Requirements

### Requirement: Canonical Skill Suite Inventory
The system SHALL maintain one versioned canonical member authority that identifies the FlowGuard kernel and every public satellite skill, including stable skill id, route role, and target-owned consumer entry files. Inventory skill ids MUST be unique and the current authority MUST contain exactly one kernel and sixteen satellites. Maintainer-source and consumer-distribution validators SHALL derive separate path policies from this member authority.

#### Scenario: Current suite is fully declared
- **WHEN** either current inventory projection is loaded from the repository
- **THEN** it identifies seventeen unique members with exactly one kernel and sixteen satellites and states which projection it validates

#### Scenario: Duplicate member is declared
- **WHEN** two canonical member records use the same skill id
- **THEN** both projections fail with a duplicate-member diagnostic and no suite-complete claim

### Requirement: Missing Controls Are Visible Failures
Suite discovery MUST begin from `SKILL.md` membership. The maintainer-source projection SHALL report missing expected author controls, while the consumer-distribution projection SHALL reject every author control and report only missing target-owned consumer files. Neither projection may silently omit the member.

#### Scenario: Maintainer control root is absent
- **WHEN** the maintainer-source inventory finds a declared skill with `SKILL.md` but no required author control root
- **THEN** its report includes that skill and returns a missing-maintainer-control failure

#### Scenario: Consumer control root is present
- **WHEN** the consumer-distribution inventory finds `.skillguard` beneath a declared member
- **THEN** its report includes that skill and returns a prohibited-author-control failure

#### Scenario: Consumer reference is absent
- **WHEN** a declared consumer skill is missing a referenced target-owned file
- **THEN** the member remains visible and consumer readiness fails with the exact missing path
