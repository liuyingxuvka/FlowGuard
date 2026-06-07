## ADDED Requirements

### Requirement: AI guidance asks open-ended model-angle questions
FlowGuard AI entry guidance SHALL ask agents to consider additional model
angles without presenting known FlowGuard routes as a closed checklist.

#### Scenario: Agent starts non-trivial model-first work
- **WHEN** an agent starts a non-trivial feature, workflow, bug repair, prompt, process, or model change
- **THEN** compact guidance MUST ask what the current model sees, what it may miss, what failure would be missed, and whether to reuse, extend, create, split, defer, scope out, or ask a human

#### Scenario: Known routes are examples
- **WHEN** AI guidance mentions fields, information flow, authority, evidence freshness, or parent-child handoffs
- **THEN** the guidance MUST state that those examples are route hints rather than the full set of valid model angles
