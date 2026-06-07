## MODIFIED Requirements

### Requirement: AI-facing field prompts are grouped
FlowGuard field inventory and prompt guidance SHALL distinguish starter,
advanced, and internal field exposure so AI agents do not treat all discovered
fields as default authoring fields.

#### Scenario: Inventory exposes AI surface tier
- **WHEN** the field lifecycle inventory is regenerated
- **THEN** each row includes an AI surface tier suitable for starter,
  advanced, or internal routing decisions

#### Scenario: Tiering does not delete fields by itself
- **WHEN** a field is classified as advanced or internal
- **THEN** the inventory does not claim the field is removable without owner,
  reader, writer, lifecycle, and test-binding evidence
