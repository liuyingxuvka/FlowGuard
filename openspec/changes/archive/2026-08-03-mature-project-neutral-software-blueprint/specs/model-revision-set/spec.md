## ADDED Requirements

### Requirement: ModelRevisionSet accounts for intent contributions atomically
A `ModelRevisionSet` SHALL bind the exact admitted intent-contribution inventory used to derive its candidate. Every contribution inside the revision boundary SHALL have one disposition of `accepted`, `superseded`, `rejected`, `deferred`, `conflicting`, or `unresolved`, and each accepted contribution SHALL map to exact changed obligations, states, transitions, invariants, relations, or explicit gaps.

#### Scenario: Accepted user decision changes one candidate behavior
- **WHEN** a user decision is accepted for a candidate revision
- **THEN** the revision set binds the decision fingerprint and every derived changed model identity
- **AND** acceptance remains atomic with the complete affected closure

#### Scenario: Earlier Spark intent is superseded
- **WHEN** an accepted contribution explicitly supersedes an earlier Spark contribution
- **THEN** the revision set preserves both immutable contribution identities and the supersession edge
- **AND** the earlier contribution is not simultaneously treated as an active candidate obligation

#### Scenario: A contribution has no modeled effect
- **WHEN** an admitted accepted contribution maps to no model obligation, state, transition, invariant, relation, or explicit scoped gap
- **THEN** revision validation reports a disconnected intent contribution
- **AND** the revision set cannot be accepted

### Requirement: Intent conflicts and unresolved targets block acceptance without changing current authority
Revision validation SHALL detect contradictory active contributions, incompatible invariants, unreachable desired terminal states, missing supersession, and target outputs with no declared consumer. No such condition SHALL be resolved by source timestamp, document status, or caller assertion alone.

#### Scenario: Two active goals require incompatible invariants
- **WHEN** the same candidate revision contains two active contributions whose required invariants cannot hold together
- **THEN** the conflict remains explicit and acceptance is blocked
- **AND** the current observed head remains unchanged

#### Scenario: A desired terminal is unreachable
- **WHEN** an accepted contribution names a desired terminal that no candidate transition path can reach from a declared initial state
- **THEN** revision validation reports the target and missing path
- **AND** passing local checks for unrelated members cannot close the revision set

#### Scenario: Candidate behavior is implemented and validated
- **WHEN** the complete candidate is implemented, independently validated, and accepted through the existing activation contract
- **THEN** a new `observed_implementation` snapshot is built from the live implementation inventory
- **AND** typed realization and supersession relations connect the candidate lineage to the new sole observed head
