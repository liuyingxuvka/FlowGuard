# field-lifecycle-mesh Specification

## Purpose
This capability defines how FlowGuard accounts for fields by owner, reader, writer, projection, lifecycle, and replacement disposition before adding, folding, or removing field-bearing surfaces.
## Requirements
### Requirement: Complete field lifecycle inventory
FlowGuard SHALL provide a field lifecycle mesh that records every discovered
field at leaf level while allowing parent group summaries by entity, payload,
schema, config, public entrypoint, or prompt/config surface.

#### Scenario: All discovered fields are accounted
- **WHEN** a field lifecycle mesh declares discovered fields for an in-scope
  boundary
- **THEN** every discovered field MUST have a leaf row with field id, location,
  owner group, field role, lifecycle status, behavior impact, reader ids,
  writer ids, and evidence status

#### Scenario: Missing field row blocks full coverage
- **WHEN** a discovered in-scope field has no leaf row
- **THEN** the field lifecycle review MUST report a missing field coverage
  finding and MUST NOT allow full field lifecycle confidence

### Requirement: Behavior-bearing fields project to model obligations
The field lifecycle mesh SHALL project behavior-bearing fields into model,
transition, code, and test obligations consumed by existing FlowGuard routes.

#### Scenario: Behavior field creates projection
- **WHEN** a field affects routing, permission, state, mode, schema version,
  feature flags, replay, migration, side effects, error behavior, or external
  outputs
- **THEN** the field lifecycle review MUST require a projection to a model
  obligation, transition coverage cell, code contract, or explicit scoped-out
  reason

#### Scenario: Non-behavior field stays accounted
- **WHEN** a field is display-only, log-only, metadata-only, or otherwise
  non-behavioral
- **THEN** the field lifecycle mesh MAY keep it out of the high-level behavior
  model only when the leaf row records a scoped-out reason

### Requirement: Field lifecycle captures replacement and disposition
The field lifecycle mesh SHALL represent old, replacement, derived, persisted,
and explicitly preserved fields with current disposition before replacement
work can claim completion.

#### Scenario: Old field disposition is unknown
- **WHEN** a field is marked old, replaced, deprecated, or compatibility-like
- **AND** the field disposition is unknown
- **THEN** full replacement confidence MUST be blocked

#### Scenario: Explicit compatibility is preserved
- **WHEN** a field remains for public compatibility, old data migration, or
  archive authority
- **THEN** the field row MUST record compatibility intent, evidence refs, and
  the owner route that keeps the compatibility surface current

### Requirement: Field lifecycle reports route handoffs
The field lifecycle review SHALL report structured owner-route handoffs for
missing projections, old-field disposition gaps, code-owner gaps, test-evidence
gaps, oversized field groups, and stale field evidence.

#### Scenario: Missing field test routes to Model-Test Alignment
- **WHEN** a behavior-bearing field has a model projection and code owner but
  no current external-contract test evidence
- **THEN** the field lifecycle report MUST include a `model_test_alignment`
  handoff with the missing field obligation id

#### Scenario: Field group is too large
- **WHEN** a field group is too large or layered for one leaf review
- **THEN** the report MUST route the split need to ModelMesh or TestMesh
  instead of treating the field lifecycle mesh as an all-in-one runner

### Requirement: Generated field lifecycle inventory
FlowGuard SHALL provide a generated field inventory that lists dataclass fields with module owner, class owner, field name, inferred lifecycle layer, and behavior-bearing hints before field deletion or folding decisions are made.

#### Scenario: Field-bearing module is audited
- **WHEN** the field inventory generator scans FlowGuard modules
- **THEN** the generated report includes field rows grouped by module and lifecycle layer

#### Scenario: Field cleanup is proposed
- **WHEN** a future maintenance task proposes removing fields
- **THEN** the field inventory is current or the task records why field inventory evidence is scoped out

### Requirement: Broad field claims expose evidence route refs
FieldLifecycleMesh SHALL require behavior-bearing field projections to expose
minimal evidence route references when the field lifecycle plan claims full,
runtime, release, production, or closure confidence.

#### Scenario: Broad behavior field has route refs
- **WHEN** a broad field lifecycle plan contains a behavior-bearing field
  projection
- **AND** the projection includes gate, required test, and required replay
  references in `evidence_refs`
- **THEN** FieldLifecycleMesh SHALL allow the field route evidence requirement
  to pass for that projection

#### Scenario: Bounded behavior field remains lightweight
- **WHEN** a bounded field lifecycle plan contains a behavior-bearing field
  projection
- **AND** the projection has no route evidence refs
- **THEN** FieldLifecycleMesh SHALL keep existing bounded behavior and SHALL NOT
  require runtime-style evidence route references

### Requirement: Missing field route refs block broad confidence
FieldLifecycleMesh SHALL report blockers for missing route references that are
required by a broad behavior-bearing field projection.

#### Scenario: Missing gate ref blocks broad claim
- **WHEN** a broad field lifecycle plan contains a behavior-bearing projection
- **AND** the projection lacks a gate reference
- **THEN** FieldLifecycleMesh SHALL report a `field_gate_evidence_missing`
  blocker

#### Scenario: Missing negative test ref blocks broad claim
- **WHEN** a broad field lifecycle plan contains a behavior-bearing projection
- **AND** the projection requires `failure_path` or `negative_path` evidence
- **AND** the projection lacks a test reference
- **THEN** FieldLifecycleMesh SHALL report a
  `field_negative_test_evidence_missing` blocker

#### Scenario: Missing replay ref blocks broad claim
- **WHEN** a broad field lifecycle plan contains a behavior-bearing projection
- **AND** the projection requires replay evidence or the field has replay
  behavior impact
- **AND** the projection lacks a replay reference
- **THEN** FieldLifecycleMesh SHALL report a
  `field_replay_evidence_missing` blocker

### Requirement: Field route refs remain handoffs
FieldLifecycleMesh SHALL treat evidence route references as handoffs to the
owning proof routes rather than replacing those proof routes.

#### Scenario: Route refs do not replace model-test alignment
- **WHEN** a broad behavior field projection includes route references
- **THEN** FieldLifecycleMesh SHALL still project the field to model
  obligations and code contracts for Model-Test Alignment
- **AND** the route refs alone SHALL NOT prove current passing test evidence

#### Scenario: Route refs do not replace runtime gateway adoption
- **WHEN** a broad behavior field projection includes a gate reference
- **THEN** FieldLifecycleMesh SHALL treat that reference as a runtime or
  boundary handoff
- **AND** runtime-gateway confidence SHALL still require Runtime Gateway
  Adoption evidence when the claim depends on production state mutation

### Requirement: Behavior fields project contract-exhaustion dimensions
FlowGuard MUST allow behavior-bearing field lifecycle rows and old-field
disposition rows to project declared contract-exhaustion dimensions.

#### Scenario: Required behavior field projects missing-field mutation
- **WHEN** a field lifecycle row marks a field as behavior-bearing and required
- **THEN** FlowGuard can project that row into a contract dimension that
  generates missing, empty, wrong-type, or unknown-value mutation cases

#### Scenario: Old field disposition projects legacy mutation
- **WHEN** an old, replaced, alias, fallback, or compatibility-like field
  remains reachable
- **THEN** FlowGuard records its disposition and can project legacy-field
  mutation cases or cleanup blockers into ContractExhaustionMesh

### Requirement: UI-boundary fields hand off to content admission
FieldLifecycleMesh SHALL keep every discovered field in the leaf inventory and SHALL hand every field or grouped field id whose reader reaches an ordinary UI adapter, view model, display, text, or output boundary to UI Flow Structure as UI candidate content, regardless of whether the source field role is presentation, metadata, state, permission, or another role. FieldLifecycleMesh SHALL NOT decide the final UI visibility class and SHALL NOT require fields with no ordinary-UI reader to enter the UI content plan.

#### Scenario: Field reaches the UI boundary
- **WHEN** any field has a reader that can place its value or state on an ordinary user surface
- **THEN** the field lifecycle handoff names the field or field group as UI candidate content for UI Flow Structure classification

#### Scenario: Internal field has no UI reader
- **WHEN** an internal audit, model, test, or diagnostic field remains outside the UI adapter/view-model/output boundary
- **THEN** FieldLifecycleMesh keeps it accounted internally without creating a UI content-admission row

### Requirement: Field lifecycle rejects hidden fallback fields
FieldLifecycleMesh SHALL classify old, renamed, alias, compatibility, backup,
and migration fields that can replace a primary field after failure.

#### Scenario: Old field fallback blocks
- **WHEN** a new primary field is missing or invalid and code reads an old
  field to return success for the same business intent
- **THEN** FieldLifecycleMesh SHALL report a hidden fallback field gap

#### Scenario: Migration field has closing disposition
- **WHEN** a migration-only field remains
- **THEN** FieldLifecycleMesh SHALL require owner, readers, writers,
  projection, lifecycle, evidence, and closing disposition

### Requirement: Field and side-effect changes join the revision set
FieldLifecycleMesh SHALL require every added, changed, replaced, removed,
externalized, or compensated behavior-bearing field or side effect in the owning model
revision set and bound to its base and candidate snapshots.

#### Scenario: Two models share a replaced field
- **WHEN** a revision changes a field written by one model and read by another
- **THEN** both model owners, the field lifecycle row, migration disposition, and affected tests close in the same revision set

#### Scenario: Member passes but field migration is incomplete
- **WHEN** all candidate model checks pass but an old field remains an undeclared successful reader or writer
- **THEN** revision-set activation is blocked

### Requirement: FieldLifecycleMesh projects its complete leaf inventory into shared coverage
FieldLifecycleMesh SHALL publish one immutable shared-coverage projection for its current complete leaf-field inventory. The projection SHALL bind the native field inventory identity, revision, fingerprint, and every discovered leaf field identity exactly once. Each projected field SHALL preserve its native lifecycle owner and behavior-impact classification and SHALL carry or reference exactly one shared disposition of `modeled`, `delegated`, or `scoped`.

#### Scenario: A discovered leaf field is absent from the projection
- **WHEN** the current native field inventory contains a leaf field that is missing from the shared-coverage projection
- **THEN** field completeness and broad behavior coverage SHALL remain blocked and SHALL identify the omitted field

#### Scenario: The ledger consumes a field projection
- **WHEN** the Behavior Commitment Ledger reconciles a FieldLifecycleMesh projection
- **THEN** it SHALL consume stable item identities and dispositions without replacing FieldLifecycleMesh as the owner of field semantics, lifecycle, readers, writers, or behavior impact

### Requirement: UI-bound fields preserve one identity across owner projections
A field that crosses a UI boundary SHALL retain one stable field identity across the FieldLifecycleMesh inventory, the UI candidate or observed inventory, and the shared behavior reconciliation. The handoff SHALL use typed relations and SHALL NOT create a second field identity or a duplicate Behavior Commitment merely because the field appears in a UI control or display.

#### Scenario: A field is rendered and edited in the UI
- **WHEN** one behavior-bearing field is both displayed and written through a UI surface
- **THEN** the field and UI projections SHALL reference the same stable field identity while preserving separate field-lifecycle and UI-flow ownership

#### Scenario: A field has no UI representation
- **WHEN** a discovered field is internal, file-bound, API-bound, or otherwise not represented in the UI
- **THEN** it SHALL remain in the complete field inventory with an explicit modeled, delegated, or scoped disposition rather than disappearing from shared coverage

### Requirement: Field coverage projections are freshness-bound
The shared field projection SHALL be current only for its exact native inventory revision and fingerprint. Changes to the leaf set, stable identity, reader, writer, projection path, lifecycle state, old-field disposition, or behavior-impact classification SHALL invalidate the affected shared reconciliation and downstream evidence.

#### Scenario: A writer is added after coverage reconciliation
- **WHEN** a new writer or projection path is discovered for a previously reconciled field
- **THEN** the field projection fingerprint SHALL change and the affected coverage and evidence claims SHALL become stale

### Requirement: Behavior-plane upgrade fields are fully accounted
FieldLifecycleMesh SHALL account the new BCL plane, actor-kind, relation, lookup-binding, canonical-ledger, preflight lookup, similarity plane, and Model Miss identity fields with owners, readers, writers, projections, lifecycle, and evidence handoffs.

#### Scenario: BCL schema fields have one owner
- **WHEN** the behavior commitment schema is upgraded
- **THEN** each added field SHALL have one field owner and identified readers/writers
- **AND** behavior-bearing fields SHALL project to Model-Test Alignment and ContractExhaustionMesh

#### Scenario: Prompt fields are updated
- **WHEN** affected skill prompts or contract sources add plane-selection instructions
- **THEN** the prompt/config field inventory SHALL record canonical source, generated projection, installed projection, and freshness owner

### Requirement: Legacy dependency field has a closing disposition
`dependency_commitment_ids` SHALL be classified as a replaced runtime field with boundary-only migration and no continuing runtime fallback.

#### Scenario: Runtime object still accepts legacy dependency
- **WHEN** normal post-upgrade runtime construction accepts `dependency_commitment_ids` as a successful relationship authority
- **THEN** FieldLifecycleMesh SHALL report an open replacement-disposition blocker

#### Scenario: Upgrader reads legacy field
- **WHEN** the artifact upgrader reads the old field to create typed relations
- **THEN** the field MAY remain visible only as migration input with owner, evidence, and closing disposition

### Requirement: Migration diagnostic fields cannot masquerade as production state
Migration-only fields such as `unclassified` plane status and manual-conversion reason SHALL remain upgrade-report fields and SHALL NOT become accepted production commitment values.

#### Scenario: Unclassified row reaches runtime ledger
- **WHEN** a canonical runtime ledger contains a migration-only unclassified value
- **THEN** field lifecycle and ledger review SHALL block broad confidence
