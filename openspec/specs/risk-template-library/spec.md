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

