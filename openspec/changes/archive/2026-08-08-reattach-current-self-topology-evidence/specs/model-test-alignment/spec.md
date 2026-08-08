## ADDED Requirements

### Requirement: Delegated assertion helpers resolve recursively with lexical identity
A delegated assertion helper SHALL count toward a coverage contract only when its complete current call graph recursively terminates at exact assertion or native-check leaves. Every helper and leaf identity SHALL include its current source owner and lexically qualified identity so nested functions, methods, closures, and same-named helpers in different scopes remain distinct. Cycles, unresolved dynamic calls, ambiguous lexical owners, stale fingerprints, or a branch with no assertion leaf SHALL block the delegated coverage path.

#### Scenario: Nested helper reaches a real assertion leaf
- **WHEN** a coverage contract delegates through several current helpers and every recursive branch terminates at exact current assertion or native-check members
- **THEN** Model-Test Alignment MAY bind those leaves to the original coverage contract
- **AND** every intermediate helper SHALL retain its lexically qualified identity and call edge

#### Scenario: Two nested helpers share a short name
- **WHEN** two helpers have the same local function name but different enclosing functions, methods, modules, or source owners
- **THEN** they SHALL remain distinct delegated-helper identities
- **AND** a short-name match SHALL NOT merge their leaves, fingerprints, coverage, or execution evidence

#### Scenario: Recursive helper branch is unresolved
- **WHEN** any reachable delegated-helper branch cycles, resolves dynamically without current evidence, names a stale helper, or terminates without an assertion/native-check leaf
- **THEN** the exact coverage path SHALL remain incomplete or blocked
- **AND** a passing sibling branch SHALL NOT satisfy the unresolved branch

### Requirement: Helper delegation preserves coverage owner and execution layer
The exact owner declared by the coverage contract SHALL remain the coverage owner across all delegated helper edges. A helper, assertion leaf, test container, full parent, or aggregate suite SHALL NOT take ownership of the coverage contract or lend its result to another behavior. An accepted planned checker and complete helper graph SHALL remain static design; execution SHALL remain `not_run` until a current terminal receipt binds the exact coverage owner, behavior, case, leaf member, subject, and result.

#### Scenario: Helper is relabeled as coverage owner
- **WHEN** a delegated helper or assertion leaf is presented as the coverage owner instead of the owner declared by the coverage contract
- **THEN** Model-Test Alignment SHALL reject the ownership substitution
- **AND** the helper MAY remain only an exact delegated implementation member

#### Scenario: Planned checker has no leaf execution receipt
- **WHEN** the planned checker, helper graph, oracle, coverage owner, and leaf identities are complete but no exact current terminal receipt covers the leaf member
- **THEN** static design MAY remain accepted
- **AND** execution SHALL remain `not_run`

#### Scenario: Parent or suite pass is copied to the helper path
- **WHEN** a parent model or aggregate suite passes but the exact coverage owner and leaf member lack their own terminal execution evidence
- **THEN** the delegated path SHALL remain `not_run`, incomplete, or blocked
- **AND** the aggregate result SHALL remain evidence only for its own declared owner and subject
