## ADDED Requirements

### Requirement: DevelopmentProcessFlow governs model-system revision order
DevelopmentProcessFlow SHALL order baseline freeze, isolated candidate
construction, affected-closure derivation, owner validation, activation
decision, compare-and-swap pointer update, installation synchronization, and
release closure. It SHALL defer model, commitment, field, test, and source
semantics to their existing owners.

#### Scenario: Candidate checks pass after the base advances
- **WHEN** the expected observed-head fingerprint no longer matches at activation time
- **THEN** DevelopmentProcessFlow blocks activation and requires a new baseline and affected validation

### Requirement: Promotion writes authority last
The process SHALL persist immutable candidate, decision, and activation
evidence before changing the sole observed-head pointer, and SHALL change that
pointer only once after all hard gates pass.

#### Scenario: Activation receipt cannot be persisted
- **WHEN** candidate validation passes but the activation receipt write fails
- **THEN** the observed-head pointer remains unchanged

### Requirement: Release closes distinct source and installation identities
Release closure SHALL separately verify source commit, package version, project
record, observed snapshot, author skill source, SkillGuard receipt, installed
consumer skills, installed Python distribution, Git tag, and published release.

#### Scenario: Source is current but installed skills are older
- **WHEN** source and model evidence pass but the installed skill projection differs
- **THEN** release readiness remains blocked until installation parity passes
