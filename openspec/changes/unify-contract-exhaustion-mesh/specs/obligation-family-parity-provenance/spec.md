## ADDED Requirements

### Requirement: Family seeds feed canonical bad-case expansion
FlowGuard obligation-family parity MUST provide same-class family seeds to
ContractExhaustionMesh when an observed miss or family mechanism requires
canonical sibling bad-case expansion.

#### Scenario: Seed expands through contract exhaustion
- **WHEN** a family bad-case seed names a required mechanism and sibling
  members
- **THEN** canonical ContractMutationCase rows are generated or required for
  the sibling cases

#### Scenario: Unmodeled sibling relation remains a gap
- **WHEN** a same-class claim lacks a declared sibling relation or mechanism
- **THEN** FlowGuard reports a model gap instead of treating the family as
  exhausted
