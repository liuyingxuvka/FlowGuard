## ADDED Requirements

### Requirement: Kernel routes target-system blueprints independently of language
The FlowGuard kernel SHALL route blueprint work by target boundary, provider capabilities, required understanding layers, and affected behavior rather than by a Python-only software branch. Existing satellite owners SHALL retain their native semantics.

#### Scenario: Target is a mixed workflow and service
- **WHEN** the task requires blueprint reasoning across a workflow and an external service contract
- **THEN** the kernel SHALL compose the required provider and satellite contributions under one target-system request
- **AND** it SHALL NOT create a new DNA skill or a language-specific core route
