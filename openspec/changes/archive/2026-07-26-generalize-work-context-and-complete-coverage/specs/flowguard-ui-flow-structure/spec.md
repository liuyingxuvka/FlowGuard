## ADDED Requirements

### Requirement: UI Flow Structure projects one current observed inventory into shared coverage
UI Flow Structure SHALL publish one immutable shared-coverage projection for the current observed UI inventory. The projection SHALL bind the observed inventory identity, revision, fingerprint, runnable build or source identity, and every current visible control, input, display, status surface, native trigger, and visible command by stable identity. Each item SHALL carry or reference exactly one disposition of `modeled`, `delegated`, or `scoped`, while UI Flow Structure remains the native owner of UI classification.

#### Scenario: An observed control is absent from shared coverage
- **WHEN** a current observed control or visible command is missing from the UI shared-coverage projection
- **THEN** UI completeness and broad behavior coverage SHALL remain blocked and SHALL identify the missing observed item

#### Scenario: The behavior ledger consumes a UI projection
- **WHEN** the Behavior Commitment Ledger reconciles the current UI projection
- **THEN** it SHALL consume the UI identities, dispositions, and typed relations without reclassifying visible content, interaction behavior, or UI ownership

### Requirement: UI completeness joins capabilities, journeys, surfaces, and blindspots
UI coverage SHALL reconcile the exact current sets of user-visible capabilities, launch-to-terminal journeys, screens and regions, controls and inputs, displays and status surfaces, overlays and menus, recovery branches, and declared blindspots. A controls-only, model-only, or happy-path-only inventory SHALL NOT support product-wide UI completeness.

#### Scenario: Controls are covered but a recovery journey is missing
- **WHEN** every visible control maps to a model but an observed error or recovery journey has no owner or disposition
- **THEN** UI completeness SHALL remain blocked and SHALL identify the missing journey branch

#### Scenario: A model describes an unobserved UI item
- **WHEN** a UI model claims a visible control or display that is absent from the current observed inventory
- **THEN** the mismatch SHALL remain visible as a model-to-observation gap instead of being counted as implemented coverage

### Requirement: UI projection freshness follows the observed runnable surface
The UI shared-coverage projection SHALL be current only for the exact observed build or source identity and UI inventory fingerprint. A change to a visible item, journey, layout-owned interaction, recovery path, blindspot, or field-bound UI candidate SHALL invalidate the affected projection and downstream behavior or test evidence.

#### Scenario: The runnable UI changes after observation
- **WHEN** a control, display, command, or journey changes after the inventory was observed
- **THEN** the previous UI projection SHALL become stale and SHALL NOT support a current completeness claim

### Requirement: Field-origin UI candidates use typed identity-preserving handoff
UI Flow Structure SHALL accept field-origin UI candidates through a typed handoff from FieldLifecycleMesh and SHALL preserve the stable field identity in the UI inventory. It SHALL separately classify whether the candidate is rendered, user-on-demand, internal, absent by design, or a real UI gap.

#### Scenario: A field candidate is intentionally internal
- **WHEN** a FieldLifecycleMesh candidate reaches the UI boundary but policy keeps it internal
- **THEN** UI Flow Structure SHALL record an explicit scoped disposition and SHALL NOT render the field merely to satisfy mechanical coverage

#### Scenario: A user-visible field candidate is absent
- **WHEN** a behavior-bearing field is declared user-visible but no current control, display, or on-demand path exposes it
- **THEN** UI Flow Structure SHALL record a visible coverage gap and route it to the existing UI owner
