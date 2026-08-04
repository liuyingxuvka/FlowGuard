## ADDED Requirements

### Requirement: External interruption has an exact settlement lifecycle
After an externally interrupted validation process tree is confirmed absent, DevelopmentProcessFlow SHALL allow an authorized exact settlement that converts only the named residual leases into immutable interrupted evidence. Partial child results SHALL remain non-reusable unless independently current under their own unchanged producer identities.

#### Scenario: Ordinary residual leases remain after process termination
- **WHEN** exact leases name a dead process and lack an internal cleanup marker because the launcher did not execute its finalizer
- **THEN** settlement SHALL bind the exact plan, owners, process identity, zero-descendant observation, operator reason, and terminal interrupted status
- **AND** it SHALL NOT delete unrelated leases or create passing evidence

### Requirement: Parent and child current pointers have separate owners
Child validations SHALL update only child-scoped current pointers. A parent current pointer SHALL be published only with a terminal parent result that accounts for every planned child as executed, reused, blocked, or not run.

#### Scenario: One child passes before parent completion
- **WHEN** a child result is terminal pass and the parent has unfinished children
- **THEN** the child pointer MAY identify that child result
- **AND** the parent pointer SHALL remain absent or explicitly interrupted

