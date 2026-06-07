## ADDED Requirements

### Requirement: Global routing inherits open FlowGuard obligations
Global FlowGuard guidance SHALL make normal FlowGuard work inherit relevant open
maintenance obligations through existing routes instead of invoking a separate
technical-debt scanner.

#### Scenario: Existing obligation is part of route selection
- **WHEN** a non-trivial coding, prompt, skill, test, process, release, archive,
  or publish task touches a model, code path, test surface, or public entrypoint
  with open FlowGuard obligations
- **THEN** global routing MUST include those obligations in route selection
- **AND** it MUST route to the existing owner route named by the obligation

#### Scenario: No standalone technical-debt route
- **WHEN** a task asks FlowGuard to reduce technical-debt risk naturally during
  ordinary use
- **THEN** global routing MUST use existing FlowGuard routes such as
  maintenance scan, model maturation, Architecture Reduction, StructureMesh,
  Model-Test Alignment, DevelopmentProcessFlow, and Risk Evidence Ledger
- **AND** it MUST NOT require a separate technical-debt scanner route

