## MODIFIED Requirements

### Requirement: Canonical Suite Deep Certification
Full skill contract governance SHALL require static skill, contract, depth,
prompt-budget, and target-native validation to pass for every member declared
by the current package-owned consumer authority, with zero hollow-contract,
parallel-route-risk, legacy-schema, missing-control, stale-generation,
retired-public-entry, unresolved-placeholder, or projection-drift findings.
Consumer readiness SHALL separately require a clean target-owned projection
with no author controls.

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
