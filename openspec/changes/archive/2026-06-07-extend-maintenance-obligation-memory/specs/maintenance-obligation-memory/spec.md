## ADDED Requirements

### Requirement: FlowGuard records anchored open maintenance obligations
FlowGuard SHALL represent unresolved route-owned maintenance work as anchored
obligation records that can be carried between normal FlowGuard runs.

#### Scenario: Anchored finding becomes obligation
- **WHEN** a FlowGuard report exposes an unresolved structure, evidence,
  model-maturation, skipped-route, state-closure, or topology-hazard gap with a
  concrete model, code, test, artifact, symbol, or public-entrypoint anchor
- **THEN** FlowGuard MUST be able to represent that gap as an open maintenance
  obligation
- **AND** the obligation MUST name the existing owner route that can resolve it

#### Scenario: Unanchored observation is not an active obligation
- **WHEN** a report contains a generic or unanchored AI concern
- **THEN** FlowGuard MUST NOT promote that concern to an active blocking
  maintenance obligation
- **AND** the concern MAY remain visible as an observation or scoped note

### Requirement: Obligations preserve owner route and current status
FlowGuard SHALL preserve each obligation's source route, required owner route,
reason code, strength, status, anchor, and evidence references.

#### Scenario: Open obligation preserves route ownership
- **WHEN** an architecture reduction candidate lacks proof, a StructureMesh
  public-entrypoint parity gap remains, or a model maturation signal is open
- **THEN** the obligation MUST keep the corresponding owner route visible
- **AND** the obligation MUST NOT claim that route has passed

#### Scenario: Resolved obligation requires evidence
- **WHEN** an obligation is marked resolved
- **THEN** it MUST reference current owner-route evidence or an explicit scoped
  disposition
- **AND** broad confidence MUST NOT treat a resolved label alone as proof

### Requirement: Obligation memory remains a helper over existing routes
FlowGuard SHALL treat maintenance obligation memory as a helper data contract,
not as a standalone validation route or technical-debt scanner.

#### Scenario: Memory does not replace owner route
- **WHEN** maintenance obligation memory reopens an obligation for a touched
  artifact
- **THEN** the owning FlowGuard route MUST still produce the evidence required
  for resolution
- **AND** the memory helper MUST NOT refactor code, split models, run tests, or
  certify behavior by itself

