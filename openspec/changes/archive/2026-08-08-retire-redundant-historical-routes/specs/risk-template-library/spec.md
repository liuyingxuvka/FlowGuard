## ADDED Requirements

### Requirement: Template search and harvest are conditional reuse operations
The risk-template library SHALL run only when a caller explicitly requests template reuse/publication or when current model evidence identifies a bounded, stable pattern intended for use outside the target project. Ordinary modeling and maintenance MUST NOT be blocked by missing search, no-match, harvest, merge, or not-harvestable dispositions.

#### Scenario: Explicit reuse request is present
- **WHEN** a caller asks to reuse or publish a risk template
- **THEN** the library searches the declared public and local layers and records exact match or no-match evidence

#### Scenario: Reusable pattern is discovered during modeling
- **WHEN** a current model plus executable known-bad proof demonstrates a stable cross-project pattern and the task includes template publication scope
- **THEN** the library may create or merge one candidate with provenance and privacy checks

#### Scenario: Ordinary project model has no template work
- **WHEN** neither trigger is present
- **THEN** FlowGuard completes the bounded model workflow without a template-library result and records no artificial skipped or no-match gate

## REMOVED Requirements

### Requirement: Template search uses public and local layers
**Reason**: Universal pre-generation search is unnecessary for ordinary target-specific DNA modeling.
**Migration**: Search both layers only after a conditional reuse trigger.

### Requirement: Template harvest closure is mandatory after reusable modeling
**Reason**: Requiring a closure disposition for every new or deepened model creates repeated reflection and false completion dependencies.
**Migration**: Run harvest closure only within an explicitly triggered reuse/publication operation.

### Requirement: Not-harvestable reasons are bounded
**Reason**: Ordinary modeling no longer creates a mandatory not-harvestable disposition.
**Migration**: When an explicit template operation chooses not to publish, preserve its concrete scoped reason in that operation's result.
