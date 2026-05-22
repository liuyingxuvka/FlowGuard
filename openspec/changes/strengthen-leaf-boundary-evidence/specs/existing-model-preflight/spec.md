## MODIFIED Requirements

### Requirement: Full preflight requires ownership evidence

Full Existing Model Preflight SHALL preserve enough existing model ownership
evidence for the downstream FlowGuard route to reuse, extend, add a child
model, or create a new boundary without duplicating responsibility.

#### Scenario: Parent model layered proof status is unknown
- **WHEN** a full preflight finds an existing model with child models
- **AND** the downstream route depends on parent/child confidence
- **THEN** the preflight MUST record parent coverage, child disjointness, child
  reattachment, leaf boundary-matrix status, and layered proof evidence id
- **AND** missing layered status MUST block the preflight from claiming that the
  existing boundary is fully understood
