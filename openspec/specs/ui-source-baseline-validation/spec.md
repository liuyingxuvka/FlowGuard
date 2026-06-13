# ui-source-baseline-validation Specification

## Purpose
TBD - created by archiving change generalize-ui-source-baseline-gate. Update Purpose after archive.
## Requirements
### Requirement: UI work mode is explicit
The system SHALL require non-trivial UI work to declare whether the in-scope UI is `greenfield`, `source_based`, or `mixed` before applying source-baseline validation.

#### Scenario: Greenfield UI does not require a source baseline
- **WHEN** a UI change is declared `greenfield`
- **THEN** source-baseline evidence is not required
- **AND** the change still requires user goals, supported tasks, target UI rationale, visible-surface coverage, and implementation evidence when those claims are made

#### Scenario: Source-based UI requires a source baseline
- **WHEN** a UI change is declared `source_based`
- **THEN** the review requires a source-baseline model before target UI completeness can be claimed

#### Scenario: Mixed UI splits obligations
- **WHEN** a UI change is declared `mixed`
- **THEN** the review requires source-baseline evidence for source-based scope and greenfield task rationale for newly invented scope

### Requirement: Source baseline records authoritative UI structure
The system SHALL model the authoritative source for source-based UI work without hard-coding any specific source technology.

#### Scenario: Source item inventory is complete
- **WHEN** a source-based UI baseline is reviewed
- **THEN** every in-scope source page, region, visible item, interaction, and user task is recorded or explicitly scoped out with reason, owner, evidence reference, and validation boundary

#### Scenario: Source type is generic
- **WHEN** a source row identifies its evidence source
- **THEN** the source type is recorded as a generic authority such as legacy app, prototype, design file, screenshot, product spec, customer workflow, manual observation, or runtime observation
- **AND** the core model does not require a source-specific parser or tool name

### Requirement: Source interactions use generic semantics
The system SHALL describe source interactions using generic interaction semantics and branch coverage.

#### Scenario: External interaction covers branches
- **WHEN** a source interaction opens a file picker, directory picker, save dialog, external shell/window, custom dialog, navigation target, command, or no-handler control
- **THEN** the source interaction gate requires trigger, confirm or selected value when applicable, cancel or no-op when applicable, success feedback, error path, focus or state return, evidence reference, and current result

#### Scenario: No-handler control needs disposition
- **WHEN** a source item appears actionable but has no handler or equivalent behavior
- **THEN** target mapping requires a disposition such as disable, hide, replace, make read-only, explicitly document, or scope out

### Requirement: Target mapping records every source difference
The system SHALL map source-baseline items and tasks to target UI items, regions, interactions, and tasks with explicit dispositions.

#### Scenario: Source item has no target disposition
- **WHEN** an in-scope source item has no target mapping and no scoped-out reason
- **THEN** source-baseline validation blocks target UI completeness

#### Scenario: Changed placement needs approval
- **WHEN** a source item or task changes target page, region, task owner, interaction kind, or visibility
- **THEN** the mapping records a finite disposition, rationale, approval or evidence reference, and validation boundary

#### Scenario: New target item is accounted
- **WHEN** a target item has no source item because it is newly introduced
- **THEN** the mapping records a `new` disposition with user-task rationale and evidence boundary

### Requirement: Observed UI aligns with source and target
The system SHALL prevent source-based UI validation from comparing only Observed UI against Target UI when a source baseline is in scope.

#### Scenario: Target is self-consistent but source-wrong
- **WHEN** the observed UI matches the target model
- **AND** the target model moves, hides, deletes, replaces, or invents source behavior without an approved mapping
- **THEN** observed-source alignment blocks full UI confidence

#### Scenario: Approved difference passes
- **WHEN** observed UI differs from the source baseline
- **AND** the target mapping records an approved disposition with current evidence
- **THEN** observed-source alignment may accept the difference for the declared scope

### Requirement: Generic route rejects hard-coded source technology in core guidance
The system SHALL keep generic UI source-baseline guidance free of hard-coded source technology names in active skills, public templates, public API names, and current route documentation.

#### Scenario: Active generic surface names a specific source technology
- **WHEN** active generic UI route guidance, template code, public API names, or current specs name one specific source technology as a hard gate
- **THEN** the generic surface review fails until the wording or API is generalized

#### Scenario: Historical logs are not active guidance
- **WHEN** historical changelog or adoption-log entries mention a previous source-specific implementation
- **THEN** the generic surface review does not require rewriting history

