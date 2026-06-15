## MODIFIED Requirements

### Requirement: Local template harvest creates candidate risk cards
FlowGuard SHALL harvest a local candidate template only from reusable model evidence that includes a protected error class, required state or side effects, completion evidence, a known-bad case, and model-instance proof that the known-bad case was caught.

#### Scenario: Reusable model is saved as candidate
- **WHEN** a model run exposes a reusable risk pattern with a known-bad case, completion evidence, and current known-bad proof
- **THEN** FlowGuard can write a local candidate template card with status `candidate`

#### Scenario: Project-specific model is not harvested
- **WHEN** a model lacks a protected error class, known-bad case, executable proof, or reusable abstract terms
- **THEN** FlowGuard refuses to write a local candidate and reports the missing fields

### Requirement: Template harvest closure is mandatory after reusable modeling
FlowGuard SHALL require a template harvest closure review after any new or materially deepened model before formal FlowGuard completion confidence.

#### Scenario: New model writes reusable candidate
- **WHEN** a new model exposes a reusable protected error class with state or side effects, completion evidence, a known-bad case, and known-bad proof
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

#### Scenario: Missing closure blocks formal confidence
- **WHEN** a new or deepened formal model has no harvest closure review
- **THEN** FlowGuard reports a blocking template harvest closure gap before formal completion confidence
