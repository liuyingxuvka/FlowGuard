## ADDED Requirements

### Requirement: Concrete miss records preserve behavior identity
Runtime, UI, and recurring-defect miss records SHALL preserve the affected behavior plane, affected commitment id, primary owner model id, and typed related relation ids when those identities are known.

#### Scenario: UI test operation miss is recorded
- **WHEN** an AI-operated UI integration run fails because the agent did not connect required services
- **THEN** the concrete miss record SHALL identify the `agent_operation` commitment and owner model
- **AND** the visible product capability MAY be recorded only as typed related context

#### Scenario: Identity is unknown
- **WHEN** concrete evidence proves a failure but no commitment identity can be found
- **THEN** the record SHALL preserve the selected plane and a coverage-gap status
- **AND** SHALL route to Behavior Commitment Ledger gap backfill

### Requirement: Recurring defect gates remain plane-local
Defect-family gates SHALL bind their observed failure, canonical cases, owner model, and commitment to one primary behavior plane.

#### Scenario: Same symptom occurs in different planes
- **WHEN** two defects share a visible symptom but fail different product/agent/process promises
- **THEN** they SHALL NOT be counted as one recurrence family without an explicit family relation and separate plane-local owners

### Requirement: Lookup backfeed remains evidence-bound
Runtime miss lookup backfeed SHALL remain evidence-bound. Concrete miss records MAY contribute stable error signatures and workflow-family terms to lookup binding only when the record names the source evidence and affected commitment or gap.

#### Scenario: Unverified diagnosis cannot become lookup binding
- **WHEN** a failure explanation is speculative or lacks current observed evidence
- **THEN** the system SHALL NOT register its text as a canonical error signature
