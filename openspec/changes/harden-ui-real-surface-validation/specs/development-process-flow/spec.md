## ADDED Requirements

### Requirement: UI last-mile artifacts participate in process freshness
DevelopmentProcessFlow SHALL treat observed UI inventories, visible-surface
mappings, functional chains, source-baseline interaction gates,
implementation-validation runs, native/manual boundaries, installed-skill sync,
shadow-workspace sync, and local Git sync as freshness-sensitive artifacts.

#### Scenario: UI inventory changes after click evidence
- **WHEN** an observed UI inventory or visible control map changes after
  implementation validation evidence was produced
- **THEN** DevelopmentProcessFlow marks the affected UI evidence stale and
  recommends rerunning UI implementation validation

#### Scenario: Background regression is progress only
- **WHEN** a UI/model regression is started in the background but has no final
  exit status and result artifact
- **THEN** DevelopmentProcessFlow treats it as liveness only, not current
  validation evidence

#### Scenario: Skill guidance changes require sync evidence
- **WHEN** UI route skill guidance or public templates change
- **THEN** final confidence requires installed-skill sync, editable-install
  import evidence, shadow-workspace import evidence, and local Git sync status
  or an explicit scoped boundary
