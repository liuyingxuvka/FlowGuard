## Purpose

Provide one portable, content-addressed representation of a current FlowGuard blueprint so an authorized consumer can copy, verify, and rebind the model without treating source code or a second package format as blueprint authority.

## ADDED Requirements

### Requirement: The current blueprint can be exported as one portable bundle
The system SHALL export the current observed target blueprint as one content-addressed bundle containing a manifest, referenced shards, model hierarchy, parent-child interfaces, inputs, states, transitions, outputs, intent, resources, implementation bindings, test/oracle bindings, readiness results, and exact source/provider identities.

#### Scenario: Export uses the current observed authority
- **WHEN** a caller requests a portable export
- **THEN** the export SHALL consume the sole current observed implementation head, accepted model revision, complete effective intent view, and frozen provider artifacts
- **AND** a target, experiment, history, or caller-supplied fingerprint SHALL NOT become the bundle authority

#### Scenario: A required layer is missing
- **WHEN** a required model, interface, resource, implementation, test, oracle, intent, or readiness member is absent or stale
- **THEN** the export SHALL fail visibly with the exact missing identity and SHALL NOT emit a ready portable status

### Requirement: A copied bundle verifies without the source repository
The system SHALL verify a copied portable bundle using only its manifest, content-addressed shards, declared provider/toolchain identities, and rebind contract.

#### Scenario: Bundle is copied to an isolated directory
- **WHEN** all declared shards are copied without the original repository's blueprint files
- **THEN** verification SHALL recompute the bundle identity, resolve every parent-child and layer reference, and return pass only when all references close

#### Scenario: A shard is changed or missing
- **WHEN** a shard is missing, changed, duplicated, or points to another subject revision
- **THEN** verification SHALL return a visible failure and SHALL not fall back to a whole report, alternate shard format, or source repository

### Requirement: Portable export has a separate readiness status
The system SHALL report `static-ready`, `exported-portable`, or an explicit non-pass status as separate claims; static readiness SHALL NOT imply portable export readiness.

#### Scenario: Static blueprint is complete but no bundle exists
- **WHEN** all static layers are current but no verified portable bundle was materialized
- **THEN** the result SHALL remain `static-ready` and SHALL report portable export as not run or incomplete

#### Scenario: Portable bundle verifies
- **WHEN** a bundle has current identity, complete shards, and successful isolated verification
- **THEN** the result SHALL report `exported-portable` in addition to the underlying static status
