## MODIFIED Requirements

### Requirement: Revision-set diffs are complete and fingerprinted
Before validation or activation, the system SHALL independently derive the
actual change set by comparing the exact base and candidate snapshots, their
source-surface inventories, and every referenced native-owner artifact
inventory. The derived set SHALL include added, removed, or fingerprint-changed
model members, relations, behavior commitments, source surfaces, fields,
state, side effects, system properties, code contracts, tests, evidence, and
owner artifacts. Caller-declared changed ids SHALL be treated as assertions
that must exactly reconcile with the derived set and SHALL NOT narrow or
replace it. Unchanged members and bindings SHALL retain their exact identities.

#### Scenario: An undeclared sibling changes
- **WHEN** a candidate snapshot changes a sibling model, relation, input, or
  owner-artifact fingerprint that the revision set did not declare
- **THEN** revision validation reports undeclared drift and the independently
  derived changed id
- **AND** activation is blocked

#### Scenario: A behavior source surface changes without a caller changed id
- **WHEN** a source surface is added, removed, moved, assigned a different
  role or owner, given a different disposition, or has a different content
  fingerprint between the base and candidate inventories
- **AND** the caller omits that surface from its changed-id list
- **THEN** the independently derived diff includes the source surface and its
  affected owner relations
- **AND** the declaration mismatch blocks acceptance rather than silently
  shrinking the affected boundary

#### Scenario: An owner artifact changes under a stable logical id
- **WHEN** a model, runner, purpose closure, resolved input, commitment
  ledger, field inventory, UI inventory, contract, test, or evidence-owner
  artifact keeps its logical id but changes fingerprint
- **THEN** the independently derived diff treats the owner artifact as changed
- **AND** every governed object reached through its typed ownership relations
  enters affected-closure derivation

#### Scenario: Caller declares a change that the inventories do not contain
- **WHEN** a caller-supplied changed id has no corresponding base-to-candidate
  identity or fingerprint difference
- **THEN** revision validation reports an over-declared or unresolved change
  assertion
- **AND** it does not manufacture a difference or evidence obligation to make
  the declaration pass

#### Scenario: A removal has no disposition
- **WHEN** a revision set removes an instance or governed object without an
  exact replacement, retirement, migration, or bounded out-of-scope
  disposition
- **THEN** the affected closure remains unresolved
- **AND** the revision set cannot be accepted

### Requirement: Validation closes the entire affected model system
Revision-set validation SHALL seed one dependency-closed affected slice from
the independently derived base-to-candidate diff, including every changed
source surface and owner artifact. It SHALL traverse current typed ownership,
containment, refinement, dependency, delegation, realization, validation, and
evidence relations and require the existing native owners to validate every
reached model, parent-child reattachment, sibling impact, behavior
commitment, source-surface disposition, field and side-effect lifecycle, code
contract, test obligation, and selected portable system property. Unaffected
evidence MAY be reused only when it is outside the derived closure and its
exact inputs, dependencies, tools, environment, obligations, and fingerprints
remain unchanged.

#### Scenario: Changed source surface reaches its native owners
- **WHEN** the derived diff contains a changed behavior source surface
- **THEN** affected closure includes its behavior commitment, primary owner
  model, delegated or primary path, fields, side effects, contracts, tests,
  evidence obligations, and any affected parent or sibling relations
- **AND** the surface cannot be closed by a caller assertion or ledger row
  without current evidence from those native owners

#### Scenario: Changed owner artifact expands the closure
- **WHEN** an owner-artifact fingerprint changes while the governed logical
  ids remain stable
- **THEN** affected closure follows the artifact's exact ownership and
  dependency edges to every consumer whose evidence may be stale
- **AND** revalidation is derived from those edges rather than from a
  caller-selected changed-id subset

#### Scenario: Members pass locally but joint behavior fails
- **WHEN** every changed model passes its local checks
- **AND** a required parent join, sibling interaction, shared resource, joint
  step, or system property fails
- **THEN** the aggregate revision-set validation fails
- **AND** none of its members is promoted

#### Scenario: Required replay binding does not match
- **WHEN** replay evidence names the wrong prediction id, prediction
  fingerprint, observation boundary, candidate instance, or candidate model
  fingerprint
- **THEN** that evidence does not close the revision-set obligation
- **AND** acceptance remains blocked
