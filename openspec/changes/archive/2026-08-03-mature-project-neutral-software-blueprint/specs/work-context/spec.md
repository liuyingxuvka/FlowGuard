## ADDED Requirements

### Requirement: WorkContext projects typed intent contributions
WorkContext SHALL project admitted requirement, design, plan, history, Spark/OpenSpark, changelog, and direct user-decision material into content-addressed intent contributions. Each contribution SHALL preserve its logical model or explicit unresolved owner, source kind and fingerprint, subject role, effective revision, decision state, supersession references, target obligation references, and rationale.

#### Scenario: Declared Spark material seeds an initial intent
- **WHEN** a project declares bounded Spark or OpenSpark material with an admitted intent mapping
- **THEN** WorkContext emits fingerprinted initial-intent contributions linked to the declared logical model or an explicit unresolved owner
- **AND** the provider retains authoring, execution, validation, and lifecycle authority

#### Scenario: A user decision supersedes an earlier idea
- **WHEN** a current user decision explicitly supersedes an admitted earlier contribution
- **THEN** both immutable contributions remain traceable in the same model lineage
- **AND** only the superseding contribution remains active for the candidate target

#### Scenario: A changelog entry has no semantic mapping
- **WHEN** a changelog or history artifact is current but has no admitted mapping to a model obligation or evolution decision
- **THEN** it remains fingerprinted planning or historical context
- **AND** it does not create, remove, or satisfy a behavior commitment

### Requirement: Intent context never becomes current behavior or test evidence by itself
An intent contribution SHALL be context and provenance only until its native model and revision owners consume it. WorkContext status, timestamps, task checkboxes, document wording, or provider completion SHALL NOT establish current model authority, implementation completion, or passing test evidence.

#### Scenario: A later document conflicts with an active decision
- **WHEN** two admitted contributions conflict and neither carries an explicit accepted supersession decision
- **THEN** WorkContext reports both contributions and the unresolved conflict
- **AND** it does not choose a winner from timestamp order alone

#### Scenario: Optional history is absent during ordinary work
- **WHEN** a scoped affected-only task has current requirements and owner evidence but no declared Spark or changelog source
- **THEN** the task MAY continue within its evidenced scope
- **AND** only a broad intent-history or whole-lineage completeness claim remains unavailable

#### Scenario: Provider status reports complete
- **WHEN** an OpenSpec, Spark, or other provider reports its native work item complete
- **THEN** FlowGuard preserves that status as WorkContext
- **AND** no model, code, test, or release evidence row becomes passing solely because of that status
