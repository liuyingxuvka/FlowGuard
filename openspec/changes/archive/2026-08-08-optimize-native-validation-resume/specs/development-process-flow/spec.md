## ADDED Requirements

### Requirement: Native validation ownership is bounded and non-duplicative
DevelopmentProcessFlow SHALL partition a broad native validation responsibility into named owners whose declared tests and source inputs correspond to distinct obligations. A native owner SHALL NOT retain tests already owned by another current member merely to make one route appear comprehensive.

#### Scenario: Broad owner overlaps sibling owners
- **WHEN** one native member selects tests that are already mapped to current sibling owners and the duplicate selection adds no independent obligation
- **THEN** the process SHALL contract the broad member to its distinct obligations and keep the sibling tests with their primary owners

#### Scenario: Split preserves all obligations
- **WHEN** a broad native owner is split into focused responsibilities
- **THEN** the compiled contract SHALL still map every required obligation to at least one exact native binding before validation can proceed

### Requirement: Full validation consumes resumable native members
The frozen full-validation owner SHALL invoke native-skill validation through the explicit exact-current resume execution path so successful unchanged member work is composed rather than repeated after a sibling or parent failure.

#### Scenario: Earlier parent failed after native member success
- **WHEN** a prior full-validation parent failed outside an exact-current native member and the member's complete receipt identities remain current
- **THEN** the next frozen parent SHALL reuse that member and execute only missing or stale native members

#### Scenario: Producer source changes before final gate
- **WHEN** the native receipt producer or a declared member input changes after a member receipt was published
- **THEN** the final gate SHALL execute the affected member once before accepting its evidence

### Requirement: Focused repair precedes one frozen full gate
DevelopmentProcessFlow SHALL use focused affected checks while the source is changing and SHALL reserve broad full validation for one stable frozen integration snapshot. A failed broad run SHALL be classified before repair; unchanged successful child evidence SHALL be reused only through exact-current verification.

#### Scenario: Validation-path defect is discovered
- **WHEN** a broad run exposes duplicate ownership, an avoidable timeout, or incomplete receipt binding
- **THEN** the process SHALL repair and focus-check that validation path before starting the next frozen full gate
