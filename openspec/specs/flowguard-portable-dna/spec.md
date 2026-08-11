# FlowGuard Native DNA Specification

## Purpose

Define the provider-neutral, content-addressed model records that live in a
target repository's native directory. The model directory, its code/test
bindings, and its current Git identity are the DNA. There is no second portable
bundle authority and no routine materialization step.

## Requirements

### Requirement: Native model records are content-addressed

The system SHALL preserve model hierarchy, interfaces, states, transitions,
outputs, intent, resources, implementation bindings, test/oracle bindings,
readiness results, and exact source/provider identities in the native model
directory. Each record SHALL be addressable by its current fingerprint and
reachable from the project pointer.

#### Scenario: Native hierarchy remains addressable
- **WHEN** a parent model is audited with its child models, interfaces, bindings, and evidence
- **THEN** every required record SHALL be reachable from the native pointer
- **AND** the audit SHALL expose the current record fingerprints

### Requirement: Native DNA qualification is in-place

- **WHEN** a caller requests DNA status
- **THEN** the check SHALL read the current directory, pointer chain, and
  binding records, return static/semantic/code/test/execution status separately,
  and write no duplicate artifact

#### Scenario: Repeated audit is read-only
- **WHEN** the same native directory is audited twice without a source change
- **THEN** both audits SHALL report the same native identity and status
- **AND** neither audit SHALL create a second DNA file or directory

### Requirement: Incomplete native DNA fails visibly

- **WHEN** a required layer is missing, stale, candidate, untracked, or blocked
- **THEN** the status SHALL retain the exact gap and SHALL NOT report a qualified
  DNA or select an alternate reader, provider, bundle, or fallback

#### Scenario: Missing child binding is visible
- **WHEN** a child model has no current code or test binding
- **THEN** the audit SHALL report the missing binding as a typed gap
- **AND** the parent SHALL NOT be marked qualified through a fallback

### Requirement: Standalone portable routes are forbidden

Requests for a single-file bundle, copied model directory, transport envelope,
portable materialization, isolated import, or reconstruction SHALL return the
typed `native_directory_only` result. No such route may write a file or become
an authority.

#### Scenario: Retired export is rejected
- **WHEN** a caller requests a standalone DNA export or copied-directory route
- **THEN** the command SHALL return `native_directory_only`
- **AND** the requested output path SHALL remain unchanged

### Requirement: Provider-neutral semantics remain separate from language

The model schema SHALL support software, non-code workflows, experiments, and
other behavior-bearing systems. A language or runtime is an adapter detail and
is never a semantic or qualification shortcut.

#### Scenario: Non-Python target uses the same native contract
- **WHEN** a TypeScript program, experiment, or non-code workflow supplies its native models and evidence
- **THEN** the same hierarchy, binding, and readiness contract SHALL apply
- **AND** no Python-specific field SHALL be required
