## ADDED Requirements

### Requirement: Model signatures carry reusable risk depth
Model similarity signatures SHALL carry reusable risk-template ids, known-bad
case ids, evidence gate ids, and a maturity level so similar models can expose
missing depth.

#### Scenario: Similar models reveal missing template depth
- **WHEN** two model signatures are in the same workflow family and one has reusable risk-template ids while the other does not
- **THEN** the similarity report can surface the missing template depth as an unresolved gap or recommended route

#### Scenario: Known-bad and evidence ids survive handoff
- **WHEN** a similarity handoff is produced for related models
- **THEN** it preserves known-bad case and evidence gate ids needed for downstream model maturation or test alignment
