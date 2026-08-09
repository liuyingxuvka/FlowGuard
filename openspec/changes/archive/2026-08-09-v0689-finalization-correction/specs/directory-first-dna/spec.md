## Purpose

This capability makes the canonical FlowGuard model directory a practical,
exchangeable software-DNA representation while keeping transport envelopes,
execution evidence, and optional experiments separate from model authority.

## ADDED Requirements

### Requirement: Canonical model directory is the DNA representation

FlowGuard SHALL expose the exact current canonical model directory, its
manifest, child shards, parent/child relations, code bindings, test bindings,
and explicit evidence statuses as the exchangeable DNA representation. The
directory SHALL be derived from one current blueprint and SHALL NOT be a
second model authority.

#### Scenario: Directory export succeeds

- **WHEN** a current blueprint is canonically qualified and exported to an
  empty bounded directory
- **THEN** FlowGuard writes exactly one manifest and its declared content-
  addressed shards, returns the directory and tree fingerprints, and reports
  the model, code, test, and evidence identities used for the export

#### Scenario: Unqualified blueprint is rejected

- **WHEN** a caller requests a directory export while a required model,
  binding, or evidence layer is stale, missing, or blocked
- **THEN** FlowGuard refuses to write a partial replacement and returns the
  typed blocker without substituting a fallback projection

### Requirement: Directory verification is exact and bounded

FlowGuard SHALL verify the directory manifest, shard paths, member identities,
content fingerprints, parent/child links, and tree fingerprint without loading
production source or executing target software. Unknown files, duplicate
shards, path escapes, stale fingerprints, duplicate JSON keys, and non-finite
numbers SHALL be visible failures.

#### Scenario: Exact directory verifies

- **WHEN** the directory contains only the manifest and the declared shards
  with unchanged bytes
- **THEN** verification returns a terminal complete result tied to the same
  blueprint and projection fingerprints

#### Scenario: Directory tampering blocks

- **WHEN** a shard is changed, duplicated, removed, or an unrelated file is
  added
- **THEN** verification returns blocked with the exact affected shard or path
  and does not reinterpret the directory through a compatibility reader

### Requirement: Monolithic transport is optional

FlowGuard SHALL allow a single-file transport envelope only as an explicitly
requested derived artifact. Normal modeling, reading, authority selection, and
exchange SHALL work from the directory and SHALL NOT require materializing a
complete duplicate bundle in memory or on disk.

#### Scenario: Directory-first consumer

- **WHEN** an AI or tool exchanges the DNA for another target
- **THEN** it can consume the manifest and selected shards from the directory
  and preserve omitted members and not-run evidence as explicit bounded
  statuses

#### Scenario: Explicit bundle request

- **WHEN** a caller explicitly requests a single-file bundle
- **THEN** FlowGuard creates it as a derived transport projection, records the
  source directory fingerprint, and does not promote the bundle to authority

### Requirement: Claims remain separated

The directory verification result SHALL distinguish static model integrity,
portable integrity, current executed evidence, and optional user-requested
experiments. A successful directory check SHALL NOT claim that the target was
rebuilt, translated, or executed.

#### Scenario: Not-run evidence stays visible

- **WHEN** a model/test binding is structurally complete but its execution
  receipt is not current
- **THEN** the directory remains exchangeable while the binding status remains
  `not_run` or `gap`, and no parent result relabels it as passed
