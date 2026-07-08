## ADDED Requirements

### Requirement: Agent skills prompt primary path authority
FlowGuard Codex skills SHALL instruct agents to enumerate runtime paths,
select one primary authority, classify non-primary surfaces, reject automatic
fallback success, and require coverage evidence before broad claims.

#### Scenario: Agent starts non-trivial implementation
- **WHEN** an agent uses FlowGuard for feature work, bug repair, refactor,
  prompt/skill changes, install sync, or release confidence
- **THEN** the skill guidance SHALL prompt for primary path authority when
  runtime paths or compatibility surfaces are in scope

#### Scenario: Skill warns against A failed B succeeded
- **WHEN** a skill describes fallback policy
- **THEN** it SHALL state that primary failure must be visible and repaired
  rather than automatically routed to alternate success
