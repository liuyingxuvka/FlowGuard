## ADDED Requirements

### Requirement: Risk ledger consumes model-angle evidence
Risk Evidence Ledger SHALL consume model-angle review evidence when a final
claim relies on the agent having considered additional model angles.

#### Scenario: Model-angle review is required but unnamed
- **WHEN** a risk row requires model-angle review
- **AND** no model-angle evidence id is named
- **THEN** the ledger MUST report missing model-angle review before full confidence

#### Scenario: Model-angle review is not current or not full
- **WHEN** a named model-angle review is stale, scoped, partial, or blocked
- **THEN** the ledger MUST keep the claim scoped or blocked rather than treating the review as full evidence
