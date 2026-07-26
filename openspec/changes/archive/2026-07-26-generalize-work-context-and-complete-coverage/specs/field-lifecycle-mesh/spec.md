## ADDED Requirements

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
