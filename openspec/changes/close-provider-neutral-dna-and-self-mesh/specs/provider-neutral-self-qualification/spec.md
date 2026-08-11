## Purpose

This capability gives FlowGuard and downstream Guard skills a single, target-neutral way to declare provider ownership and to report whether a layered DNA model is merely present, statically ready, or actually qualified by current semantic, code, and test bindings.

## ADDED Requirements

### Requirement: Provider declarations SHALL be explicit and target-neutral

The system SHALL accept a provider declaration that names one profile, one layer plan, one owner, and one claim boundary, without requiring FlowGuard to know the domain semantics of the provider.

#### Scenario: A valid external provider is admitted
- **WHEN** a provider declares a unique id, a registered profile, a supported target kind, a layer plan, and an owner
- **THEN** the registry admits it and returns the same declaration as the canonical current entry

#### Scenario: A duplicate provider is rejected
- **WHEN** a second declaration reuses an existing provider id or profile-owner pair
- **THEN** registry admission fails visibly with a duplicate-owner reason and keeps the first entry unchanged

#### Scenario: An unknown profile is rejected
- **WHEN** a provider references a profile that has no registered layer plan
- **THEN** registry admission fails visibly and does not create an implicit or fallback profile

### Requirement: Self-DNA qualification SHALL distinguish readiness levels

The system SHALL report static blueprint readiness separately from semantic mesh qualification and SHALL only report a qualified self-DNA when the current semantic mesh, layer hierarchy, code bindings, and test bindings are all present and current within the declared boundary.

#### Scenario: Static blueprint is ready but semantic evidence is stale
- **WHEN** the blueprint compiles but a semantic child fingerprint or binding is stale
- **THEN** the result reports static readiness independently and marks semantic qualification as stale or blocked

#### Scenario: Candidate semantic mesh is not current authority
- **WHEN** the semantic mesh status is candidate, unlicensed, or unknown
- **THEN** qualification is blocked with that exact status and no qualified self-DNA claim is emitted

#### Scenario: Fully bound current self-DNA qualifies
- **WHEN** every required layer, parent-child relation, code owner, test owner, and current evidence identity is present
- **THEN** the result reports qualified self-DNA and exposes the binding counts and evidence identities used for the claim

### Requirement: Qualification SHALL use the native directory and remain non-reconstructive

The qualification contract SHALL inspect the exact current native model directory, its model files, code/test bindings, evidence identities, and source revision in place. It SHALL NOT create a standalone file, copied directory, transport bundle, reconstruction, language-specific implementation, or fallback route as part of ordinary qualification.

#### Scenario: A downstream skill consumes a qualified contract
- **WHEN** an external Guard supplies a registered provider and its own domain evidence
- **THEN** FlowGuard returns the provider-neutral qualification result and the native-directory identity without interpreting domain-specific states

#### Scenario: A caller requests a standalone DNA artifact
- **WHEN** a caller asks for a bundle, copied-directory export, materialization, or isolated import
- **THEN** the current product surface rejects the request with a typed `native_directory_only` result and leaves the repository and authority unchanged

### Requirement: Reduction status SHALL be honest and tri-state

The reduction report SHALL separately expose candidate-inventory completeness, proof completeness, and applied-and-verified simplification; a report SHALL NOT describe cleanup as release-ready when unresolved candidates or unapplied changes remain.

#### Scenario: Candidates exist but proof is incomplete
- **WHEN** the inventory contains candidates whose callers, semantics, tests, or ownership are unresolved
- **THEN** the report marks proof incomplete and keeps the candidates unresolved

#### Scenario: Proof is complete but no simplification was applied
- **WHEN** a candidate has complete proof but the source has not been changed and revalidated
- **THEN** the report marks proof complete but applied-and-verified simplification false

#### Scenario: Simplification is applied and verified
- **WHEN** a proven contraction or retirement is applied and the affected model, code, and tests pass under the same frozen identity
- **THEN** the report marks applied-and-verified simplification true and records the verification identity
