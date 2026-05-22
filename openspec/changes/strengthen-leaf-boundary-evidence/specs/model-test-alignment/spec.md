## MODIFIED Requirements

### Requirement: Test evidence binds to code contracts when contracts are in scope

When code external contracts are included, ordinary test evidence SHALL bind to
both the relevant model obligations and the relevant code contract ids.

#### Scenario: Duplicate primary edge proof requires a child split
- **WHEN** more than one current passing primary `edge_path` evidence row
  claims the same model obligation
- **THEN** Model-Test Alignment MUST report
  `obligation_too_coarse_for_primary_evidence`
- **AND** the decision MUST be `child_model_split_required`
- **AND** the report MUST NOT treat downgrading one proof to supporting evidence
  as coverage unless that evidence is attached to a child obligation, code
  contract, or leaf matrix cell

#### Scenario: Leaf matrix-cell evidence is not a duplicate primary proof
- **WHEN** multiple current passing test rows claim the same model obligation
  and kind but are marked as leaf matrix-cell evidence with distinct target
  cell ids
- **THEN** Model-Test Alignment MUST NOT report duplicate primary ownership for
  those rows

#### Scenario: Supporting evidence has no target
- **WHEN** a supporting or leaf matrix-cell evidence row does not identify the
  child obligation, code contract, or leaf cell it supports
- **THEN** Model-Test Alignment MUST block the coverage claim with a missing
  target finding
