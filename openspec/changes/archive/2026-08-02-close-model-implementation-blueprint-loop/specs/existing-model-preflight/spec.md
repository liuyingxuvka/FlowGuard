## ADDED Requirements

### Requirement: Whole-software blueprint preflight consumes an independent implementation inventory
Existing-model preflight SHALL request and preserve the independently discovered implementation and non-code inventory when the task explicitly claims, exports, or qualifies a whole-software blueprint. For ordinary work it SHALL continue selecting only the affected current owner closure and SHALL NOT scan or load the whole software solely because many models exist.

#### Scenario: Ordinary affected change
- **WHEN** a task changes one bounded behavior without requesting a whole-software blueprint claim
- **THEN** preflight selects the affected owner closure and does not require a full implementation inventory

#### Scenario: Whole-software blueprint requested
- **WHEN** the task explicitly requests blueprint closure or export
- **THEN** preflight includes the independent inventory identity and every unresolved implementation surface in its downstream handoff
