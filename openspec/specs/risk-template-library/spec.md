# risk-template-library Specification

## Purpose
TBD - created by archiving change raise-minimum-valuable-model-entry. Update Purpose after archive.
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
FlowGuard SHALL harvest a local candidate template only from reusable model
evidence that includes a protected error class, required state or side effects,
completion evidence, and a known-bad case.

#### Scenario: Reusable model is saved as candidate
- **WHEN** a model run exposes a reusable risk pattern with a known-bad case and completion evidence
- **THEN** FlowGuard can write a local candidate template card with status `candidate`

#### Scenario: Project-specific model is not harvested
- **WHEN** a model lacks a protected error class, known-bad case, or reusable abstract terms
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
