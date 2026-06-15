## MODIFIED Requirements

### Requirement: model-first-function-flow teaches minimum valuable entry
The model-first-function-flow guidance SHALL teach one formal minimum valuable model entry instead of a direct `Explorer(...)`, optional runner, fallback, or thin default path for non-trivial model creation and model deepening work.

#### Scenario: Skill guidance names minimum valuable model
- **WHEN** an agent reads the model-first-function-flow skill
- **THEN** the default entry guidance requires a protected error class, modeled state, side effects, completion evidence, a known-bad case, and executable proof that the known-bad case is caught

#### Scenario: Thin entry no longer controls default wording
- **WHEN** docs or installed skill guidance describe the default model-first path
- **THEN** they use minimum valuable model language and do not present a thin happy-path model or direct Explorer run as sufficient

#### Scenario: Fallback language is absent
- **WHEN** model-first guidance describes FlowGuard entry choices
- **THEN** it MUST NOT present direct Explorer, fallback explorers, local mini-frameworks, or compatibility routes as acceptable FlowGuard entry paths

### Requirement: model-first-function-flow routes template search and harvest
The model-first-function-flow guidance SHALL route new or deepened model work through public/local template search before modeling and local candidate harvest after reusable successful modeling.

#### Scenario: Search before modeling
- **WHEN** an agent starts a new or materially deepened model
- **THEN** the guidance requires public and local template search or an explicit no-match reason

#### Scenario: Harvest after reusable modeling
- **WHEN** a completed model introduces a reusable protected error class and known-bad case
- **THEN** the guidance instructs the agent to save, merge, duplicate-link, or record accepted not-harvestable template closure

#### Scenario: Formal runner is the route
- **WHEN** the guidance instructs an agent to run a new or deepened model
- **THEN** it MUST use the formal check plan path rather than direct Explorer as the route
