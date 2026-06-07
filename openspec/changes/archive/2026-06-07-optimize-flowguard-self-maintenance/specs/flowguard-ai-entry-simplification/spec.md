## ADDED Requirements

### Requirement: Compact route profiles
FlowGuard AI entry surfaces SHALL expose compact route profiles that identify route id, trigger, minimal inputs, outputs, evidence owner, and next actions before exposing broad helper lists.

#### Scenario: Route-first API lookup
- **WHEN** an AI consumer asks how to perform a FlowGuard maintenance task
- **THEN** the API documentation and public route helpers SHALL point to the compact route profile for that task

#### Scenario: Full helper list remains available
- **WHEN** a consumer needs the full helper API
- **THEN** the full helper lists SHALL remain available behind the route-first entry surface

### Requirement: Flat surface warning
FlowGuard AI guidance SHALL warn against treating `__all__`, `MODELING_HELPER_API`, or broad helper lists as the first planning surface.

#### Scenario: Large helper API exists
- **WHEN** the helper API contains many exported names
- **THEN** docs and tests SHALL continue to prefer route profile discovery for AI usage
