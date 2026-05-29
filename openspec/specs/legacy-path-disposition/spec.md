# legacy-path-disposition Specification

## Purpose
TBD - created by archiving change require-proof-artifact-bound-evidence. Update Purpose after archive.
## Requirements
### Requirement: Legacy path disposition
FlowGuard SHALL represent the disposition of old or alternate paths during
model-miss closure as one of deleted, blocked, delegated to the repaired path,
same-contract repaired, explicitly out of scope, or unknown.
Architecture Reduction compatibility-surface classification MAY inform which
old paths need disposition, but it SHALL NOT replace post-repair disposition or
proof-artifact requirements.

#### Scenario: Old path is still unknown
- **WHEN** a model miss repair proves a new child path but an old in-scope path
  has missing or unknown disposition
- **THEN** strict model-miss closure SHALL remain blocked

#### Scenario: Architecture Reduction classification does not close old path
- **WHEN** Architecture Reduction classifies a surface as boundary adapter,
  prune candidate, archive-only, or evidence-needed
- **AND** that surface remains an executable old path in a repair closure claim
- **THEN** strict closure still requires a LegacyPathDisposition result for the
  old path

### Requirement: Parent route coverage includes old paths
FlowGuard SHALL require parent route coverage to include fresh, resume, replay,
old-state, and peer/adapter ingress paths that can reach a repaired or legacy
child boundary.

#### Scenario: Parent coverage omits a reachable old ingress
- **WHEN** a repaired child path has proof but parent route coverage omits a
  reachable legacy or replay ingress
- **THEN** strict parent confidence SHALL report a parent coverage gap
