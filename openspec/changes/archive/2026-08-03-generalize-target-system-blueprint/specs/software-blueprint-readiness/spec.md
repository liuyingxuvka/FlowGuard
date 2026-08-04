## ADDED Requirements

### Requirement: Software blueprint readiness is a target-system specialization
Software-project discovery SHALL contribute provider results to the canonical target-system blueprint. Python, JavaScript, Rust, or another language adapter SHALL be selected by declared provider capability and SHALL NOT define the core target admission rule.

#### Scenario: Non-Python software provider is current
- **WHEN** a bounded software target supplies current observation and authority provider results without a Python provider
- **THEN** FlowGuard SHALL evaluate those results through the canonical blueprint compiler
- **AND** it SHALL NOT reject the blueprint because its language is not Python

#### Scenario: Software adapter is unavailable
- **WHEN** a required source boundary has no current deep-discovery provider
- **THEN** readiness SHALL report a missing-provider gap for that exact boundary
- **AND** candidate discovery SHALL remain incomplete rather than shallow-ready

### Requirement: Project success includes canonical blueprint readiness
A project blueprint success result used for a static DNA claim SHALL require both evidence qualification and canonical static blueprint readiness. An older owner-level or inventory-only qualification SHALL NOT produce success while behavior, binding, resource, intent, or test readiness is blocked.

#### Scenario: Qualification passes but behavior readiness is blocked
- **WHEN** project inventories qualify but behavior contracts, helper ownership, portable bindings, or real test coverage are incomplete
- **THEN** the project blueprint success result SHALL be false
- **AND** the response SHALL preserve the lower layer that passed

### Requirement: Candidate generation never manufactures closure
Software candidate generation SHALL keep inferred semantics, guessed helper ownership, placeholder case designs, and source-only oracle claims unresolved until admitted independent evidence supplies their exact identities.

#### Scenario: Candidate builder discovers a function
- **WHEN** discovery finds a behavior-bearing function but no current block-local semantic or concrete test-case binding exists
- **THEN** the candidate SHALL identify the missing rows
- **AND** it SHALL NOT create accepted generic semantics or a synthetic coverage edge

### Requirement: Missing language adapters are provider gaps
Candidate generation SHALL describe missing deep observation capability for an exact target boundary as a provider gap. It SHALL NOT classify a language or non-code target as globally unsupported by the target-system core.

#### Scenario: No adapter exists for one source boundary
- **WHEN** a software target declares a source boundary for which no current deep-discovery provider is registered
- **THEN** candidate generation SHALL return the exact missing observation capability and boundary
- **AND** another language, workflow, trace, or contract provider SHALL remain independently usable for its declared boundary
