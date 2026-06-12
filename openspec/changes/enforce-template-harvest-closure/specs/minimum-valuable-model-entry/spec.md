## MODIFIED Requirements

### Requirement: Template reuse review is part of model creation
The minimum valuable model path SHALL perform a template reuse review before
model generation, preserve the result in the check plan or adoption evidence,
and complete with a harvest closure review after new or materially deepened
modeling.

#### Scenario: Template was used
- **WHEN** a matching public or local template is used
- **THEN** the model intent or check plan records the used template id

#### Scenario: Template was not used
- **WHEN** no matching template is used
- **THEN** the model intent or check plan records a no-match reason

#### Scenario: Model closes harvest loop
- **WHEN** an AI creates or materially deepens a minimum valuable model
- **THEN** the check plan or adoption evidence records template harvest closure as written, merged, duplicate-linked, or not-harvestable with an accepted reason
