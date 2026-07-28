## ADDED Requirements

### Requirement: Hot-path budgets cover guaranteed first-read bundles
FlowGuard SHALL maintain a deterministic manifest of representative AI routes
whose budgets include every prompt surface guaranteed to be loaded before route
work begins, including root guidance, the selected skill shell, automatically
required shared/reference material, and declared route configuration.

#### Scenario: Individual files pass but the bundle is oversized
- **WHEN** each first-read file is below its individual limit but their declared
  route bundle exceeds its byte or conservative token-estimate budget
- **THEN** the hot-path prompt check SHALL fail for that route

#### Scenario: Route material changes
- **WHEN** a guaranteed-loaded prompt component changes
- **THEN** telemetry SHALL report the route id, component identities, UTF-8
  bytes, characters, lines, conservative token estimate, and budget result

### Requirement: Shared guidance is guaranteed loaded
FlowGuard SHALL permit deduplication of common invariants into shared guidance
only when the
route loader and clean consumer projection guarantee that every affected skill
loads the exact shared component before acting.

#### Scenario: Satellite shell delegates common gates
- **WHEN** repeated cross-route gates are removed from a satellite `SKILL.md`
- **THEN** the skill's declared first-read bundle SHALL include the current
  shared core and the satellite SHALL retain its trigger, owner, route-specific
  gates, reference routing, and claim boundary

#### Scenario: Shared guidance is only linked
- **WHEN** a satellite merely links optional shared text without guaranteed
  loading
- **THEN** prompt compression SHALL remain incomplete

### Requirement: Token telemetry is regression evidence
FlowGuard SHALL expose deterministic representative-route prompt telemetry as
test and release evidence without presenting an estimate as actual provider
billing.

#### Scenario: Release validation runs
- **WHEN** a FlowGuard source release is validated
- **THEN** the release evidence SHALL include current prompt-bundle metrics and
  budget status for every representative route
