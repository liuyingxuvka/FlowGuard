## ADDED Requirements

### Requirement: AI entry guidance points to field replacement handoffs
FlowGuard AI entry guidance SHALL point agents to structured field lifecycle
and replacement disposition evidence without adding a parallel session runner
or a long prompt checklist.

#### Scenario: Agent starts field-heavy work
- **WHEN** an agent starts work involving fields, schemas, modes, feature
  flags, prompt/config surfaces, or feature replacement
- **THEN** compact guidance MUST direct the agent to existing model preflight,
  field lifecycle mesh, model-code-test alignment, development freshness, and
  closure gates

#### Scenario: Entry guidance does not replace owner routes
- **WHEN** field lifecycle review reports missing tests, code owner gaps,
  old-field disposition gaps, stale evidence, or oversized field groups
- **THEN** AI guidance MUST route to the existing owner route instead of
  claiming the entry path solved the gap
