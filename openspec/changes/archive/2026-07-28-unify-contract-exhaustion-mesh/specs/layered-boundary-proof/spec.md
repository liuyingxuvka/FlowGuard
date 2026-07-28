## ADDED Requirements

### Requirement: Leaf boundary proof consumes canonical finite cases
FlowGuard layered boundary proof MUST be able to consume canonical
contract-exhaustion case ids as leaf boundary-matrix evidence requirements.

#### Scenario: Leaf matrix cites canonical case
- **WHEN** a leaf boundary matrix proves a generated rejected-input,
  stale-evidence, or wrong-output case
- **THEN** the proof row can cite the canonical contract-exhaustion case id

#### Scenario: Missing case proof scopes parent confidence
- **WHEN** a required canonical case has no current leaf proof evidence
- **THEN** layered boundary proof keeps parent confidence scoped or blocked
