## ADDED Requirements

### Requirement: OpenSpec history has an explicit current disposition
The semantic-sync checker SHALL enumerate every audited historical ADDED and
MODIFIED requirement and SHALL assign each row exactly one disposition of
`current`, `replaced`, `retired`, or `pending`. A pending, duplicated, or
unmapped row MUST block archive and broad project closure.

#### Scenario: Historical requirement has no disposition
- **WHEN** an audited historical requirement is absent from the current specs
  and has no replacement or retirement evidence
- **THEN** semantic sync reports the row as `pending` and blocks archive

#### Scenario: Retired requirement is intentionally absent
- **WHEN** a historical requirement has an explicit retirement reason and no
  current runtime, public route, alias, or fallback authority
- **THEN** semantic sync accepts the `retired` disposition without restoring it

### Requirement: Delta operations are validated before archive
Before an OpenSpec change is archived, the semantic-sync checker SHALL resolve
every delta operation against the current specification set. ADDED titles MUST
be absent, MODIFIED and REMOVED titles MUST exist exactly once, and a rename
MUST explicitly bind its old and new titles before a modification of the new
title is accepted.

#### Scenario: Modified title has no current source
- **WHEN** a delta declares MODIFIED for a requirement title that is absent
  from the current capability
- **THEN** pre-archive semantic sync blocks without invoking archive

#### Scenario: Modified title is ambiguous
- **WHEN** a delta title resolves to more than one current requirement
- **THEN** pre-archive semantic sync blocks and names every conflicting source

#### Scenario: Rename and modification are explicit
- **WHEN** a requirement is renamed and its behavior changes
- **THEN** the change contains a RENAMED old-to-new row and a complete MODIFIED
  block under the new title

### Requirement: Post-archive current specs equal the projected result
The semantic-sync checker SHALL compute an in-memory canonical projection of
the expected current specifications before archive and SHALL compare the
actual current specification set with that projection after the official
OpenSpec archive operation. Any content, title, capability, requirement, or
scenario mismatch MUST block DevelopmentProcessFlow closure.

#### Scenario: Archive drops a scenario
- **WHEN** official archive completes but the actual current spec omits a
  scenario present in the pre-archive projection
- **THEN** post-archive semantic sync fails and broad completion remains blocked

#### Scenario: Archive matches the projection
- **WHEN** every actual current capability and normalized requirement block
  equals the frozen pre-archive projection
- **THEN** semantic sync emits a passing read-only comparison report

### Requirement: Semantic sync does not own OpenSpec lifecycle
The FlowGuard semantic-sync checker SHALL remain read-only with respect to
OpenSpec provider artifacts and SHALL NOT archive, edit, migrate, execute, or
replace OpenSpec lifecycle operations.

#### Scenario: Checker is asked to repair an archive
- **WHEN** semantic sync detects a provider mismatch
- **THEN** it reports the mismatch and required provider action without writing
  specs, invoking archive, or creating provider receipts

### Requirement: Current authority regression scan is exact
The current-spec authority scan SHALL bind the package-owned consumer suite
identity and SHALL reject superseded fixed member counts, retired public skill
ids, historical fixed release versions, compatibility success paths, or
synthetic payload-proof completion in current requirements.

#### Scenario: Superseded suite count remains
- **WHEN** a current requirement still treats seventeen skills or sixteen
  satellites as the current consumer suite
- **THEN** current-spec authority validation fails and names that requirement

#### Scenario: Current specs follow package authority
- **WHEN** current requirements derive membership and version identity from the
  package-owned authority and contain no retired success path
- **THEN** the current-spec authority scan passes for that boundary
