## ADDED Requirements

### Requirement: Workflow step contracts can be projected from plan-detail steps
WorkflowStepContracts SHALL provide a projection from plan-detail steps with receipts, prerequisites, invalidations, and claim gates.

#### Scenario: Step receipts become contracts
- **WHEN** a plan-detail step declares required receipts and produced receipts
- **THEN** the projection creates a `WorkflowStepContract` with matching receipt rules

#### Scenario: Claim-gated receipt blocks premature completion
- **WHEN** a projected contract is required for `done_claimed`
- **THEN** a trace that claims done without the required receipt fails step-contract review
