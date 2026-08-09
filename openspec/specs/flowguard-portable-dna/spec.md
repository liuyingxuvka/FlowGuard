# FlowGuard Portable DNA Specification

## Purpose

Define one target-neutral, content-addressed representation of a current FlowGuard blueprint. It is a portable model projection, not a second source-code authority and not an automatic reconstruction exercise.

## Requirements

### Requirement: The current blueprint can be exported as one portable bundle
The system SHALL export the current observed target blueprint as one content-addressed bundle containing the manifest, referenced shards, model hierarchy, parent-child interfaces, inputs, states, transitions, outputs, intent, resources, implementation bindings, test/oracle bindings, readiness results, and exact source/provider identities.

#### Scenario: Export uses the current observed authority
- **WHEN** a caller requests a portable export
- **THEN** the export SHALL consume the sole current observed implementation head, accepted model revision, complete effective intent view, and frozen provider artifacts
- **AND** a target, experiment, history, or caller-supplied fingerprint SHALL NOT become the bundle authority

#### Scenario: A required layer is missing
- **WHEN** a required model, interface, resource, implementation, test, oracle, intent, or readiness member is absent or stale
- **THEN** the export SHALL fail visibly with the exact missing identity
- **AND** it SHALL not emit a ready portable status

### Requirement: A copied bundle verifies without the source repository
The system SHALL verify a copied portable bundle using only its manifest, content-addressed shards, declared provider/toolchain identities, and rebind contract.

#### Scenario: Bundle is copied to an isolated directory
- **WHEN** all declared shards are copied without the original repository's blueprint files
- **THEN** verification SHALL recompute the bundle identity, resolve every parent-child and layer reference, and return pass only when all references close

#### Scenario: A shard is changed or missing
- **WHEN** a shard is missing, changed, duplicated, or points to another subject revision
- **THEN** verification SHALL return a visible failure
- **AND** it SHALL not use an alternate shard format or source repository

### Requirement: Portable export has a separate readiness status
The system SHALL report `static-ready`, `exported-portable`, or an explicit non-pass status as separate claims; static readiness SHALL not imply portable export readiness.

#### Scenario: Static blueprint is complete but no bundle exists
- **WHEN** all static layers are current but no verified portable bundle was materialized
- **THEN** the result SHALL remain `static-ready` and SHALL report portable export as not run or incomplete

#### Scenario: Portable bundle verifies
- **WHEN** a bundle has current identity, complete shards, and successful isolated verification
- **THEN** the result SHALL report `exported-portable` in addition to the underlying static status

### Requirement: Current self DNA can be exchanged
FlowGuard SHALL be able to materialize one current self portable-blueprint
bundle from the same current source/model/code/test evidence used by its
canonical self blueprint.

#### Scenario: Self bundle is exported
- **WHEN** the current self blueprint is canonically export-ready
- **THEN** one content-addressed portable bundle SHALL be written atomically
- **AND** the bundle SHALL preserve static, portable-integrity, and execution
  status as separate fields

#### Scenario: Self bundle is checked in isolation
- **WHEN** the exported self bundle is copied to an empty directory
- **THEN** the portable verifier SHALL validate it without loading source,
  providers, tests, fallback readers, or reconstruction logic
