# directory-first-dna Specification

## Purpose

The native, versioned model directory is the software/object DNA. It includes
the model files, parent/child relations, input/output/state/effect contracts,
code and test bindings, evidence pointers, and the source revision that owns
them. DNA is inspected where it lives; FlowGuard does not create a second DNA
file, copied directory, transport bundle, or isolated materialization.

## Requirements

### Requirement: Native model directory is the only DNA representation

FlowGuard SHALL inspect the exact current canonical model directory and its
Git-bound files as the DNA representation. The directory SHALL remain the
single authority and SHALL include model, code, test, oracle, resource,
parent/child, and evidence identities needed for the declared boundary.

#### Scenario: Native directory is current

- **WHEN** the current project pointer resolves to a tracked model directory
  and every required model/code/test/evidence identity is current
- **THEN** the in-place audit returns the directory fingerprint, depth, counts,
  and exact binding statuses without writing another artifact

#### Scenario: Native directory is incomplete

- **WHEN** a required model, binding, or evidence layer is stale, missing,
  untracked, or blocked
- **THEN** the audit returns the typed gap and does not copy, export, or replace
  the directory with a partial projection

### Requirement: In-place verification is exact and bounded

FlowGuard SHALL verify the native directory manifest, pointer chain, member
identities, content fingerprints, parent/child links, code/test/oracle bindings,
and source revision without loading target software or executing a reconstruction.
Unknown files, duplicate members, path escapes, stale fingerprints, duplicate
JSON keys, and non-finite numbers SHALL be visible failures.

#### Scenario: Native directory verifies

- **WHEN** the current directory contains only its declared native files and
  all identities close
- **THEN** verification returns a terminal result tied to the same source and
  model fingerprints

#### Scenario: Native directory is tampered

- **WHEN** a model, binding, pointer, or test identity is changed, removed, or
  duplicated
- **THEN** verification returns blocked with the exact affected path or ID and
  does not reinterpret it through a compatibility reader

### Requirement: Standalone DNA artifact routes are retired

The product SHALL reject requests to write or verify a standalone DNA file,
copied DNA directory, transport bundle, portable materialization, or isolated
import. These are not alternate authorities and are not optional normal-use
transport paths.

#### Scenario: Standalone artifact is requested

- **WHEN** a caller invokes an old bundle/export/materialization route
- **THEN** FlowGuard returns a typed `native_directory_only` failure, writes no
  output, and leaves model authority unchanged

### Requirement: Claims remain separated

The native-directory verification result SHALL distinguish static model
integrity, code/test binding currentness, current executed evidence, and
optional user-requested experiments. A successful in-place check SHALL NOT
claim that the target was rebuilt, translated, or executed.

#### Scenario: Not-run evidence stays visible

- **WHEN** a model/test binding is structurally complete but its execution
  receipt is not current
- **THEN** the native directory remains the DNA authority while the binding
  status remains `not_run` or `gap`, and no parent result relabels it as passed
