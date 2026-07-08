## ADDED Requirements

### Requirement: Model misses upgrade the model before same-class exhaustion
FlowGuard MUST require non-trivial in-scope model misses to be abstracted into
a model rule or declared boundary before same-class bad-case exhaustion can
support broad closure.

#### Scenario: Observed bug becomes model rule
- **WHEN** a runtime, test, replay, or manual validation bug appears after a
  FlowGuard pass
- **THEN** the review records the root-cause model gap and the model rule or
  declared boundary that now represents the bug class

#### Scenario: Same-class closure uses contract exhaustion
- **WHEN** the repaired bug class requires same-class evidence
- **THEN** ModelMissReview uses ContractExhaustionMesh cases rather than a
  hand-written same-class case as canonical coverage
