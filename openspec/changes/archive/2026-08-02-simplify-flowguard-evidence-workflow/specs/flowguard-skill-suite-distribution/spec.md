## ADDED Requirements

### Requirement: Distribution owner publishes typed current suite evidence
The distribution workflow SHALL own current suite identity, clean installation projection, and source/install parity evidence in a form that downstream process gates can verify without duplicating distribution semantics.

#### Scenario: Installed projection is stale
- **WHEN** the source projection identity differs from the installed suite identity
- **THEN** distribution evidence is not current and downstream release confidence remains blocked
