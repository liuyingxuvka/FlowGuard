## REMOVED Requirements

### Requirement: Seventeen Skill Deep Certification
**Reason**: A fixed historical member count is not current suite authority.
The package-owned consumer authority now supplies the exact public member set.

**Migration**: Use `Canonical Suite Deep Certification`; do not retain a
seventeen-member alias, compatibility reader, or parallel certification path.

## ADDED Requirements

### Requirement: Canonical Suite Deep Certification
Full author skill contract governance SHALL require static skill, contract,
depth, prompt-budget, and target-native validation to pass for every member
declared by the current package-owned consumer authority, with zero
hollow-contract, parallel-route-risk, legacy-schema, missing-control,
stale-generation, retired-public-entry, unresolved-placeholder, or
projection-drift findings. Consumer readiness SHALL separately require a clean
target-owned projection with no author controls.

#### Scenario: One canonical member is hollow
- **WHEN** every other authority-declared member passes but one member lacks
  required deep evidence
- **THEN** suite certification fails and reports the exact passing and blocked
  counts rather than a partial suite pass

#### Scenario: Literal historical member count remains
- **WHEN** a current prompt, contract, check, or specification treats a fixed
  historical member count as authority
- **THEN** contract governance fails and requires package-authority derivation

### Requirement: One suite maintenance unit
All current FlowGuard consumer skill members SHALL remain in the single
`unit:flowguard-suite` author maintenance unit. Every semantic check SHALL
have one target-declared member, evidence subject, execution owner, obligation
boundary, and dependency position. Official OpenSpec and unrelated installed
skills MUST remain outside that unit, and receipts MUST NOT cross maintenance
unit boundaries.

#### Scenario: A second FlowGuard unit reuses suite receipts
- **WHEN** a proposed maintenance unit imports, projects, or reuses a receipt
  from `unit:flowguard-suite`
- **THEN** SkillGuard blocks the plan as foreign-unit evidence

#### Scenario: Same-unit producer owns several projections
- **WHEN** the target explicitly assigns one producer to several semantic
  checks with identical producer inputs and dependencies
- **THEN** the producer executes at most once while each semantic projection
  retains its distinct subject and obligation identity
