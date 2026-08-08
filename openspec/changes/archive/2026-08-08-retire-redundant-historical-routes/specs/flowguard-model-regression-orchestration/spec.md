## ADDED Requirements

### Requirement: Retired regression owners require replacement-case accounting
Model regression orchestration SHALL remove an intentionally retired child only after every still-required failure obligation and native case has either moved to one current child with an executable oracle or received an explicit product-behavior retirement disposition.

#### Scenario: Historical model child is redundant
- **WHEN** its protections are fully mapped to current children or intentionally retired behavior
- **THEN** the manifest, purpose closure, model inventory, parent aggregation, and release plan use the reduced current child set

#### Scenario: Failure obligation is orphaned
- **WHEN** a retired child's current failure or known-bad obligation has neither a replacement owner nor an approved behavior-retirement disposition
- **THEN** manifest validation blocks removal and identifies the orphaned obligation

### Requirement: Runtime validation inputs have exact model owners
Every ordinary runtime source input in the model-regression manifest SHALL map to its exact current model owner set through the authoritative software-blueprint ownership map or an equally exact reviewed declaration. A broad package-wide source glob SHALL NOT make every current model stale merely because one bounded runtime module changed. A truly package-global metadata or toolchain input MAY affect every model only when its global ownership is explicit and independently reviewable.

#### Scenario: One runtime module serves one model owner
- **WHEN** that module changes and no package-global input changes
- **THEN** affected planning SHALL invalidate only its exact model owner and any models reached through declared dependency edges
- **AND** unrelated sibling models SHALL remain eligible for exact-current evidence reuse

#### Scenario: An ordinary runtime module has no exact owner mapping
- **WHEN** manifest compilation finds a runtime source that is neither directly mapped nor covered by one exact reviewed owner group
- **THEN** manifest validation SHALL fail with the unmapped source
- **AND** it SHALL NOT fall back to a package-wide run-all group

#### Scenario: Package metadata is globally consumed
- **WHEN** a declared package-metadata or toolchain input changes and every current model genuinely consumes it
- **THEN** the manifest MAY invalidate the complete current model set
- **AND** that global edge SHALL remain separately named from ordinary runtime source ownership

### Requirement: Every logical model has one canonical regression evidence identity
Each current model-regression manifest row SHALL declare exactly one native evidence identity equal to `check:model-regression:<logical-model-id>`. Additional independently owned diagnostic checks MAY remain beside it, but a hyphenated alias, display label, historical spelling, or another model's identity SHALL NOT replace or duplicate the canonical logical-model evidence id.

#### Scenario: One evidence id uses a display-name spelling
- **WHEN** a manifest row's logical model id uses one canonical spelling but its model-regression evidence id uses a hyphenated, aliased, or historical spelling
- **THEN** manifest validation SHALL fail before the inconsistency can expand across every implementation surface owned by that model
- **AND** the producer SHALL replace the identity directly rather than adding an alias or compatibility reader

#### Scenario: One model also owns a separate diagnostic check
- **WHEN** the purpose closure declares its exact canonical model-regression evidence id and one separately named diagnostic projection
- **THEN** both evidence members MAY remain when each has a distinct current purpose
- **AND** only the exact `check:model-regression:<logical-model-id>` row SHALL satisfy the logical model-regression identity
