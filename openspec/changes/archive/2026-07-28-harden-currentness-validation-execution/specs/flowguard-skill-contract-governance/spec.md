## RENAMED Requirements

- FROM: `Seventeen Skill Deep Certification`
- TO: `Canonical Suite Deep Certification`

## MODIFIED Requirements

### Requirement: Canonical Suite Deep Certification
Full skill contract governance SHALL require static skill, contract, depth,
prompt-budget, and target-native validation to pass for every member declared
by the current package-owned consumer authority, with zero hollow-contract,
parallel-route-risk, legacy-schema, missing-control, stale-generation,
retired-public-entry, unresolved-placeholder, or projection-drift findings.

#### Scenario: One canonical member is hollow
- **WHEN** every other authority-declared member passes but one member lacks
  required deep evidence
- **THEN** suite certification fails and reports the exact passing and blocked
  counts rather than a partial suite pass

#### Scenario: Literal historical member count remains
- **WHEN** a current prompt, contract, check, or specification treats a fixed
  historical member count as authority
- **THEN** contract governance fails and requires package-authority derivation

## ADDED Requirements

### Requirement: One suite maintenance unit
All current FlowGuard consumer skill members SHALL remain in the single
`unit:flowguard-suite` author maintenance unit. Every semantic check SHALL have
one target-declared member, evidence subject, execution owner, obligation
boundary, and dependency position. Official OpenSpec and unrelated installed
skills MUST remain outside that unit.

#### Scenario: A second FlowGuard unit reuses suite receipts
- **WHEN** a proposed maintenance unit imports, projects, or reuses a receipt
  from `unit:flowguard-suite`
- **THEN** SkillGuard blocks the plan as foreign-unit evidence

#### Scenario: Same-unit producer owns several projections
- **WHEN** the target explicitly assigns one producer to several semantic
  checks with identical producer inputs and dependencies
- **THEN** the producer executes at most once while each semantic projection
  retains its distinct subject and obligation identity

### Requirement: Maintained prompt reduction preserves semantic gates
Prompt maintenance SHALL compare every touched consumer bundle with its frozen
pre-change byte baseline. A touched bundle MUST be strictly smaller, the total
suite prompt projection MUST be smaller, no ceiling may increase in the same
change, and all target-declared route, prohibition, output, claim-boundary, and
native checks MUST remain current.

#### Scenario: Prompt shrinks by deleting a hard gate
- **WHEN** a prompt bundle is smaller but its semantic check no longer finds a
  required hard gate or prohibited fallback
- **THEN** prompt reduction fails despite the lower byte count

#### Scenario: Untouched prompt grows
- **WHEN** a member outside the declared affected prompt set has a larger
  consumer projection
- **THEN** the reduction plan blocks as an unmapped or unintended change
