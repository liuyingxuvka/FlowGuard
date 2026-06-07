## ADDED Requirements

### Requirement: Installed skill route alignment
Installed FlowGuard Codex skill route maps SHALL stay aligned with the package route graph, including route ids, triggers, minimal workflow, hard gates, evidence boundaries, and downstream handoffs.

#### Scenario: Package route graph adds a group
- **WHEN** the package route graph adds or changes a route group
- **THEN** installed skill guidance SHALL be updated or the mismatch SHALL be recorded as a scoped maintenance obligation
