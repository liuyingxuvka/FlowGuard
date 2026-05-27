# flowguard-structure-simplification Specification

## Purpose
TBD - created by archiving change simplify-flowguard-structure. Update Purpose after archive.
## Requirements
### Requirement: CLI Template Registration Preservation
FlowGuard SHALL reduce repeated template command registration without changing
the public command names, common `--output`/`--force` arguments, stdout JSON
template output, or template file write behavior.

#### Scenario: Template command stdout remains stable
- **WHEN** a user runs a supported `python -m flowguard <name>-template`
  command without `--output`
- **THEN** FlowGuard MUST emit the same JSON template envelope and template
  name as before the registration simplification.

#### Scenario: Template command output arguments remain stable
- **WHEN** a user asks for help or supplies `--output` and `--force` to a
  supported file-template command
- **THEN** FlowGuard MUST expose and accept the same arguments after the
  simplification.

### Requirement: Public Facade Compatibility
FlowGuard SHALL keep the broad `flowguard.__init__` facade and declared
`API_SURFACE` groups stable during the first structure simplification pass.

#### Scenario: Public imports remain available
- **WHEN** the API surface test iterates every name listed in `API_SURFACE`
- **THEN** each name MUST still be present in `flowguard.__all__` and as a
  package attribute.

### Requirement: Model-Backed Simplification Evidence
FlowGuard SHALL classify structure simplification candidates with explicit
Architecture Reduction proof status and required next route before treating a
candidate as safe to implement.

#### Scenario: Public entrypoint contraction requires parity route
- **WHEN** a candidate affects a public import, CLI command, or file-writing
  side effect
- **THEN** the candidate MUST require StructureMesh or conformance replay
  evidence before it can support a final done claim.

#### Scenario: Shadow artifact cleanup remains bounded
- **WHEN** a duplicate shadow-only `.flowguard` artifact is removed during sync
- **THEN** the cleanup MUST preserve peer-created OpenSpec and source work and
  MUST NOT be reported as package behavior evidence.

### Requirement: Dual Workspace And Install Verification
FlowGuard SHALL verify the Git checkout, editable install, and shadow workspace
after the simplification is implemented.

#### Scenario: Installed and shadow imports agree
- **WHEN** the editable install is refreshed from the Git checkout
- **THEN** import checks from both the Git checkout and shadow workspace MUST
  report the same FlowGuard schema and package version.

#### Scenario: Background regression has final artifacts
- **WHEN** a broad regression is run in the background
- **THEN** final confidence MUST wait for exit status and captured output files,
  not progress logs alone.
