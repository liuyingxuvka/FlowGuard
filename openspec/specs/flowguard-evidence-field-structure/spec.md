# flowguard-evidence-field-structure Specification

## Purpose

Define one direct-current lightweight evidence schema whose removed,
historical, fixture-only, and route-specific fields remain outside ordinary
runtime constructors.
## Requirements
### Requirement: Lightweight evidence gate structures
FlowGuard SHALL provide one current lightweight evidence gate and detail shape
for broad evidence models. Duplicate legacy input concepts, removed flat gate
fields, old AutoSplit process metrics, standalone analogous-scan gate fields,
and strict-adapter fixture-only fields MUST be rejected by current constructors
and APIs rather than converted, defaulted, aliased, or accepted as a second
success path.

#### Scenario: Risk evidence gates can be grouped
- **WHEN** a risk evidence row needs model, test, finite same-class,
  canonical-maturation, or contract-exhaustion gate state
- **THEN** that state is represented by the current reusable gate object and
  bound to the current native owner evidence
- **AND** removed flat or analogous-scan gate fields are rejected

#### Scenario: Process evidence details can be grouped
- **WHEN** process evidence includes command status, background status, or mesh
  split status
- **THEN** that state is represented by the focused current detail object and
  old AutoSplit metrics are rejected

#### Scenario: Strict adapter fixture fields reach a public constructor
- **WHEN** a test-owned strict-adapter fixture field is supplied to the current
  plan-intake or evidence API
- **THEN** validation rejects it instead of retaining production compatibility

### Requirement: Field Schemas Remove Duplicate Input Concepts
FlowGuard field-bearing dataclasses SHALL avoid duplicate same-shape helper
classes and duplicate input fields when one canonical class or field captures
the same concept.

#### Scenario: Duplicate helper class shape
- **WHEN** two helper classes have the same fields and represent the same
  concept
- **THEN** the system exposes one canonical class instead of two public input
  classes

### Requirement: Historical Fields Stay In Dedicated Routes
Historical, migration, fallback, and old-path fields SHALL appear only in
routes that explicitly own their disposition. Normal current route input
schemas MUST NOT expose those fields as ordinary optional fields.

#### Scenario: Normal model input
- **WHEN** an agent creates a normal field-bearing route plan
- **THEN** it is not asked to fill compatibility-preserved, old-path,
  fallback, or generic legacy fields

### Requirement: Compatibility conversion is explicit
Current runtime SHALL reject compatibility conversion for removed evidence
fields. Historical artifacts MAY be inspected only by an explicit bounded
upgrade owner; ordinary constructors, APIs, and route logic MUST NOT convert,
default, alias, or accept the retired shape.

#### Scenario: Removed field reaches current runtime
- **WHEN** a caller supplies a retired evidence field to a current constructor
- **THEN** the constructor rejects it visibly and exposes no compatibility
  success path
