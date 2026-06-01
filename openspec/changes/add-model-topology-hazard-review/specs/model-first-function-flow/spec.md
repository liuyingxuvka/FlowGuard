## ADDED Requirements

### Requirement: Model-first checks run automatic topology hazard review

FlowGuard SHALL run a default model-topology hazard review inside
`run_model_first_checks(...)` before broad confidence is summarized.

#### Scenario: Topology hazard section is always present

- **GIVEN** a model-first check plan with a workflow
- **WHEN** `run_model_first_checks(...)` runs
- **THEN** the summary MUST include a `topology_hazard` section
- **AND** metadata MUST include the reviewed topology hazard plan and report.

#### Scenario: Unanchored AI concern cannot block confidence

- **GIVEN** a topology hazard candidate with a hard disposition
- **AND** the candidate has no concrete topology anchor
- **WHEN** `review_topology_hazards(...)` runs
- **THEN** the candidate MUST be reported as observation-only
- **AND** it MUST NOT block confidence.

#### Scenario: Anchored future-use hazard stays visible

- **GIVEN** the topology contains a repeatable side effect, external boundary,
  old/new compatibility path, coarse terminal, shared writer, or parent/child
  compression landmark
- **WHEN** no current evidence handles or scopes the derived hazard
- **THEN** the topology hazard report MUST return scoped or blocked confidence
- **AND** it MUST name the required owner route.

### Requirement: Topology hazard APIs are public helper APIs

FlowGuard SHALL expose topology hazard helper APIs through the public helper API
and route registry without adding them to the minimal core `Explorer` API.

#### Scenario: Route-scoped discovery includes topology hazard review

- **WHEN** callers inspect `FLOWGUARD_ROUTE_API`
- **THEN** a `model_topology_hazard_review` group MUST list the topology
  digest, usage intent, hazard candidate, report, inference, and review helper
  names.
