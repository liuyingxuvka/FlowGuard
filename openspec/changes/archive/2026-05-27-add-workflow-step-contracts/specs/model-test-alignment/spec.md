## ADDED Requirements

### Requirement: Model-Test Alignment consumes workflow step contracts
FlowGuard SHALL allow Model-Test Alignment planning to consume workflow step contracts by projecting each required workflow step into a required model obligation with obligation type `workflow_step`.

#### Scenario: Required step has test evidence
- **WHEN** a projected workflow-step obligation has current passing test evidence of an allowed kind
- **THEN** Model-Test Alignment SHALL treat the obligation as covered using the existing evidence freshness and result-status rules

#### Scenario: Required step lacks test evidence
- **WHEN** a projected workflow-step obligation has no current passing test evidence
- **THEN** Model-Test Alignment SHALL report missing test evidence for that workflow-step obligation
