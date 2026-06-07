## ADDED Requirements

### Requirement: Global routing recognizes rough-plan expansion
FlowGuard global routing SHALL route non-trivial rough-plan expansion, plan completion, and "make this plan detailed" requests to the plan-detailing compiler.

#### Scenario: Rough plan routes to plan detailing
- **WHEN** a user asks to turn a vague idea or short plan into a detailed FlowGuard process plan
- **THEN** global routing selects the plan-detailing compiler before downstream FlowGuard routes

#### Scenario: Route still avoids trivial work
- **WHEN** the task is a tiny copy edit, direct command answer, or formatting-only change
- **THEN** global routing may skip plan detailing with a reason
