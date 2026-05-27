# model-boundary-diff-propagation Specification

## Purpose
TBD - created by archiving change propagate-model-boundary-diffs. Update Purpose after archive.
## Requirements
### Requirement: Boundary diff capture
FlowGuard SHALL represent a child model boundary change as a semantic diff that
identifies old and new ownership for affected functions, state fields, side
effects, invariants, contracts, risk classes, and validation evidence.

#### Scenario: Child widens risk ownership
- **WHEN** a child model expands from owning one failure mode to owning a
  broader risk class
- **THEN** the boundary diff records the old owner, the new owner, the widened
  risk class, and the evidence that must be refreshed

#### Scenario: Child drops state ownership
- **WHEN** a child model stops owning writes for a state field
- **THEN** the boundary diff records the removed write responsibility and marks
  the parent partition map as requiring reconciliation

### Requirement: Parent propagation reconciliation
FlowGuard SHALL propagate child boundary diffs to the parent model and SHALL
mark affected parent coverage, partition, freshness, and release-readiness
claims stale until the parent reconciles the diff.

#### Scenario: Parent map accepts propagated diff
- **WHEN** the parent partition map is updated to assign every changed coverage
  item to a parent owner, child owner, shared-kernel owner, or read-only shared
  use
- **THEN** parent propagation reports the diff as reconciled

#### Scenario: Parent map omits propagated diff
- **WHEN** a propagated diff affects a parent coverage item that has no valid
  owner after reconciliation
- **THEN** parent propagation reports a coverage-gap finding and does not
  return green release-readiness evidence

### Requirement: Sibling intersection review
FlowGuard SHALL recheck sibling models whose declared boundaries intersect a
propagated child diff and SHALL distinguish permitted shared reads from unsafe
duplicate ownership or handoff drift.

#### Scenario: Intersecting sibling owns same side effect
- **WHEN** a propagated diff gives one child ownership of a side effect already
  owned by a sibling
- **THEN** sibling review reports an ownership-conflict finding

#### Scenario: Non-intersecting sibling remains fresh
- **WHEN** a sibling model declares no intersecting function, state, side
  effect, invariant, contract, or risk-class boundary
- **THEN** sibling review does not require that sibling evidence to be rerun for
  this diff

#### Scenario: Shared read remains allowed
- **WHEN** a sibling only reads a state field whose write owner changed in the
  propagated diff
- **THEN** sibling review treats the read as allowed only if the parent
  partition map still declares the write owner explicitly

### Requirement: Bug instances are holdout evidence
FlowGuard SHALL treat observed bug instances as validation or holdout evidence
only, and SHALL NOT treat an observed bug instance as the sole model target.

#### Scenario: Known bug is the only target
- **WHEN** a model-miss repair represents only the observed bug instance and no
  same-class generalized responsibility boundary
- **THEN** the review fails as point-fix-only modeling

#### Scenario: Known bug validates generalized class
- **WHEN** the model represents the generalized bug class and keeps the observed
  bug instance as holdout evidence
- **THEN** the review can use the observed instance to validate the generalized
  model without making the instance the target

### Requirement: Bug-class responsibility precision
FlowGuard SHALL judge model precision against the bug-class responsibility
boundary that the model claims to own, including parent, child, sibling,
shared-kernel, and escalated ownership decisions.

#### Scenario: Bug class belongs to another boundary
- **WHEN** a model claims precision for a bug class whose function, state, side
  effect, or risk ownership belongs to another model boundary
- **THEN** the review reports a responsibility-boundary mismatch

#### Scenario: Bug class crosses sibling boundaries
- **WHEN** a generalized bug class spans two sibling ownership boundaries
- **THEN** the review requires parent escalation, shared-kernel ownership, or an
  explicit handoff contract before precision can be accepted

### Requirement: Large propagation checks use mesh and budget evidence
FlowGuard SHALL route large or slow propagation checks through ModelMesh,
Budgeted model-group, and LongCheck evidence conventions instead of weakening
required checks or treating incomplete evidence as passing.

#### Scenario: Propagation creates a large parent review
- **WHEN** a propagated diff invalidates a parent review that exceeds the
  configured large-model threshold
- **THEN** the review uses ModelMesh split decisions or Budgeted model-group
  execution and reports incomplete shards as incomplete evidence

#### Scenario: Propagation check runs as a long check
- **WHEN** an affected propagation check is run in the background or exceeds the
  local long-check threshold
- **THEN** final evidence names the LongCheck log artifacts, exit code, last
  update time, and proof-reuse status before pass or fail is claimed

#### Scenario: Incomplete budgeted propagation evidence
- **WHEN** a budgeted propagation run stops with pending states or missing
  required labels
- **THEN** the propagation result is incomplete and cannot support a green
  release-readiness claim
