## ADDED Requirements

### Requirement: Claimed angle resolution binds current owner evidence
Model Angle Deliberation SHALL treat `resolved` as a caller observation only and SHALL require current passing evidence from the declared owner route that covers the exact angle and current subject identity before the angle can stop blocking a required broad claim.

#### Scenario: Bare resolved flag is rejected
- **WHEN** a required current angle is marked resolved without current owner-route proof for that angle
- **THEN** the review MUST keep the angle unresolved or scoped and MUST NOT support full confidence

#### Scenario: Exact owner proof resolves the angle
- **WHEN** a required current angle is marked resolved and its current passing proof comes from the declared owner route, covers the angle obligation, and matches the current subject fingerprints
- **THEN** the review MAY treat the angle as resolved within the proof's declared boundary

### Requirement: Model angles contribute gaps to maturation
Model Angle Deliberation SHALL expose every unresolved, deferred, scoped, or stale required angle as a typed contribution to the task-local Model Maturation coverage universe.

#### Scenario: Unresolved angle cannot disappear from an empty caller signal list
- **WHEN** Model Angle Deliberation has an unresolved required angle and a caller supplies no matching maturation signal
- **THEN** the compiled maturation intake MUST still contain the angle coverage item and an open signal owned by the angle's declared route
