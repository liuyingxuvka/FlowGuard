## ADDED Requirements

### Requirement: FlowGuard self-qualification uses the public target-system compiler
FlowGuard's self blueprint SHALL provide FlowGuard-specific provider evidence and target data to the same canonical compiler used by external targets. The self wrapper SHALL NOT omit required reports, relax success conditions, inject fallback owners, or use a self-only success rule.

#### Scenario: Generic compiler reports a model-test blocker
- **WHEN** the public compiler returns a blocked model-test report for FlowGuard
- **THEN** the self result SHALL also be blocked or incomplete
- **AND** self-specific convenience fields SHALL NOT remain green

### Requirement: Self evidence is acceptance evidence, not product scope
A passing FlowGuard self blueprint SHALL prove only the FlowGuard target under its exact providers and inventories. Generic capability claims SHALL additionally require independent target fixtures that do not import self-specific owners, models, paths, or helpers.

#### Scenario: Self passes while an external target omits behavior
- **WHEN** FlowGuard self remains green but an external fixture lacks a required behavior, resource, provider, or test member
- **THEN** the external result SHALL fail independently
- **AND** self success SHALL NOT license it

### Requirement: Composed self review reuses one exact blueprint instance
An explicit self-qualification and cleanup pass SHALL build one exact current self blueprint and pass that immutable in-memory instance to the reduction review and compact projection.

#### Scenario: Cleanup rebuilds a different self authority
- **WHEN** cleanup constructs a second blueprint with different provider, inventory, or source identities
- **THEN** the composed self-maintenance result SHALL be blocked as identity-divergent

## MODIFIED Requirements

### Requirement: Self-maintenance exposes honest depth and safe contraction inputs
The self-maintenance parent SHALL consume current child evidence for independent inventory, intent lineage, semantics, model-code-test bindings, resources and oracles, static qualification, and affected-only behavior. It SHALL publish exact gaps and provide ArchitectureReduction only current evidence-bound candidates.

#### Scenario: One FlowGuard test row is orphaned
- **WHEN** the self test inventory contains a required executable node or obligation without a complete current binding
- **THEN** the parent reports the exact orphan and its owner
- **AND** broad self regression success does not close static blueprint qualification

#### Scenario: Static self-blueprint reaches the deepest canonical layer
- **WHEN** every required static child passes
- **THEN** self-maintenance reports static self-blueprint complete with `static_blueprint` as the deepest proven layer

#### Scenario: Self-audit finds an uncertain duplicate path
- **WHEN** the blueprint exposes a possible duplicate helper, adapter, branch, validation route, or facade without current equivalence evidence
- **THEN** the parent emits a typed ArchitectureReduction candidate with unresolved proof status
- **AND** it does not edit or remove the path automatically
