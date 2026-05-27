## ADDED Requirements

### Requirement: Deterministic challenge scenario synthesis
FlowGuard SHALL allow the existing scenario matrix builder to add bounded,
deterministic adversarial challenge patterns from the same input and initial
state data used by existing generated scenarios.

#### Scenario: Builder creates challenge routes
- **WHEN** a caller adds challenge patterns to a builder with at least two
  inputs
- **THEN** the resulting scenarios include high-risk repeated, delayed,
  stale-state, terminal-replay, and partial-failure style input sequences as
  ordinary Scenario Sandbox scenarios

#### Scenario: Builder respects existing limits
- **WHEN** a caller sets max scenario or max sequence length limits
- **THEN** challenge routes beyond those limits are omitted without bypassing
  the existing builder limits

### Requirement: Generated challenge routes remain candidate evidence
FlowGuard SHALL keep generated challenge scenarios candidate-only by default
unless the caller supplies an explicit domain expectation or oracle.

#### Scenario: Generated challenge route has no oracle
- **WHEN** a caller builds challenge routes without an explicit expectation
- **THEN** each generated scenario defaults to `needs_human_review`

#### Scenario: Caller supplies expectation
- **WHEN** a caller supplies an explicit ScenarioExpectation
- **THEN** generated challenge routes use that expectation exactly like other
  generated matrix scenarios

### Requirement: Model-derived challenge route synthesis
FlowGuard SHALL synthesize candidate challenge scenarios from actual model
evidence in a FlowGuard check report, not only from static input permutations.

#### Scenario: Counterexample becomes a candidate route
- **WHEN** an Explorer report contains an invariant violation with a concrete
  trace
- **THEN** FlowGuard can create a candidate Scenario using the trace's exact
  external input sequence and initial state

#### Scenario: Trace semantics become route reasons
- **WHEN** an Explorer report contains repeated labels, repeated blocks,
  interleaved replay, state revisits, dead branches, exceptions, or trace text
  with risk signals
- **THEN** generated challenge scenarios include model-derived tags and notes
  that explain the model evidence behind the route

#### Scenario: Runner exposes model-derived candidates
- **WHEN** `run_model_first_checks` auto-generates scenarios for a relevant
  risk profile and Explorer produces model evidence
- **THEN** the summary includes a model-derived challenge section and keeps
  those generated scenarios as candidate evidence

### Requirement: Risk explanation is visible
FlowGuard SHALL attach risk-oriented tags and notes to generated challenge
routes so users can understand why each route is likely to expose bugs.

#### Scenario: Challenge route records risk tags
- **WHEN** the builder creates a delayed replay or stale-state challenge route
- **THEN** the scenario includes tags identifying the challenge route and risk
  family

#### Scenario: Challenge route records risk notes
- **WHEN** the builder creates a challenge route
- **THEN** the scenario notes explain the high-risk condition without requiring
  a separate report format

### Requirement: Existing helper packs reuse challenge synthesis
FlowGuard helper packs SHALL reuse the existing scenario matrix builder's
challenge route synthesis rather than introducing a separate generated-test
workflow.

#### Scenario: Retry and side-effect packs include challenge routes
- **WHEN** retry or side-effect pack scenarios are generated
- **THEN** their output includes bounded challenge routes for repeated or
  delayed side-effect risks

#### Scenario: Deduplication and cache packs include challenge routes
- **WHEN** deduplication or cache pack scenarios are generated
- **THEN** their output includes bounded challenge routes for duplicate,
  stale-state, or replay-after-change risks
