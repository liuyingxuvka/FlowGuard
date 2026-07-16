## ADDED Requirements

### Requirement: Strategy guidance remains current across maintained skill projections
The skill-suite distribution SHALL synchronize and parity-check the current DevelopmentProcessFlow skill, protocol, prompt, contract source, compiled contract, and check manifest after strategy-selection maintenance under one SkillGuard validation owner. Because the current project contract has no legacy or fallback runtime authority, the same owner SHALL also compile every maintained skill member to the current contract/depth schema and remove all former-runtime residuals before distribution currentness can pass.

#### Scenario: Installed protocol is stale
- **WHEN** the installed DPF protocol lacks the current strategy-selection contract
- **THEN** distribution parity fails rather than accepting an older or fallback guidance path

#### Scenario: Another maintained skill retains former-runtime authority
- **WHEN** any maintained member still contains a former runtime contract, legacy manifest, fallback authority, converter, or stale depth profile
- **THEN** suite distribution is blocked even if the DPF member itself is current
