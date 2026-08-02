## ADDED Requirements

### Requirement: Independent task facts define the minimum denominator
The system SHALL compile the minimum task-fact denominator from request, current-model, public-surface, and lifecycle observations rather than accepting a caller-selected list as complete. Each fact SHALL carry its source and SHALL be classified as declared, unknown, omitted, scoped-out, or contradictory. Unknown, omitted, contradictory, or unmapped facts SHALL remain visible and SHALL prevent an unqualified whole-task sufficiency claim.

#### Scenario: Caller supplies a smaller fact list
- **WHEN** an independently observed current-model or public-surface fact is absent from the caller-supplied list
- **THEN** the fact remains in the denominator with its provenance and the whole-task claim is unresolved

#### Scenario: Scope deliberately excludes a fact
- **WHEN** a fact is explicitly excluded by an authorized bounded scope
- **THEN** the fact is preserved as scoped-out and the result can claim only that bounded scope

#### Scenario: One observation plane has no current source snapshot
- **WHEN** request, current-model, public-surface, or lifecycle inspection has no current source reference and fingerprint
- **THEN** the missing plane remains a blocking denominator gap and whole-task sufficiency cannot close

### Requirement: Unresolved facts create explicit coverage demand
The system SHALL assign every unknown, omitted, contradictory, or unmapped task fact to an explicit coverage demand owner or return a blocking unresolved-owner diagnostic.

#### Scenario: No owner exists for an unknown fact
- **WHEN** the compiled denominator contains an unknown fact that no canonical owner accepts
- **THEN** the demand result is blocked and identifies the fact and missing ownership
