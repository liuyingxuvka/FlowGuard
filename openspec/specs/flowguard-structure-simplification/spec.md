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
`API_SURFACE` groups stable during structure simplification, and SHALL derive
`flowguard.__all__` from those groups plus a small explicit public supplement
instead of maintaining a second full duplicate export list.

#### Scenario: Public imports remain available
- **WHEN** the API surface test iterates every name listed in `API_SURFACE`
- **THEN** each name MUST still be present in `flowguard.__all__` and as a
  package attribute.

#### Scenario: Public export snapshot remains stable
- **WHEN** the facade export declaration is simplified
- **THEN** the set of public names in `flowguard.__all__` MUST match the
  pre-simplification export set.

#### Scenario: Supplement exports stay explicit
- **WHEN** a public name is intentionally exported but is not part of an
  `API_SURFACE` group
- **THEN** it MUST be listed in the explicit export supplement and covered by
  an API-surface test.

### Requirement: Model-Backed Simplification Evidence
FlowGuard SHALL classify structure simplification candidates with explicit
Architecture Reduction proof status, required next route, and lifecycle
disposition before treating a candidate as safe to implement or safe to close.

#### Scenario: Public entrypoint contraction requires parity route
- **WHEN** a candidate affects a public import, CLI command, or file-writing
  side effect
- **THEN** the candidate MUST require StructureMesh or conformance replay
  evidence before it can support a final done claim

#### Scenario: Shadow artifact cleanup remains bounded
- **WHEN** a duplicate shadow-only `.flowguard` artifact is removed during sync
- **THEN** the cleanup MUST preserve peer-created OpenSpec and source work and
  MUST NOT be reported as package behavior evidence

#### Scenario: Completed simplification is not re-queued
- **WHEN** a simplification model observes that the target code already matches
  the approved smaller structure and current validation evidence exists
- **THEN** the model MUST keep the simplification visible as completed evidence
  or history rather than returning it as a new ready candidate

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

### Requirement: Redundant compatibility fields may be removed
FlowGuard SHALL allow structure simplification to remove redundant compatibility
fields when a clearer replacement preserves the represented behavior and
validation evidence.

#### Scenario: Repeated ids are replaced by a typed handoff
- **WHEN** multiple downstream route dataclasses repeat model-similarity
  relation, maintenance-group, change-impact, test-obligation, or
  code-obligation id fields
- **THEN** FlowGuard MAY replace those fields with a single typed handoff
- **AND** tests MUST prove the same route findings, warnings, and blockers are
  still produced through the new structure

#### Scenario: Compatibility removal is released
- **WHEN** a redundant public field is removed during a cleanup
- **THEN** changelog and version records MUST mark the cleanup as an
  intentional breaking surface change for the local 0.x version
- **AND** the full capability behavior MUST remain covered by current tests

### Requirement: Handoff cleanup keeps route ownership explicit
FlowGuard SHALL keep route ownership visible after replacing repeated fields
with a handoff object.

#### Scenario: Downstream route consumes similarity provenance
- **WHEN** Existing Model Preflight, Code Structure Recommendation,
  Model-Test Alignment, or Architecture Reduction consumes model-similarity
  evidence
- **THEN** the route MUST read the typed handoff and emit route-specific
  findings rather than treating similarity as proof by itself

