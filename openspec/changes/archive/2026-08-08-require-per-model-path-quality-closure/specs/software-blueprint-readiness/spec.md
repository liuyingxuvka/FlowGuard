## ADDED Requirements

### Requirement: Blueprint readiness includes model path-quality closure
Broad software-blueprint readiness SHALL require a current path-quality result for every new or materially changed required model in the independently observed denominator. Missing, stale, unresolved, or semantically mismatched rows SHALL remain exact readiness gaps and SHALL NOT be replaced by model executability, code binding, test presence, or parent aggregation alone.

#### Scenario: Model executes but path quality is unresolved
- **WHEN** a model is executable and bound to code and tests but retains an unresolved path-quality row
- **THEN** broad DNA readiness remains blocked or explicitly scoped for that model boundary

#### Scenario: Unaffected model remains current
- **WHEN** an affected-topology review proves that a prior model and its consumed identities are unchanged
- **THEN** its current path-quality result may remain reusable without deep re-execution
