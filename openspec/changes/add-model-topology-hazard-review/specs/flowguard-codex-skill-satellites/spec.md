## ADDED Requirements

### Requirement: Codex exposes a topology hazard satellite skill

FlowGuard SHALL expose `flowguard-model-topology-hazard-review` as a direct
Codex satellite skill while keeping the model-first kernel as the router for
ambiguous or cross-route work.

#### Scenario: Skill route is present and prompt-grounded

- **WHEN** the Codex skill directories are inspected
- **THEN** `flowguard-model-topology-hazard-review` MUST have a concise
  `SKILL.md`, OpenAI agent metadata, a protocol reference, and a lazy-loaded
  prompt template
- **AND** the kernel route map MUST route model-shape future-use hazards to the
  new satellite skill.
