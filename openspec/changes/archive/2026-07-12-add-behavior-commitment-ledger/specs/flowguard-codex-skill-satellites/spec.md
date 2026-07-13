## ADDED Requirements

### Requirement: Agent skills prompt default commitment registration
FlowGuard Codex skill satellites SHALL instruct agents to register or review
behavior commitments before non-trivial FlowGuard work that changes, validates,
publishes, or claims external behavior.

#### Scenario: New project starts FlowGuard work
- **WHEN** an agent begins non-trivial FlowGuard adoption or planning for a project without a current behavior ledger
- **THEN** the skill guidance SHALL route to Behavior Commitment Ledger baseline creation

#### Scenario: Existing behavior changes
- **WHEN** an agent changes a registered behavior
- **THEN** the skill guidance SHALL update the ledger row, owner model, evidence, and PPA binding when path-sensitive
