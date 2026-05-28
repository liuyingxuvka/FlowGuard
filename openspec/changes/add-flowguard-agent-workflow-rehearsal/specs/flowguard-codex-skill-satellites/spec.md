## ADDED Requirements

### Requirement: Agent workflow rehearsal satellite is directly discoverable
The repository SHALL provide `flowguard-agent-workflow-rehearsal` as a
standalone FlowGuard satellite skill that Codex can invoke directly.

#### Scenario: Rehearsal satellite is listed with peers
- **WHEN** a Codex agent reads the FlowGuard skill topology or reusable AGENTS
  guidance
- **THEN** `flowguard-agent-workflow-rehearsal` appears as a peer FlowGuard
  satellite beside the existing route-specific satellites

#### Scenario: Rehearsal satellite preserves hard gates
- **WHEN** the satellite is used in another repository or machine
- **THEN** it requires the real FlowGuard package for FlowGuard claims
- **AND** it requires a fresh current-machine skill inventory before rehearsal

### Requirement: Installed skill synchronization includes rehearsal satellite
The release and local synchronization process SHALL include
`flowguard-agent-workflow-rehearsal` in repository and installed Codex skill
surface checks.

#### Scenario: Installed skill is synchronized
- **WHEN** the change is validated for local use
- **THEN** the installed Codex skills directory contains the new rehearsal
  satellite
- **AND** repository skill docs tests verify the satellite topology

#### Scenario: Installed prompt behavior is not claimed from repository-only changes
- **WHEN** the repository copy of the skill has changed
- **THEN** the change is not reported as active installed behavior until the
  installed skill surface is synchronized or explicitly reported as unsynced
