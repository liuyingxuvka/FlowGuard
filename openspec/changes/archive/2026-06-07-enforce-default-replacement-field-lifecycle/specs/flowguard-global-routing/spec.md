## ADDED Requirements

### Requirement: Replacement defaults to disposition
FlowGuard global routing SHALL treat feature replacement, route migration,
field migration, prompt externalization, or compatibility cleanup as requiring
old-path and old-field disposition unless explicit compatibility intent is
declared.

#### Scenario: Replacement has no compatibility intent
- **WHEN** a user asks for a new path to replace old behavior
- **AND** the user does not explicitly request compatibility preservation
- **THEN** FlowGuard routing MUST require disposition evidence for old runtime
  paths, old fields, old tests, old prompt/config surfaces, and old public
  entrypoints before full done confidence

#### Scenario: Compatibility is explicit
- **WHEN** compatibility preservation is declared for a public API, old data,
  old schema, or external integration
- **THEN** FlowGuard routing MUST keep that compatibility surface visible and
  route it through the owner route for parity, migration, or rejection evidence
