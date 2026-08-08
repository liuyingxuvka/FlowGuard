## ADDED Requirements

### Requirement: Provider-neutral blueprints carry exact path-quality subjects
A target-system blueprint SHALL bind each required behavior model to its compact path-quality subject identity, conclusion, trigger state, unresolved ids, and detailed-evidence fingerprint without assuming a programming language or provider. Parent blocks SHALL consume compact child summaries and exact interface identities rather than duplicate deep candidate payloads.

#### Scenario: Non-code workflow is modeled
- **WHEN** the target is a process, service graph, configuration workflow, or non-Python system
- **THEN** its path-quality rows use the same state, transition, input, output, effect, error, interface, obligation, and evidence semantics without requiring source-language-specific fields

#### Scenario: Child summary is stale
- **WHEN** a child path-quality subject or interface identity changes
- **THEN** the consuming parent summary and affected blueprint readiness become stale
