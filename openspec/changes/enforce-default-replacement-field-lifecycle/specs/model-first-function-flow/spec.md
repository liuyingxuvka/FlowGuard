## ADDED Requirements

### Requirement: Model-first checks consume field lifecycle boundaries
Model-first FlowGuard guidance SHALL surface field lifecycle coverage when a
model's state, input, output, schema, mode, or side-effect behavior depends on
software fields.

#### Scenario: Behavior field is missing from the model
- **WHEN** a field lifecycle row marks a field as behavior-bearing
- **AND** no model obligation, transition cell, state closure dimension, or
  scoped-out reason covers it
- **THEN** model-first review MUST report a model maturation gap before broad
  confidence

#### Scenario: Leaf field remains below the main model
- **WHEN** a field is fully accounted in a field lifecycle leaf row and has no
  behavior impact
- **THEN** model-first review MAY leave it outside the high-level state machine
  while keeping the scoped-out reason visible
