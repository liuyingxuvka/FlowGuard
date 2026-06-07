## ADDED Requirements

### Requirement: Model-first work derives three-way binding

The model-first FlowGuard kernel SHALL derive or request model obligations, code
contracts, and test evidence before claiming full FlowGuard confidence.

#### Scenario: Agent claims model coverage
- **WHEN** an agent claims that modeled behavior is covered
- **THEN** the claim must identify the model obligation ids, code contract ids,
  and test evidence ids, or report the missing links as gaps.
