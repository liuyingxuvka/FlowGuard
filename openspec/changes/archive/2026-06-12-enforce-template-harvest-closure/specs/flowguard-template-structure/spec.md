## ADDED Requirements

### Requirement: Starter templates demonstrate harvest closure
FlowGuard SHALL show a harvest closure review in public starter templates that
demonstrate risk intent, check plans, or risk-template library usage, in
addition to template search and minimum model review.

#### Scenario: Risk intent template is generated
- **WHEN** an agent generates the Risk Intent CheckPlan template
- **THEN** the example check plan includes a template harvest review field

#### Scenario: Risk template library template is generated
- **WHEN** an agent generates the risk-template library template
- **THEN** the example run prints a harvest closure review result
