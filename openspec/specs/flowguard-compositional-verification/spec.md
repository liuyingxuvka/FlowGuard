# flowguard-compositional-verification Specification

## Purpose
Define how independently checked parent and child models are bound, refined, composed, and diagnosed without turning local success into unsupported whole-system confidence.
## Requirements
### Requirement: Explicit Parent Child Refinement
The system SHALL require a complete explicit binding from every reachable child state and transition to a parent state and transition or to a declared stutter permitted by the binding.

#### Scenario: Child step refines parent step
- **WHEN** mapped source, target, input, and output symbols match one parent transition
- **THEN** the child transition satisfies step refinement

#### Scenario: Unmapped child step fails
- **WHEN** a reachable child transition lacks a parent transition mapping and is not an allowed stutter
- **THEN** refinement fails with the child trace and missing mapping id

### Requirement: Contract Substitutability
The system SHALL reject a child that requires stronger assumptions than its parent or fails to provide every parent guarantee.

#### Scenario: Stronger child precondition is rejected
- **WHEN** the child assumption set contains a requirement absent from the parent assumption set
- **THEN** refinement fails with the strengthened assumption tokens

#### Scenario: Child covers parent guarantees
- **WHEN** every parent guarantee is declared by the child and step refinement passes
- **THEN** the guarantee projection passes

### Requirement: Assume Guarantee Composition
The system SHALL verify that each component assumption is supplied by the environment or another component guarantee and that declared guarantee conflicts are absent.

#### Scenario: Closed composition passes
- **WHEN** all component models pass, all assumptions are supplied, and no conflict pair is present
- **THEN** composition passes with exact provider bindings

#### Scenario: Missing provider blocks composition
- **WHEN** a component assumption has no environment or peer guarantee provider
- **THEN** composition fails with the unresolved token and component id

### Requirement: Compositional Counterexample Preservation
The system SHALL retain the smallest available child trace, mapped parent trace, contract gap, or incompatible component pair for every failed composition or refinement claim.

#### Scenario: Refinement failure is actionable
- **WHEN** a concrete child transition does not refine its declared parent transition
- **THEN** the report identifies both transition ids, mapped states, and the mismatched symbol

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
