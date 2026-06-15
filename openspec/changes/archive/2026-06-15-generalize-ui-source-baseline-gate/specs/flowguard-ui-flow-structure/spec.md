## ADDED Requirements

### Requirement: UI Flow Structure routes by UI work mode
FlowGuard UI Flow Structure SHALL classify each non-trivial UI task as greenfield, source-based, or mixed before requiring source-baseline evidence.

#### Scenario: Greenfield UI uses target task evidence
- **WHEN** a UI task has no existing source authority and is declared greenfield
- **THEN** UI Flow Structure requires product/user goals, supported task frames, target UI rationale, visible-surface coverage, functional chains, human-operability evidence, and implementation validation when claimed
- **AND** it does not require source-baseline mapping evidence

#### Scenario: Source-based UI uses source-baseline evidence first
- **WHEN** a UI task replaces, migrates, reproduces, or intentionally changes an existing source authority
- **THEN** UI Flow Structure requires a reviewed source-baseline model and target mapping before target UI completeness can be claimed

#### Scenario: Mixed UI separates source and new scope
- **WHEN** a UI task includes both source-based and greenfield areas
- **THEN** source-based areas require source-baseline mapping and greenfield areas require product/user-task rationale

### Requirement: UI Flow Structure compares source, target, and observed UI
FlowGuard UI Flow Structure SHALL compare Source Baseline, Target UI, and Observed UI for source-based scopes instead of accepting target-model self-consistency alone.

#### Scenario: Observed matches wrong target
- **WHEN** observed UI evidence matches the target model
- **AND** the target model has unapproved drift from the source baseline
- **THEN** UI Flow Structure blocks broad source-based UI confidence

#### Scenario: Source item has approved replacement
- **WHEN** a source item is replaced, hidden, moved, deleted, or deferred
- **AND** the target mapping includes a current disposition, rationale, and evidence boundary
- **THEN** UI Flow Structure may treat that source difference as accounted for

### Requirement: Generic source interactions replace source-specific callback gates
FlowGuard UI Flow Structure SHALL model file pickers, directory pickers, save dialogs, external opens, custom dialogs, commands, navigation, and no-handler controls with generic source interaction semantics.

#### Scenario: Source interaction branch is missing
- **WHEN** a source-based UI interaction requires confirm, cancel, result, error, focus return, or feedback behavior
- **AND** the source interaction gate lacks branch evidence or an explicit scoped boundary
- **THEN** UI Flow Structure blocks full source-based UI confidence

#### Scenario: Generic skill names no source-specific technology
- **WHEN** the installed generic UI Flow Structure skill is read
- **THEN** it describes source-baseline authority, work mode, generic interactions, source-target mapping, and observed alignment without naming a specific source technology as a hard gate
