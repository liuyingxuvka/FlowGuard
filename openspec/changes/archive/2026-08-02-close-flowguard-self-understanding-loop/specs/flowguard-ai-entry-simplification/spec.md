## ADDED Requirements

### Requirement: Understanding, implementation admission, and user choice remain independent
The AI entry path SHALL report understanding sufficiency, FlowGuard implementation admission, and user execution choice as three independent values. A user choice to proceed directly SHALL NOT upgrade understanding sufficiency or create a FlowGuard-ready result.

#### Scenario: User permits direct code with unresolved understanding
- **WHEN** the user chooses direct execution while required model coverage remains unresolved
- **THEN** the result preserves direct-user-choice, reports unresolved understanding, and does not report FlowGuard-ready

#### Scenario: User requests discussion only
- **WHEN** the user requests no code
- **THEN** the result reports no-code independently of the understanding status

### Requirement: Lightweight use remains available
The AI entry path SHALL permit lightweight or direct work when the caller does not request a complete FlowGuard claim, while preserving all non-waivable authorization and safety boundaries.

#### Scenario: Small task uses a bounded path
- **WHEN** a task has a declared bounded scope and no complete FlowGuard claim is requested
- **THEN** the path can remain lightweight and its result is explicitly scoped
