## ADDED Requirements

### Requirement: Parent success recomposes exact leaf evidence
A TestMesh parent SHALL list the complete frozen leaf inventory and SHALL recompose only from exact current child receipt ids and covered-member fingerprints. Parent command success SHALL NOT manufacture a missing leaf or case.

#### Scenario: One required child receipt is absent
- **WHEN** the frozen parent requires child owners A and B but only A has current terminal evidence
- **THEN** the parent SHALL remain incomplete
- **AND** B SHALL remain visibly `execute`, `not_run`, or `blocked`

### Requirement: Affected-only freshness follows explicit ownership edges
Source, model, contract, provider, checker, and environment changes SHALL invalidate only owners that explicitly consume the changed component and their genuine receipt dependants. Unknown or ambiguous ownership SHALL block instead of expanding to run-all.

#### Scenario: One model fingerprint changes
- **WHEN** only model B changes and model A has exact-current independent evidence
- **THEN** A MAY remain reusable
- **AND** B and its declared dependants SHALL require current execution

#### Scenario: Changed component has no owner edge
- **WHEN** an affected component cannot be assigned to one exact validation owner
- **THEN** planning SHALL block before execution
- **AND** it SHALL NOT choose a global fallback owner or all-suite run

### Requirement: Passing leaf receipts come only from the exact supervised producer
A passing validation-owner leaf SHALL be published only from the in-process bounded supervisor result for the exact frozen contract command and working directory. Success SHALL require zero exit, a successful containment query, an exited root process, an explicitly empty descendant-process set, unchanged governed inputs, and one current pre-publication verification. Caller-authored child status, a serialized terminal artifact, or a public generic receipt saver SHALL NOT publish pass.

#### Scenario: Caller self-reports a passing child
- **WHEN** ordinary code constructs a passing child result or a green-looking supervision value without running the frozen owner command
- **THEN** no passing leaf receipt SHALL be published
- **AND** non-pass recording SHALL remain a separate API that rejects `pass`

#### Scenario: Supervised command or working directory differs
- **WHEN** a genuine supervised result was produced for a different command or working directory than the current owner contract
- **THEN** publication SHALL block with the exact command or working-directory mismatch

#### Scenario: Windows Job still reports only the exited root PID
- **WHEN** the root process has exited and a containment query transiently retains only that root PID
- **THEN** the root PID SHALL be excluded from descendant ids
- **AND** an unknown query or any genuine child PID SHALL still block success

#### Scenario: Inputs drift immediately before publication
- **WHEN** governed inputs change after execution or after receipt preparation but before final publication
- **THEN** the prepared evidence SHALL NOT become a current passing receipt
- **AND** the publisher SHALL stage proof data, rederive currentness, and publish only the verified immutable result
