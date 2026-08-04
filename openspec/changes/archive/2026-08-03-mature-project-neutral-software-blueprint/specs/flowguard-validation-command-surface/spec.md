## ADDED Requirements

### Requirement: Project blueprint audit and check commands are read-only
The command surface SHALL provide project-neutral blueprint audit and check operations for a declared project root and blueprint definition. Audit SHALL report discovered inventories, bindings, layer statuses, and unresolved items; check SHALL return composable status and exit semantics for the requested static or receipt-qualified claim. Neither operation SHALL write a projection, modify the target project, install software, or run reconstruction.

#### Scenario: A project blueprint audit is requested
- **WHEN** a caller runs the project-neutral audit for a bounded Python project
- **THEN** the command returns canonical machine-readable inventory, lineage, binding, evidence, and depth findings
- **AND** the project tree and model-authority pointer remain unchanged

#### Scenario: Static check has no reconstruction receipt
- **WHEN** a caller requests static qualification and supplies no empirical reconstruction evidence
- **THEN** the command evaluates every static layer and reports reconstruction `not_run`
- **AND** it does not launch a reconstruction helper or subprocess

#### Scenario: Unsupported language is inside the boundary
- **WHEN** audit reaches a behavior-bearing source that no registered discovery adapter supports
- **THEN** the command returns a non-pass result naming the exact path and missing adapter
- **AND** it does not fall back to FlowGuard's Python self preset

### Requirement: Export and reconstruction remain separately explicit
Read-only audit and check SHALL remain separate from deterministic export, and all of those surfaces SHALL remain separate from empirical reconstruction execution. A reconstruction requirement flag MAY require validation of a supplied receipt, but SHALL NOT authorize or start reconstruction.

#### Scenario: Audit is used during ordinary maintenance
- **WHEN** ordinary affected-only maintenance invokes project blueprint audit or check
- **THEN** no blueprint projection is written unless the existing explicit export surface is separately invoked
- **AND** reconstruction remains `not_run`

#### Scenario: Reconstruction evidence belongs to another blueprint
- **WHEN** a check receives a reconstruction receipt whose blueprint fingerprint differs from the current qualification
- **THEN** the empirical layer is blocked with the identity mismatch
- **AND** the static-layer result remains independently reported

#### Scenario: JSON output is requested
- **WHEN** a caller requests canonical JSON from audit or check
- **THEN** the result preserves stable layer, finding, owner, fingerprint, skipped, and `not_run` fields
- **AND** human progress text does not replace the terminal result
