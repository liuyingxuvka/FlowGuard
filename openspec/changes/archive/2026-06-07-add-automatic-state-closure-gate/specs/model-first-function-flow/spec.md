## ADDED Requirements

### Requirement: Model-first checks run automatic state closure review

FlowGuard SHALL run a default state/input closure review inside
`run_model_first_checks(...)` before broad confidence is summarized.

#### Scenario: Inferred unknown policy scopes confidence

- **GIVEN** a model-first check plan with finite external inputs or finite
  dataclass state fields
- **WHEN** the caller does not provide an explicit state closure policy
- **THEN** FlowGuard MUST infer visible dimensions and representative unknown
  cases
- **AND** the summary MUST include a `state_closure` section with scoped
  confidence rather than treating the finite enumeration as a full pass.

#### Scenario: Explicit safe open boundary passes closure

- **GIVEN** a `StateClosurePlan` declares an `open_boundary` dimension
- **AND** representative unknown cases are supplied or generated
- **AND** the handling rejects, blocks, isolates, or routes unknown values before
  side effects
- **WHEN** `review_state_closure(...)` runs
- **THEN** the closure report MUST allow full state closure confidence for that
  dimension.

#### Scenario: Unsafe unknown handling blocks confidence

- **GIVEN** an open or unbounded closure dimension
- **WHEN** unknown values are accepted as normal flow or can cause side effects
  before resolution
- **THEN** the closure report MUST block confidence instead of returning a clean
  pass.

### Requirement: State closure APIs are public helper APIs

FlowGuard SHALL expose state closure helper APIs through the public helper API
and route registry without adding them to the minimal core `Explorer` API.

#### Scenario: Route-scoped discovery includes state closure

- **WHEN** callers inspect `FLOWGUARD_ROUTE_API`
- **THEN** a `state_closure` group MUST list the state closure helper types,
  constants, inference helper, and review helper.
