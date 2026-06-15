## ADDED Requirements

### Requirement: Business path identity capture
Model-first FlowGuard work SHALL capture business-path identity for important
workflow routes when route duplication, conflict, old/new disposition, or
runtime binding can affect confidence.

#### Scenario: Important path records identity
- **WHEN** a modeled workflow contains an important user-facing or business-facing route
- **THEN** the model records a stable path id, business intent, trigger, expected terminal, state writes, side effects, and available evidence or source labels

#### Scenario: Old and new paths record disposition
- **WHEN** a modeled workflow keeps an old path beside a replacement path
- **THEN** the model records whether the old path is superseded, preserved for compatibility, delegated, deleted, or still unresolved

### Requirement: Business path relation capture
Model-first FlowGuard work SHALL record explicit equivalence and exclusivity
between business paths when those relationships explain why similar paths are
valid or invalid.

#### Scenario: Similar paths are declared equivalent
- **WHEN** two paths intentionally perform the same business job
- **THEN** the model records the equivalence and the compatibility or reduction evidence required to keep both paths

#### Scenario: Competing paths are declared exclusive
- **WHEN** two paths share a trigger but are valid only under separate conditions
- **THEN** the model records the exclusive relationship or preconditions that prevent conflict
