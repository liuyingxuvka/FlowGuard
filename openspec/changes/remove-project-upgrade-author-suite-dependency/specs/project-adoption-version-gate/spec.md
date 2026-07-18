## ADDED Requirements

### Requirement: Non-editable project upgrade uses packaged consumer authority
FlowGuard project audit and writing upgrade SHALL validate the current global
15-skill consumer projection against one immutable consumer-suite authority
shipped inside the installed FlowGuard package. Runtime project adoption SHALL
NOT read an author suite map, require an editable checkout, inspect a
target-local suite, or select a fallback authority.

#### Scenario: Empty ordinary project upgrades under a non-editable install
- **WHEN** an exact non-editable FlowGuard installation runs
  `project-upgrade` in an empty ordinary project
- **AND** the matching global 15-skill consumer projection is current
- **THEN** the command writes the current managed `AGENTS.md` block and
  `.flowguard/project.toml`
- **AND** the post-write project audit passes
- **AND** the project contains no `.agents/skills`, `.skillguard`, suite map,
  or copied FlowGuard skill directory

#### Scenario: Packaged authority is unavailable
- **WHEN** the installed package lacks a readable current consumer-suite
  authority
- **THEN** project upgrade exits nonzero before mutation with an exact
  authority finding
- **AND** it does not consult an author checkout or target-local suite map

#### Scenario: Global projection differs from packaged authority
- **WHEN** a declared consumer member or file is missing, extra, modified, or
  contains author-control residue
- **THEN** project upgrade exits nonzero before mutation with exact parity
  findings
- **AND** it does not install, repair, alias, or downgrade the global suite

#### Scenario: Project contains an obsolete local suite
- **WHEN** the target project contains a legacy local FlowGuard suite or suite
  map
- **THEN** that local tree is not read as current authority
- **AND** the packaged authority and global consumer projection remain the
  only validation path
