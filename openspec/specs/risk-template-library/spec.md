# risk-template-library Specification

## Purpose
Define packaged public and per-machine local risk templates so new or deepened
FlowGuard models can reuse known risk shapes, record no-match decisions, and
harvest reusable local candidates without leaking private project paths.
## Requirements
### Requirement: Packaged public risk templates
FlowGuard SHALL provide packaged public risk templates that are available on any
computer after FlowGuard is installed, without requiring a project-local
template library.

#### Scenario: Public templates load without local state
- **WHEN** a user searches risk templates on a machine with no local template library
- **THEN** FlowGuard returns packaged public templates for common reusable risk patterns

#### Scenario: Public templates avoid private paths
- **WHEN** packaged public templates are inspected
- **THEN** they contain abstract workflow/risk language and no machine-specific user paths

### Requirement: Portable per-machine local template library
FlowGuard SHALL support a per-machine local risk template library using a
portable per-user data root, with `FLOWGUARD_TEMPLATE_LIBRARY_ROOT` as an
override.

#### Scenario: Default local root is portable
- **WHEN** FlowGuard computes the default local template library path
- **THEN** the path is derived from the current user's platform/home directory and not from a hard-coded developer path

#### Scenario: Environment override selects library root
- **WHEN** `FLOWGUARD_TEMPLATE_LIBRARY_ROOT` is set
- **THEN** FlowGuard reads and writes local templates under that directory

### Requirement: Template search uses public and local layers
FlowGuard SHALL search packaged public templates and the per-machine local
library before a model creation or model deepening flow generates a new model.

#### Scenario: Search reports matched layers
- **WHEN** public and local templates both match a query
- **THEN** the search result identifies which matches came from packaged public templates and which came from the local library

#### Scenario: No match is explicit
- **WHEN** no template matches the current risk
- **THEN** the template reuse review records an explicit no-match reason instead of silently skipping reuse

### Requirement: Local template harvest creates candidate risk cards
FlowGuard SHALL harvest a local candidate template only from reusable model evidence that includes a protected error class, required state or side effects, completion evidence, a known-bad case, and model-instance proof that the known-bad case was caught.

#### Scenario: Reusable model is saved as candidate
- **WHEN** a model run exposes a reusable risk pattern with a known-bad case, completion evidence, and current known-bad proof
- **THEN** FlowGuard can write a local candidate template card with status `candidate`

#### Scenario: Project-specific model is not harvested
- **WHEN** a model lacks a protected error class, known-bad case, executable proof, or reusable abstract terms
- **THEN** FlowGuard refuses to write a local candidate and reports the missing fields

### Requirement: Similar templates can merge without losing evidence
FlowGuard SHALL provide deterministic local merge behavior for templates with
the same protected error classes and merge keys while preserving source ids and
known-bad cases.

#### Scenario: Matching candidates merge
- **WHEN** two local candidate templates share a merge key and protected error class
- **THEN** FlowGuard produces one merged template with combined known-bad cases and source ids

#### Scenario: False friends stay separate
- **WHEN** two templates have similar words but protect different error classes
- **THEN** FlowGuard keeps them separate and records the reason as a false-friend rationale when supplied

### Requirement: Template harvest closure is mandatory after reusable modeling
FlowGuard SHALL require a template harvest closure review after any new or materially deepened model before formal FlowGuard completion confidence.

#### Scenario: New model writes reusable candidate
- **WHEN** a new model exposes a reusable protected error class with state or side effects, completion evidence, a known-bad case, and known-bad proof
- **THEN** the harvest closure review records disposition `written` and the written local template id

#### Scenario: Deepened model strengthens existing template
- **WHEN** a materially deepened model adds a known-bad case, required evidence, or state/side-effect requirement to an existing reusable risk pattern
- **THEN** the harvest closure review records disposition `merged` and the affected template id

#### Scenario: Existing template already covers the model
- **WHEN** public or local template search finds a template that already covers the new or deepened model pattern
- **THEN** the harvest closure review may record disposition `duplicate_linked` with the linked template id instead of writing a duplicate local card

#### Scenario: Harvest is skipped with accepted reason
- **WHEN** a model is not reusable enough to harvest
- **THEN** the harvest closure review records disposition `not_harvestable` and one accepted reason

#### Scenario: Missing closure blocks formal confidence
- **WHEN** a new or deepened formal model has no harvest closure review
- **THEN** FlowGuard reports a blocking template harvest closure gap before formal completion confidence

### Requirement: Not-harvestable reasons are bounded
FlowGuard SHALL accept only concrete not-harvestable reasons so agents cannot
replace harvest closure with vague prose.

#### Scenario: Vague skip reason is rejected
- **WHEN** a harvest closure review uses `not_harvestable` without an accepted reason
- **THEN** FlowGuard reports an unsupported or missing not-harvestable reason

#### Scenario: Human deferral remains explicit
- **WHEN** the user explicitly asks not to write a local candidate template
- **THEN** FlowGuard may record `human_deferred` as the not-harvestable reason

