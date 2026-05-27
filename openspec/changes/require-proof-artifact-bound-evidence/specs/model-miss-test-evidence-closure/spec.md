## MODIFIED Requirements

### Requirement: Recurring model misses promote to a defect-family gate
FlowGuard SHALL require an artifact-backed defect-family gate when the same
same-class model-miss family recurs or when the miss is high risk enough that a
local point fix would overclaim final confidence.

#### Scenario: Recurring family without promotion is blocked
- **WHEN** a same-class model miss has occurred more than once and no
  defect-family gate has been promoted
- **THEN** FlowGuard SHALL report the recurring miss as blocked and SHALL NOT
  allow full confidence for the affected family

#### Scenario: Promoted family has current artifact-backed proof
- **WHEN** a promoted defect family names a model obligation, authority
  boundary, observed failure case, same-class generalized case, historical
  holdout case, current external passing proof evidence, and a current proof
  artifact reference
- **THEN** FlowGuard SHALL allow the defect-family gate to pass

#### Scenario: Declaration-only evidence is insufficient
- **WHEN** a promoted defect family only has caller-declared passing evidence
  without proof artifact binding
- **THEN** FlowGuard SHALL keep the defect-family gate blocked in strict
  closure mode

### Requirement: Model miss closure includes legacy path disposition
FlowGuard SHALL block full closure for a repaired model miss until every
in-scope old, alternate, replay, or recovery path is proven deleted, blocked,
delegated to the repaired contract, repaired to the same contract, or explicitly
out of scope.

#### Scenario: Repaired child path does not dispose old path
- **WHEN** a repaired child path has current same-class evidence but an old
  route path remains reachable with unknown disposition
- **THEN** model-miss closure SHALL remain blocked
