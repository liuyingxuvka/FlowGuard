## ADDED Requirements

### Requirement: System-composition delivery follows a proof-first lifecycle
DevelopmentProcessFlow SHALL order system-composition work as benchmark/problem freeze, existing-owner and semantic freeze, candidate-architecture comparison, single checker-owner implementation, native evidence, prompt/skill activation, latest stable SkillGuard validation, clean consumer projection, local adoption/version sync, frozen-snapshot final verification, scoped Git commit, push/tag/source-only GitHub Release, and post-publish source/install/Git/remote parity verification.

#### Scenario: Prompt claims capability before native evidence
- **WHEN** agent guidance is updated before the executable API/CLI and benchmark acceptance exist
- **THEN** the process blocks activation because the AI would claim a capability the product cannot yet execute

#### Scenario: Large regressions run in the background
- **WHEN** model regressions are backgrounded under one declared owner
- **THEN** implementation may continue while progress is treated only as liveness and final confidence waits for complete terminal evidence

#### Scenario: Source changes after final validation starts
- **WHEN** a peer or owner changes a governed source, toolchain, or impact-plan input
- **THEN** the old final receipt becomes stale and no second unattended retry is started

#### Scenario: SkillGuard changes during implementation
- **WHEN** the maintained FlowGuard skill source is ready but SkillGuard has concurrent maintenance activity
- **THEN** the process freezes the latest stable released SkillGuard identity immediately before supervision, passes explicit run-state and evidence roots, and does not consume an older or moving maintainer checkout

#### Scenario: Post-publish correction is required
- **WHEN** source or release evidence changes after the release tag is published
- **THEN** the published tag remains immutable and the correction uses a new version rather than moving or overwriting the existing release
