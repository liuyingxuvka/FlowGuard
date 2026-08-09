## ADDED Requirements

### Requirement: Release work freezes identity once and validates once
The development process SHALL perform implementation and affected validation first, one consolidated cleanup pass second, version/model/install identity synchronization third, and one final full release gate only after the release tree is frozen.

#### Scenario: A feature is still changing
- **WHEN** source, model, prompt, or OpenSpec work remains in progress
- **THEN** the process SHALL use affected-only checks and SHALL not start the final full release parent

#### Scenario: Release identities are frozen
- **WHEN** source, model authority, OpenSpec, skills, installation, and release tree are current and frozen
- **THEN** plan-only SHALL classify each final owner as execute, reuse_current, or blocked before any producer starts
- **AND** one final parent SHALL execute each stale owner at most once

### Requirement: Independent reconstruction is not a routine release owner
The ordinary FlowGuard development and release process SHALL not execute or require an independent software reconstruction experiment unless a separate explicit change requests that qualification.

#### Scenario: User requests ordinary modeling or maintenance
- **WHEN** a target is being modeled, changed, audited, or released without an explicit reconstruction qualification request
- **THEN** the process SHALL use the portable blueprint and affected validation routes only
- **AND** it SHALL not start a reconstruction branch
