## ADDED Requirements

### Requirement: Satellite reference protocols own detailed route guidance
Each directly invokable FlowGuard satellite SHALL own its detailed protocol in
the satellite `references/` directory when that route has a standalone skill.

#### Scenario: Kernel reference duplicates are folded
- **WHEN** the kernel reference directory includes a protocol whose detailed
  route is owned by a standalone satellite
- **THEN** the kernel copy is either absent or a compact handoff stub
- **AND** the satellite reference remains reachable and substantive

#### Scenario: Standalone satellite remains usable
- **WHEN** a satellite skill is installed or copied independently
- **THEN** its `SKILL.md` and satellite reference provide the route trigger,
  hard gates, workflow checklist, validation boundary, and non-goals without
  requiring the kernel's duplicate copy
