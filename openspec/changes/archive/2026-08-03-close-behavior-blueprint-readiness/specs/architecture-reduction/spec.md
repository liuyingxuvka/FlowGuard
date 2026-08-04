## ADDED Requirements

### Requirement: Self-reduction review is fingerprinted machine evidence
A FlowGuard pre-release self-reduction review SHALL bind the exact self-blueprint fingerprint, independently declared candidate denominator, observable contracts, proof status, target action, required next route, and residual risk for every candidate. Narrative notes SHALL NOT substitute for this report.

#### Scenario: Narrative lists three completed reductions
- **WHEN** a self-audit document names reductions but no current machine report binds their candidate universe and proof
- **THEN** reduction review SHALL remain not run for release purposes

#### Scenario: Candidate lacks equivalence evidence
- **WHEN** a candidate may reduce code but current behavior-preservation evidence is incomplete
- **THEN** it SHALL remain `blocked_by_missing_evidence` or `manual_review`
- **AND** no cleanup SHALL occur automatically

