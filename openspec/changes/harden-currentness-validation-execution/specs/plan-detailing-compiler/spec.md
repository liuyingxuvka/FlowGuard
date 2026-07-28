## ADDED Requirements

### Requirement: PlanDetail preserves proof references without producing proof
PlanDetail compilation SHALL preserve an existing proof artifact id, producer
receipt id, result reference, and expected fingerprint exactly as supplied for
later independent resolution. It MUST NOT synthesize a proof artifact,
producer receipt, terminal status, exit code, result fingerprint, currentness,
match result, supersession result, or verification result from planning rows,
task state, expected outcomes, or declared evidence status.

#### Scenario: Plan row declares a passing result
- **WHEN** a PlanDetail row says a check passed or includes an expected result
  path and exit code without loaded producer evidence
- **THEN** the compiled lifecycle projection MUST retain a planned or missing
  evidence requirement
- **AND** it MUST create no `ProofArtifactRef` or passing evidence row

#### Scenario: Exact proof reference is present
- **WHEN** a PlanDetail row contains an existing receipt id, proof id, and
  expected fingerprint
- **THEN** compilation MUST copy those identities unchanged
- **AND** downstream verification, not the compiler, MUST determine whether
  they are current

### Requirement: Plan-only compilation has zero execution authority
Plan-only compilation SHALL be a pure projection. It MUST start zero producers,
acquire zero owner or resource leases, write zero execution receipts or result
artifacts, create zero run manifests, and update zero current-evidence or
current-parent pointers.

#### Scenario: Plan-only includes every validation owner
- **WHEN** compilation produces a complete validation owner plan
- **THEN** the plan MAY expose owner dispositions and reasons
- **AND** no execution-state artifact or lease may be materialized

#### Scenario: A planned owner has no reusable receipt
- **WHEN** plan-only determines that an owner would require execution
- **THEN** it MUST report the `execute` disposition without launching the owner
  or manufacturing its evidence

