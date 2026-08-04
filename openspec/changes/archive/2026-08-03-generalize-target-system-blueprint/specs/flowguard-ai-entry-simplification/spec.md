## ADDED Requirements

### Requirement: AI entry consumes one compact blueprint summary
The ordinary FlowGuard entry SHALL expose one compact, read-only blueprint summary containing target identity, affected or whole scope, layer statuses, deepest proven layer, first gap, and gap count. It SHALL NOT require the AI to load the complete blueprint merely to decide whether it understands enough.

#### Scenario: Lightweight maintenance task is requested
- **WHEN** the task affects a bounded neighborhood and its compact summary proves that neighborhood current
- **THEN** the entry MAY route scoped work without claiming whole-target DNA readiness
- **AND** unrelated whole-target gaps remain visible

#### Scenario: Whole-target claim is requested
- **WHEN** the AI proposes a whole-target blueprint-completeness claim
- **THEN** the entry SHALL require a current whole-target static blueprint summary
- **AND** prose confidence or direct user permission SHALL NOT fill a blueprint gap

### Requirement: Provider gaps are explained in target language
AI-facing results SHALL describe a missing source, workflow, trace, intent, resource, or authority provider as an exact evidence gap rather than describing every target as a Python software project.

#### Scenario: Non-code workflow lacks an oracle provider
- **WHEN** a workflow target has current steps and state but lacks an independent oracle provider
- **THEN** the AI entry SHALL name the missing oracle capability and affected behavior
- **AND** it SHALL NOT ask for a Python adapter
