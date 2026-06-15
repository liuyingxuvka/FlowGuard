## ADDED Requirements

### Requirement: PlanDetailing acts as simulator plan mode
PlanDetailing SHALL act as the `plan_detailing` internal mode for the
development-process simulator while preserving explicit direct use when a user
names `flowguard-plan-detailing-compiler`.

#### Scenario: Simulator delegates rough plan
- **WHEN** the development-process simulator selects `plan_detailing`
- **THEN** PlanDetailing SHALL produce or review structured rows for scope,
  state, artifacts, side effects, receipts, validation, failure branches,
  rework gates, human questions, and final claim evidence

#### Scenario: Direct explicit use remains available
- **WHEN** a user explicitly asks to use `flowguard-plan-detailing-compiler`
- **THEN** PlanDetailing SHALL remain directly invokable with its existing
  hard gates and downstream projection helpers

#### Scenario: Generic automatic use enters simulator
- **WHEN** a user generically asks to discuss or refine a non-trivial plan
- **THEN** PlanDetailing guidance SHALL point the automatic route to
  `flowguard-development-process-flow` and `plan_detailing` mode rather than
  presenting itself as the ordinary first entry
