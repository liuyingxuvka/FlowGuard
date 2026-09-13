## ADDED Requirements

### Requirement: Unresolved candidates block cleanup readiness
Architecture-reduction review SHALL report unresolved candidate identities and
count. `cleanup_release_ready` SHALL be false while any candidate necessity,
proof obligation, or authorized disposition remains unresolved, even when the
audit denominator itself is complete.

#### Scenario: Candidate inventory is complete but proof is missing
- **WHEN** the review counts all candidates but one candidate remains
  unresolved or lacks required proof
- **THEN** audit completeness MAY be true
- **AND** cleanup release readiness SHALL be false
