## ADDED Requirements

### Requirement: Plan detailing is exposed as a direct Codex satellite
FlowGuard SHALL include `flowguard-plan-detailing-compiler` as a directly invokable Codex satellite skill.

#### Scenario: Satellite is discoverable
- **WHEN** the FlowGuard Codex skill topology is read
- **THEN** plan detailing appears beside the existing direct satellites

#### Scenario: Installed skill sync covers plan detailing
- **WHEN** the repository skill is updated
- **THEN** installed Codex skill synchronization checks include the plan-detailing satellite
