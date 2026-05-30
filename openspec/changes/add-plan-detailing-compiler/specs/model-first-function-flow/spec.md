## ADDED Requirements

### Requirement: Model-first routing begins with plan detailing for vague non-trivial work
The model-first-function-flow guidance SHALL route vague or under-specified non-trivial work through plan detailing before behavior modeling.

#### Scenario: Vague request uses plan detail first
- **WHEN** an agent receives a non-trivial request with only a rough idea or short plan
- **THEN** the model-first guidance directs the agent to create or review plan-detail rows before writing the core `Input x State -> Set(Output x State)` model

#### Scenario: Existing detailed plan can proceed directly
- **WHEN** the request already includes current structured plan-detail evidence
- **THEN** the model-first guidance may consume that evidence and continue to the smallest owning FlowGuard route

### Requirement: Model claims preserve plan-detail scope
The model-first-function-flow guidance SHALL preserve plan-detail scoped, missing, or human-review findings as model confidence boundaries.

#### Scenario: Plan detail is scoped
- **WHEN** plan-detail review reports scoped confidence
- **THEN** the model-first result cannot claim broader completion confidence until the scoped gap is closed by downstream evidence
