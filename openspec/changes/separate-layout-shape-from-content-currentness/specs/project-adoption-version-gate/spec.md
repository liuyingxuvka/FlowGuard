## MODIFIED Requirements

### Requirement: Project adoption checks the layout before authority

The existing project-adoption version gate SHALL run the bounded current layout-shape audit before reading deep model, test, receipt, or evidence authority. A layout blocker SHALL make those later checks `not_run`, SHALL preserve the exact blocker, and SHALL require a direct current rewrite before adoption can pass. Adoption SHALL expose `light`, `affected`, and `full` claim boundaries; it SHALL NOT use a broad compatibility reader or silently expand an affected request to full validation.

#### Scenario: Layout is blocked before model authority

- **WHEN** the target layout is missing, obsolete, mixed, or unsafe
- **THEN** project adoption SHALL report `project_layout_invalid`
- **AND** model/test/evidence authority SHALL not be consulted

#### Scenario: Current layout allows authority checks

- **WHEN** the layout passes with a current manifest and conserved inventory
- **THEN** adoption MAY proceed to model and suite checks, each with its own
  current identity and claim boundary

#### Scenario: Light adoption passes without deep work

- **WHEN** shape, adoption controls, and the current pointer are valid
- **THEN** light adoption MAY pass its bounded claim
- **AND** deep model, validation, and release checks SHALL remain `not_run`

#### Scenario: Affected adoption has an unknown path

- **WHEN** a changed path has no exact owner or has multiple owners
- **THEN** affected adoption SHALL block and SHALL execute no owner

### Requirement: Direct-current repair has no general migration path

Project adoption SHALL never add or call a general migration command, compatibility reader, alias, dual manifest, or fallback layout authority. Obsolete material SHALL remain historical input until an AI or human directly rewrites it into the current layout and rebuilds identities.

#### Scenario: Historical material is available

- **WHEN** old paths or old manifests exist under history or elsewhere
- **THEN** adoption SHALL not use them as current authority and SHALL keep the target blocked until direct rewrite and identity rebuild complete
