## ADDED Requirements

### Requirement: Skill hot path enforces harvest closure
The FlowGuard skill kernel SHALL state that template harvest closure is required
after any new or materially deepened model while keeping detailed template
catalogs out of the hot path.

#### Scenario: Agent reads model-first hot path
- **WHEN** an agent reads the model-first kernel or reusable AGENTS snippet
- **THEN** the minimum workflow includes harvest closure as written, merged, duplicate-linked, or not-harvestable with an accepted reason
- **AND** it does not embed long public or local template catalogs

#### Scenario: Satellite route bypass is prevented
- **WHEN** a directly routed satellite skill creates or deepens a model
- **THEN** its first-read guidance also requires template harvest closure before broad completion claims
