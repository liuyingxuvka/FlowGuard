## ADDED Requirements

### Requirement: ExistingModelPreflight consumes provider context after plane lookup
ExistingModelPreflight SHALL use spec work-package task and obligation context only after canonical plane-first commitment lookup and SHALL preserve provider context separately from behavior ownership.

#### Scenario: OpenSpec task mentions a product behavior
- **WHEN** a development-process task targets an existing product commitment
- **THEN** preflight SHALL keep the development-process package primary and the product commitment as a typed target rather than merge their owners

#### Scenario: Provider context is stale or unmapped
- **WHEN** the work package lacks current provider identity or reconciliation
- **THEN** preflight SHALL report a scoped context gap and SHALL NOT use the task list as complete model evidence
