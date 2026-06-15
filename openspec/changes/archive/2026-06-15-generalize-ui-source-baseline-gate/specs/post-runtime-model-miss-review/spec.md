## ADDED Requirements

### Requirement: Source-target UI drift is a model miss
Post-runtime Model Miss Review SHALL classify user-observed source page, region, task, interaction, or control-placement drift after green UI evidence as a source-target model miss rather than a local button-only defect.

#### Scenario: Control appears in wrong target task
- **WHEN** a user reports that a source-based UI control appears in the wrong page, region, or user task after FlowGuard evidence was green
- **THEN** Model Miss Review records the previous green model, the real source expectation, the observed target drift, affected same-class controls or tasks, and the missing source-target mapping evidence

#### Scenario: Target document was wrong
- **WHEN** the target model is internally consistent but conflicts with the source baseline or approved difference ledger
- **THEN** Model Miss Review backpropagates the miss to source-baseline modeling and same-class counterexamples
