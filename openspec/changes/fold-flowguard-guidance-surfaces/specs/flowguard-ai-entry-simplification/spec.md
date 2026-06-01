## ADDED Requirements

### Requirement: Reference prompt surfaces remain layered
FlowGuard AI guidance SHALL keep long examples, agent prompt templates, and
route-specific protocol detail behind explicit reference handoffs rather than
embedding them in first-read or core second-read surfaces.

#### Scenario: Core modeling reference points outward
- **WHEN** an agent reads the core modeling protocol for ordinary FlowGuard work
- **THEN** satellite trigger detail is represented as a compact handoff table
- **AND** the agent can load the matching satellite protocol only after the
  route is selected

#### Scenario: Long templates are separated
- **WHEN** a protocol needs a reusable agent prompt template
- **THEN** the primary protocol points to a template reference file
- **AND** the long template body is not embedded in the primary protocol

### Requirement: Guidance fold-down preserves synchronization evidence
FlowGuard guidance fold-down SHALL be finalized only after source, editable
install behavior, installed Codex skill content, shadow workspace imports, and
local git evidence are checked after the final prompt/reference edits.

#### Scenario: Fold-down is finalized locally
- **WHEN** guidance reference compression is ready to claim done
- **THEN** validation includes OpenSpec checks, FlowGuard model checks, focused
  skill docs tests, broader regression, editable install verification,
  installed skill parity, shadow workspace verification, and local git status
  or commit/tag evidence
