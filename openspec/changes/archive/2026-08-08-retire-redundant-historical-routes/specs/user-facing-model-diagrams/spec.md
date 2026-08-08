## MODIFIED Requirements

### Requirement: No Runtime Semantics Change
The retained `user_facing_model_diagrams` owner SHALL bind deterministic Mermaid export and optional route-specific explanation guidance without changing any checker, model, validation, or completion semantics. Export SHALL preserve stable node identity, direction, escaping, trace/state/loop structure, and deterministic output for the same model identity. Prompt guidance SHALL remain optional for trivial work, SHALL explain the current situation for non-trivial use, SHALL preserve each selected route's edge meaning, and SHALL state that a diagram never substitutes for validation evidence.

#### Scenario: Diagram export changes a checker result
- **WHEN** adding, removing, or rendering a diagram changes pass, fail, blocked, skipped, or not-run semantics
- **THEN** the diagram owner violates its claim boundary and current completion is blocked

#### Scenario: Mermaid content contains unsafe or unstable labels
- **WHEN** model labels require escaping or repeated export sees the same stable model identity
- **THEN** output is safely escaped and deterministic without changing node identity or direction

#### Scenario: Route guidance is compacted
- **WHEN** kernel or satellite prompts are reduced
- **THEN** optional-use boundaries, current-situation explanation, selected route edge meanings, and the no-evidence-substitution rule remain current in source and installed projections

#### Scenario: Diagram implementation or prompt suite changes
- **WHEN** `flowguard/mermaid.py`, its API/tests/spec, or a governed FlowGuard prompt carrying diagram guidance changes
- **THEN** the prior model result becomes stale instead of remaining current from self-only model files
