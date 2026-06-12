## ADDED Requirements

### Requirement: Template harvest closure is mandatory after reusable modeling
FlowGuard SHALL require a template harvest closure review after any new or
materially deepened model before broad FlowGuard completion confidence.

#### Scenario: New model writes reusable candidate
- **WHEN** a new model exposes a reusable protected error class with state or side effects, completion evidence, and a known-bad case
- **THEN** the harvest closure review records disposition `written` and the written local template id

#### Scenario: Deepened model strengthens existing template
- **WHEN** a materially deepened model adds a known-bad case, required evidence, or state/side-effect requirement to an existing reusable risk pattern
- **THEN** the harvest closure review records disposition `merged` and the affected template id

#### Scenario: Existing template already covers the model
- **WHEN** public or local template search finds a template that already covers the new or deepened model pattern
- **THEN** the harvest closure review may record disposition `duplicate_linked` with the linked template id instead of writing a duplicate local card

#### Scenario: Harvest is skipped with accepted reason
- **WHEN** a model is not reusable enough to harvest
- **THEN** the harvest closure review records disposition `not_harvestable` and one accepted reason

#### Scenario: Missing closure is a gap
- **WHEN** a new or deepened model has no harvest closure review
- **THEN** FlowGuard reports a template harvest closure gap before broad completion confidence

### Requirement: Not-harvestable reasons are bounded
FlowGuard SHALL accept only concrete not-harvestable reasons so agents cannot
replace harvest closure with vague prose.

#### Scenario: Vague skip reason is rejected
- **WHEN** a harvest closure review uses `not_harvestable` without an accepted reason
- **THEN** FlowGuard reports an unsupported or missing not-harvestable reason

#### Scenario: Human deferral remains explicit
- **WHEN** the user explicitly asks not to write a local candidate template
- **THEN** FlowGuard may record `human_deferred` as the not-harvestable reason
