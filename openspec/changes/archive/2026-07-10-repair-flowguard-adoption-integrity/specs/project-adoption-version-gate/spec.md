## ADDED Requirements

### Requirement: Managed Adoption Semantic Parity
Project audit SHALL compare the current managed `AGENTS.md` block with the block produced by the installed generator using stable rule identifiers and normalized content. It SHALL also compare package version, project-manifest version, and rendered adoption version. Markers alone MUST NOT satisfy adoption health.

#### Scenario: Managed block has stale version
- **WHEN** package and manifest report 0.53.1 but the managed block records 0.53.0
- **THEN** project audit fails with a rendered-version-mismatch finding

#### Scenario: Current governance rule is missing
- **WHEN** the rendered block omits a required BCL, PPA, path-sensitive, latest-schema-first, or default-replacement rule
- **THEN** project audit fails with the missing stable rule identifiers

### Requirement: Non-Mutating Upgrade Preview
Project upgrade SHALL provide a dry-run mode that computes proposed manifest changes, managed-block semantic differences, suite findings, affected artifacts, and minimum revalidation without modifying any repository file or adoption log.

#### Scenario: Dry-run previews stale adoption repair
- **WHEN** project upgrade runs with `--dry-run --json` against a stale managed block
- **THEN** it reports the proposed semantic changes and the repository tree remains byte-identical

### Requirement: Upgrade Must Not Weaken Governance
A writing project upgrade MUST refuse to proceed when the proposed generated block loses a rule present in the current required rule set, when the installed engine is older than the project record, or when suite inventory validation is unresolved.

#### Scenario: Generator would delete PPA rules
- **WHEN** the proposed generated block lacks the current Primary Path Authority rule
- **THEN** the upgrade exits nonzero before writing and reports a governance-regression blocker

#### Scenario: Installed engine is older
- **WHEN** the installed engine version is lower than the project manifest version
- **THEN** the upgrade exits nonzero without changing the project

### Requirement: Adoption Decision Evidence
Project audit and upgrade results SHALL include canonical status, versions, inventory hash, managed-block semantic hash, findings, skipped steps, required revalidation, and claim boundary. A log entry MAY be written only for a real audit or writing upgrade, and logging MUST NOT convert a failed check into pass.

#### Scenario: Successful writing upgrade completes
- **WHEN** an approved writing upgrade finishes and post-write audit passes
- **THEN** adoption logs record the before/after hashes, versions, checks, and remaining claim boundary
