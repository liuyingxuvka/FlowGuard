## ADDED Requirements

### Requirement: Kernel requires target-project adoption rule
The FlowGuard Skill Kernel SHALL tell agents that real FlowGuard use in another
repository must check whether the target project carries a FlowGuard
`AGENTS.md` adoption block.

#### Scenario: Target project lacks FlowGuard AGENTS block
- **WHEN** the kernel is used for non-trivial FlowGuard work in another
  repository
- **AND** the target project lacks a FlowGuard managed `AGENTS.md` block
- **THEN** the kernel instructs the agent to add or update the block from the
  canonical FlowGuard snippet unless the user requested read-only work

#### Scenario: Read-only work does not force writes
- **WHEN** the user explicitly requests read-only analysis
- **THEN** the kernel may report the missing AGENTS block as a gap without
  writing project files
