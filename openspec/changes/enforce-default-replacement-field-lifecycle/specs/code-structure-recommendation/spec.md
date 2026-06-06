## ADDED Requirements

### Requirement: Code structure consumes field owners
Code Structure Recommendation SHALL consume field lifecycle reader, writer,
owner, public-entrypoint, and validation-boundary rows when deriving target
modules or facades.

#### Scenario: Field writer owner is missing
- **WHEN** a behavior-bearing field has writes in scope
- **AND** no target code owner or validation boundary owns those writes
- **THEN** Code Structure Recommendation MUST report an owner gap instead of
  recommending implementation structure as complete

#### Scenario: Field facade is required
- **WHEN** old field access must be delegated to a new field or new path for
  public compatibility
- **THEN** the target structure recommendation MUST expose the facade or
  adapter boundary and route public-entrypoint parity to StructureMesh when
  required
