## ADDED Requirements

### Requirement: Official OpenSpec is read-only context
FlowGuard SHALL read only official OpenSpec proposal, design, specification,
task, and derived-status material inside one declared project root. OpenSpec
retains sole authority over its authoring artifacts, validation, lifecycle,
and archive operations.

#### Scenario: Current OpenSpec change is read
- **WHEN** a caller supplies a safe change id under the declared project's
  `openspec/changes` directory
- **THEN** FlowGuard SHALL return one current read-only context containing the
  exact artifact paths and content identities without modifying the project

#### Scenario: Another provider is requested
- **WHEN** a caller requests Spec Kit or any provider other than official
  OpenSpec
- **THEN** FlowGuard SHALL reject the request and SHALL NOT fall back to a
  provider-neutral reader

### Requirement: OpenSpec context carries no execution authority
The OpenSpec context SHALL contain no command, check owner, dependency owner,
session, cache, receipt, reuse, consumer fan-out, obligation reconciliation,
completion projection, or archive-readiness authority.

#### Scenario: FlowGuard validation is needed
- **WHEN** OpenSpec material informs a FlowGuard model or test obligation
- **THEN** the FlowGuard validation SHALL have its own native owner and
  evidence and SHALL NOT reuse or project an OpenSpec status as execution proof

#### Scenario: OpenSpec task status changes
- **WHEN** the proposal, design, specification, or task material changes
- **THEN** the context identity SHALL change without opening, resuming, or
  closing a provider session

### Requirement: Context discovery is project bounded
OpenSpec context discovery SHALL remain beneath the explicit project root and
SHALL accept only safe single-directory change ids.

#### Scenario: Unsafe change id is supplied
- **WHEN** a change id is empty, nested, or attempts path traversal
- **THEN** the reader SHALL reject it before reading outside the declared root

#### Scenario: OpenSpec change is incomplete
- **WHEN** proposal, design, specification, or task material is missing
- **THEN** the review SHALL report each missing kind and SHALL NOT create,
  repair, or synthesize the missing provider artifact
