## ADDED Requirements

### Requirement: Token closure and executable composition remain distinct
FlowGuard SHALL preserve assumption/provider and declared-conflict composition as a contract-closure gate and SHALL expose executable joint-state composition as a separate evidence stage under the same canonical checker owner. Neither stage may project the other's pass claim.

#### Scenario: Token closure passes without system evidence
- **WHEN** every component and contract token closes but no current bounded system artifact was checked
- **THEN** the result may report contract composition green but MUST report executable composition not run

#### Scenario: Executable composition passes
- **WHEN** component checks, token closure, exact slice compilation, and the final compiled portable-model check all pass without truncation
- **THEN** the existing portable-compositional-verification commitment may report bounded executable composition green

### Requirement: Composition preserves blocked and invalid evidence classes
Composition SHALL preserve the stage and top-level status vocabulary `pass`, `fail`, `blocked`, `invalid`, and `not_run`. `invalid` denotes malformed or unsupported current-schema input; `blocked` denotes stale, unresolved, omitted, or incomplete evidence; `fail` denotes a current complete semantic counterexample, except for a canonical-checker-confirmed reachable safety witness under truncation; and `not_run` is stage evidence only and can never support a top-level pass.

#### Scenario: Component exploration is truncated
- **WHEN** a component checker returns blocked
- **THEN** token and executable composition remain blocked and cannot be cited as a failed-but-complete proof

#### Scenario: Invalid component input is supplied
- **WHEN** a selected component fails current-schema or reference validation
- **THEN** composition returns invalid rather than blocked or fail

#### Scenario: System stage is not run
- **WHEN** token closure completes but no current system definition/request is checked
- **THEN** the system stage is `not_run` and the top-level result cannot be pass
