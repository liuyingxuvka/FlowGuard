## MODIFIED Requirements

### Requirement: Project blueprint audit and check commands are read-only
The command surface SHALL provide provider-neutral target-system blueprint audit and check operations for an explicit target descriptor, frozen provider registry, provider snapshot, and any target-specialized definition. Audit SHALL report provider qualification, canonical layer statuses, bindings, and unresolved items; check SHALL return composable status and exit semantics for the requested static claim. Neither operation SHALL write a projection, modify the target, install software, or execute a missing provider.

#### Scenario: A declared workflow blueprint audit is requested
- **WHEN** a caller supplies a bounded workflow target and current observation and authority provider results
- **THEN** the command returns canonical machine-readable provider, lineage, evidence, and depth findings without requiring a programming language
- **AND** the target artifacts and authority pointers remain unchanged

#### Scenario: A target boundary lacks a deep provider
- **WHEN** audit reaches a required source, workflow, trace, resource, or authority boundary for which no registered current provider supplies the required capability
- **THEN** the command returns a non-pass result naming the exact boundary and missing provider capability
- **AND** it does not fall back to FlowGuard's Python self preset or another shallow adapter

#### Scenario: FlowGuard self-blueprint and reduction are requested together
- **WHEN** the self-blueprint check receives the explicit composed architecture-reduction option
- **THEN** it builds one current self-blueprint and returns both compact bounded results from that exact bundle
- **AND** it does not rebuild the blueprint, write a cache, or modify source
