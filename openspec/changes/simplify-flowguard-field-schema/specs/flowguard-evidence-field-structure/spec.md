## ADDED Requirements

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
Historical, compatibility, fallback, and old-path fields SHALL appear only in
routes that explicitly own migration or legacy disposition. Normal route input
schemas MUST NOT expose those fields as ordinary optional fields.

#### Scenario: Normal model input
- **WHEN** an agent creates a normal field-bearing route plan
- **THEN** it is not asked to fill compatibility-preserved, old-path, fallback,
  or generic legacy fields

## REMOVED Requirements

### Requirement: Compatibility Fields In Normal Schemas
**Reason**: Compatibility fields spread old-path cleanup concerns into ordinary
routes and keep obsolete fields alive.

**Migration**: Use Legacy Path Disposition, Architecture Reduction, or
FieldLifecycleMesh disposition rows when old-path evidence is actually needed.
