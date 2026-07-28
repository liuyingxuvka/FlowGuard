## ADDED Requirements

### Requirement: UI consistency helpers extend the existing UI Flow Structure API group
FlowGuard SHALL expose product-scope UI consistency types and review helpers
through the existing `ui_flow_structure` public owner group. The helpers SHALL
remain discoverable through `UI_FLOW_STRUCTURE_ROUTE_API`,
`FLOWGUARD_ROUTE_API["ui_flow_structure"]`,
`ROUTE_ADVANCED_API["ui_flow_structure"]`, and the flat public package exports
without creating a Product Design Language or Functional Path Reuse API group.

#### Scenario: Extended UI consistency helper is exported
- **WHEN** a public UI consistency type or review helper is added for this
  change
- **THEN** its name MUST be present in `flowguard.__all__` and importable from
  `flowguard`
- **AND** it MUST be discoverable through the existing `ui_flow_structure`
  route group

#### Scenario: Starter surface remains compact
- **WHEN** the extended UI consistency API is registered
- **THEN** `ROUTE_STARTER_API["ui_flow_structure"]` MUST remain a compact direct
  entry to the existing UI Flow Structure owner
- **AND** advanced data types and helpers MUST remain available through the
  existing advanced or full UI group instead of becoming starter routes

#### Scenario: Parallel UI route is rejected
- **WHEN** API registry changes introduce a `product_design_language`,
  `functional_path_reuse`, or equivalent parallel public owner key
- **THEN** API surface and self-maintenance validation MUST report a route
  registry mismatch

### Requirement: Extended existing models preserve public compatibility
FlowGuard SHALL extend the existing UI Flow Structure, behavior identity, path
binding, transition, and evidence model families rather than publishing
replacement wrapper models. Existing public type and helper names SHALL remain
importable, and additive fields SHALL preserve existing valid construction and
serialization behavior except where this change explicitly defines the
singular primary-path migration.

#### Scenario: Existing constructor omits additive fields
- **WHEN** existing consumer code constructs an extended public model using a
  previously valid argument set that does not rely on ambiguous plural primary
  paths
- **THEN** the construction MUST remain valid with deterministic defaults for
  the additive fields

#### Scenario: Existing public import remains available
- **WHEN** a model family gains UI consistency, business-intent, path-binding,
  inventory, or evidence fields
- **THEN** its existing public class and review-helper names MUST remain in the
  flat exports and their existing route-scoped API groups

#### Scenario: Compatibility surface does not become an owner
- **WHEN** a migration adapter accepts a legacy deterministic one-item input or
  projects an extended model into an existing public shape
- **THEN** the adapter MUST delegate to the existing owner model and reviewer
- **AND** the API registry MUST NOT expose the adapter as a new route owner

### Requirement: UI consistency API adds no CLI command
The FlowGuard API registry and CLI discovery surfaces MUST keep UI consistency
review inside the existing `ui_flow_structure` route and existing commands.
This change MUST NOT add a Product Design Language, Functional Path Reuse, or
UI consistency CLI command.

#### Scenario: CLI command inventory is inspected
- **WHEN** CLI and API surface tests inspect the commands added by this change
- **THEN** no new product-language, path-reuse, or UI-consistency command name
  is present
- **AND** Python callers use the existing `ui_flow_structure` public helpers
