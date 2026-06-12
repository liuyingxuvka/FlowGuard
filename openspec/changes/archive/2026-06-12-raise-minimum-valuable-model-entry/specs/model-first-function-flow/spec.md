## ADDED Requirements

### Requirement: model-first-function-flow teaches minimum valuable entry
The model-first-function-flow guidance SHALL teach a minimum valuable model
entry instead of a thin default path for non-trivial model creation and model
deepening work.

#### Scenario: Skill guidance names minimum valuable model
- **WHEN** an agent reads the model-first-function-flow skill
- **THEN** the default entry guidance requires a protected error class, modeled state, side effects, completion evidence, and a known-bad case

#### Scenario: Thin entry no longer controls default wording
- **WHEN** docs or installed skill guidance describe the default model-first path
- **THEN** they use minimum valuable model language and do not present a thin happy-path model as sufficient

### Requirement: model-first-function-flow routes template search and harvest
The model-first-function-flow guidance SHALL route new or deepened model work
through public/local template search before modeling and local candidate harvest
after reusable successful modeling.

#### Scenario: Search before modeling
- **WHEN** an agent starts a new or materially deepened model
- **THEN** the guidance requires public and local template search or an explicit scoped skip

#### Scenario: Harvest after reusable modeling
- **WHEN** a completed model introduces a reusable protected error class and known-bad case
- **THEN** the guidance instructs the agent to save or report a local candidate template
