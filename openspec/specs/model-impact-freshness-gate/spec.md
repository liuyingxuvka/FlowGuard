# model-impact-freshness-gate Specification

## Purpose
This capability defines FlowGuard's Model Impact Freshness Gate behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Model Impact Classification

FlowGuard SHALL provide a public helper that reviews every existing model
inventory record against the current upgrade impact before broad upgrade
freshness is claimed.

#### Scenario: Every model is classified

- **GIVEN** an upgrade inventory with existing FlowGuard model records
- **AND** every record has an impact assessment
- **WHEN** the model-impact freshness helper reviews the plan
- **THEN** the report lists affected, reused, and deprecated model ids by
  classification

#### Scenario: Missing classification blocks

- **GIVEN** an upgrade inventory with an existing FlowGuard model record
- **AND** that record has no impact assessment
- **WHEN** the model-impact freshness helper reviews the plan
- **THEN** the report is blocked with an unknown-impact decision

### Requirement: Selective Reuse For Unchanged Models

FlowGuard SHALL allow previous model evidence to be reused only when a
not-impacted classification has a current reuse ticket.

#### Scenario: Not-impacted model reuses current evidence

- **GIVEN** a model classified as not impacted by the upgrade
- **AND** a reuse ticket names the previous evidence id
- **AND** model, dependency, FlowGuard semantic, previous evidence, and output
  fingerprints are current
- **WHEN** the model-impact freshness helper reviews the plan
- **THEN** the model is accepted as reused without requiring a rerun

#### Scenario: Reuse ticket missing blocks

- **GIVEN** a model classified as not impacted by the upgrade
- **AND** no reuse ticket exists
- **WHEN** the model-impact freshness helper reviews the plan
- **THEN** the report is blocked with a reuse-ticket decision

#### Scenario: Direct dependency hit needs same-output proof

- **GIVEN** an upgrade changed an artifact or FlowGuard semantic id listed by a
  model inventory record
- **AND** that model is classified as not impacted
- **WHEN** the reuse ticket has no same-output proof or output fingerprint
- **THEN** the report is blocked

### Requirement: Affected Models Require Current Rerun Evidence

FlowGuard SHALL require affected models to have update review and current
passing rerun evidence before upgrade freshness is claimed.

#### Scenario: Affected model rerun passes

- **GIVEN** a model classified as affected
- **AND** model and test update review are recorded
- **AND** the current rerun evidence has passed
- **WHEN** the model-impact freshness helper reviews the plan
- **THEN** the model is accepted as rerun evidence

#### Scenario: Affected model has no rerun

- **GIVEN** a model classified as affected
- **AND** no current rerun evidence exists
- **WHEN** the model-impact freshness helper reviews the plan
- **THEN** the report is blocked with an affected-model rerun decision

#### Scenario: Affected model output changes

- **GIVEN** a model classified as affected
- **AND** the rerun output changed
- **WHEN** no output-change explanation is recorded
- **THEN** the report is blocked

### Requirement: Deprecated Models Stay Visible

FlowGuard SHALL keep deprecated model records visible with a replacement and
reason rather than silently dropping them from upgrade freshness claims.

#### Scenario: Deprecated model has replacement

- **GIVEN** a model classified as deprecated
- **AND** a replacement model id and reason are recorded
- **WHEN** the model-impact freshness helper reviews the plan
- **THEN** the model is listed as deprecated without requiring rerun evidence

#### Scenario: Deprecated model lacks replacement

- **GIVEN** a model classified as deprecated
- **AND** no replacement model id is recorded
- **WHEN** the model-impact freshness helper reviews the plan
- **THEN** the report is blocked

### Requirement: Upgrade Freshness Decision

FlowGuard SHALL return a structured decision that distinguishes current,
unknown-impact, reuse-ticket, affected-rerun, deprecated-replacement, and
blocked outcomes.

#### Scenario: Mixed affected and reused inventory passes

- **GIVEN** all affected models have current rerun evidence
- **AND** all not-impacted models have valid reuse tickets
- **AND** all deprecated models have replacement records
- **WHEN** the model-impact freshness helper reviews the plan
- **THEN** the report is OK with a current freshness decision

### Requirement: Model and test reuse follow the same current-evidence principle
FlowGuard SHALL document model-result reuse and test-result reuse as separate
ticket types governed by the same principle: unchanged evidence may be reused
only when the owning ticket and concrete result artifact are current.

#### Scenario: Model result reuse remains model-owned
- **WHEN** model output is not impacted by a framework or artifact change
- **THEN** model reuse SHALL continue to use `ModelReuseTicket`

#### Scenario: Test result reuse is test-owned
- **WHEN** a previous test result is reused for current model/test alignment or
  TestMesh confidence
- **THEN** test reuse SHALL use a test-result reuse ticket plus proof artifact
  rather than a model reuse ticket
