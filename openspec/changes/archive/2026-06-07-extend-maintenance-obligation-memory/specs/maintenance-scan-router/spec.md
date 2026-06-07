## ADDED Requirements

### Requirement: Maintenance scan reopens touched obligations
Maintenance scan SHALL consume prior open maintenance obligations and route them
through existing owner routes when current work touches their anchors.

#### Scenario: Touched code path reopens structure obligation
- **WHEN** a maintenance scan includes a prior open obligation anchored to a
  code path, symbol, module, test surface, model id, or public entrypoint
- **AND** current changed artifacts touch that anchor
- **THEN** the scan MUST return a maintenance action for the obligation's owner
  route
- **AND** broad confidence MUST remain scoped or blocked until current
  owner-route evidence resolves the action

#### Scenario: Untouched obligation remains recorded
- **WHEN** a prior obligation is active but none of the current changed
  artifacts touch its anchors
- **THEN** the scan MAY keep the obligation visible in report metadata
- **AND** it MUST NOT force an unrelated owner-route action for the current
  narrow claim

### Requirement: Maintenance scan does not validate obligations
Maintenance scan SHALL treat reopened obligations as route actions, not as proof
that the underlying structure, model, or evidence risk has been resolved.

#### Scenario: Reopened obligation has current evidence
- **WHEN** a reopened obligation's owner route has current passing evidence
- **THEN** the scan MAY mark the corresponding maintenance action resolved
- **AND** the scan report MUST still identify the owner evidence used

#### Scenario: Reopened obligation lacks evidence
- **WHEN** a reopened obligation lacks current owner-route evidence
- **THEN** the scan MUST keep the action open
- **AND** it MUST NOT report full maintenance confidence for a broad claim

