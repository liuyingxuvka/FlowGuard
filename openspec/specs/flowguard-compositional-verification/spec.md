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
