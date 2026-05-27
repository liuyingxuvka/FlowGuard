## ADDED Requirements

### Requirement: Legacy path disposition
FlowGuard SHALL represent the disposition of old or alternate paths during
model-miss closure as one of deleted, blocked, delegated to the repaired path,
same-contract repaired, explicitly out of scope, or unknown.

#### Scenario: Old path is still unknown
- **WHEN** a model miss repair proves a new child path but an old in-scope path
  has missing or unknown disposition
- **THEN** strict model-miss closure SHALL remain blocked

#### Scenario: Old path delegates to repaired path
- **WHEN** the old path is still reachable but its disposition delegates all
  in-scope behavior to the repaired child contract
- **THEN** strict closure MAY pass if the delegation has current proof artifact
  evidence and the parent route coverage consumes it

### Requirement: Parent route coverage includes old paths
FlowGuard SHALL require parent route coverage to include fresh, resume, replay,
old-state, and peer/adapter ingress paths that can reach a repaired or legacy
child boundary.

#### Scenario: Parent coverage omits a reachable old ingress
- **WHEN** a repaired child path has proof but parent route coverage omits a
  reachable legacy or replay ingress
- **THEN** strict parent confidence SHALL report a parent coverage gap
