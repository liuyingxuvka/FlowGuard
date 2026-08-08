## ADDED Requirements

### Requirement: Local intent sources are exact model inputs
Every active `project_file` intent contribution SHALL have one exact owner-local source-path binding on its declared logical model. The binding SHALL participate in that model instance's resolved immutable input inventory and focused validation contract. For each model owner, the bound path set SHALL equal the active local intent-source set for that owner: missing, extra, duplicate, unsafe, unresolved, or foreign-owner paths SHALL block candidate construction and current-authority audit. A broad input selector, matching text, shared source file, or system-level stale finding SHALL NOT substitute for the exact owner-local binding.

#### Scenario: One model's local design source changes
- **WHEN** an active local intent source changes after the observed snapshot was accepted
- **THEN** fresh model observation changes the exact input identity of every logical model owner that declares that source
- **AND** affected-owner planning selects those models without treating unrelated models as changed

#### Scenario: Active local contribution has no owner-local input
- **WHEN** a current or candidate project-file contribution names a logical model but that model does not declare the exact source path
- **THEN** revision construction and current-authority audit block with the missing owner/source pair
- **AND** a broad glob, root owner, or inferred textual match cannot close the binding

#### Scenario: Model keeps an unused historical intent path
- **WHEN** a model declares an intent-source path that no active project-file contribution for that exact owner uses
- **THEN** current binding review reports the extra path and remains blocked
- **AND** the path must be deliberately removed instead of accumulating as a historical fallback input

#### Scenario: Several models consume one design source
- **WHEN** one local source legitimately informs several logical models
- **THEN** every model declares its own exact path binding and includes the same file identity in its own input inventory
- **AND** the shared file does not create a shared primary model owner

#### Scenario: Intent comes from WorkContext
- **WHEN** an active contribution is owned by a declared external WorkContext artifact
- **THEN** its exact context, native owner, source reference, and artifact fingerprint remain bound through the cumulative current-intent view
- **AND** FlowGuard does not convert the external artifact into a repository path or require a particular programming language or provider
