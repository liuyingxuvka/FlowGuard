## ADDED Requirements

### Requirement: Runnable UI proves content admission behavior
UI Implementation Validation SHALL bind the current content-visibility plan to the implementation revision and a current observed-surface inventory. It SHALL provide structured per-content evidence rows that prove default-visible content is admitted, on-demand content is hidden, explicitly revealed, observed in the reveal target, and returned to hidden, and internal content is absent from the ordinary observed UI. A boolean review flag or one opaque evidence reference SHALL NOT satisfy this requirement.

#### Scenario: Runtime evidence proves default hidden and reveal
- **WHEN** a runnable UI claim includes `user_on_demand` content
- **THEN** current screenshot, DOM, desktop/manual observation, test, or equivalent evidence records the closed state, reveal event and revealed state, and return to the closed state

#### Scenario: Internal content appears in observed UI
- **WHEN** the current implementation renders content classified `internal` on an ordinary user surface
- **THEN** implementation validation blocks runnable, complete, usable, and release-ready UI claims

#### Scenario: Visibility evidence is stale
- **WHEN** the content-visibility plan, UI model, or implementation revision changes after the evidence was produced
- **THEN** the visibility evidence is stale and MUST be rerun before it supports completion

#### Scenario: One opaque evidence reference claims the whole boundary
- **WHEN** implementation validation supplies no per-content phase rows or no observed inventory
- **THEN** validation blocks the runnable UI claim even when the opaque reference is non-empty

#### Scenario: A content row cites another content item's observation
- **WHEN** default-visible or revealed evidence for one content item points only to an observed item for different content or a different UI state
- **THEN** validation rejects the row instead of treating the unrelated observation as per-content proof
