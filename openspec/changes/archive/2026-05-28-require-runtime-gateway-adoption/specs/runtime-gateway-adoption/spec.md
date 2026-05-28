# runtime-gateway-adoption Specification

## Purpose

Define when FlowGuard is only design/test evidence versus when it is actually
connected to runtime state mutation gates.

## ADDED Requirements

### Requirement: Adoption levels are explicit

FlowGuard SHALL provide public adoption-level constants for `design_model`,
`test_aligned`, and `runtime_gateway`, and SHALL let a review plan declare the
target level being claimed.

#### Scenario: Design-only model remains valid
- **WHEN** a plan declares `design_model`
- **THEN** FlowGuard SHALL NOT require runtime gateway contracts or writer
  observations
- **AND** the report SHALL NOT claim runtime-gateway protection

#### Scenario: Runtime gateway level is stricter
- **WHEN** a plan declares `runtime_gateway`
- **THEN** FlowGuard SHALL require complete critical-state writer inventory,
  managed state surfaces, gateway-mediated write observations, and current
  evidence bindings

### Requirement: Critical state surfaces require gateway ownership

FlowGuard SHALL let projects declare critical state surfaces and the gateway
contracts that own those surfaces for runtime mutation.

#### Scenario: Critical surface has no gateway
- **WHEN** a critical state surface has no owner gateway
- **AND** the plan claims `runtime_gateway`
- **THEN** the review SHALL report a blocker for the unmanaged state surface

#### Scenario: Surface references unknown gateway
- **WHEN** a state surface references a gateway id that is not declared
- **THEN** the review SHALL report an unknown gateway owner finding

### Requirement: Complete writer inventory is required for runtime-gateway claims

FlowGuard SHALL require a current writer inventory evidence id before a plan can
claim that every critical write path has been reviewed.

#### Scenario: Missing inventory evidence
- **WHEN** a plan claims `runtime_gateway`
- **AND** no complete writer inventory evidence id is supplied
- **THEN** the review SHALL block runtime-gateway adoption

### Requirement: Direct critical-state writes block runtime-gateway adoption

FlowGuard SHALL treat every current write observation to a critical state
surface as blocked unless it is mediated by a declared gateway that manages the
target surface.

#### Scenario: Direct write bypasses gateway
- **WHEN** a current passing write observation writes a critical state surface
  directly
- **THEN** the review SHALL report `direct_state_write_bypasses_gateway`
- **AND** runtime-gateway adoption SHALL NOT be OK

#### Scenario: Declared legacy bypass remains blocking
- **WHEN** a write observation declares a legacy bypass reason
- **THEN** the review SHALL keep the bypass visible
- **AND** runtime-gateway adoption SHALL remain blocked rather than treating the
  bypass as green

#### Scenario: Gateway writes unmanaged surface
- **WHEN** a write observation names a gateway
- **AND** that gateway does not manage the target state surface
- **THEN** the review SHALL report a gateway surface mismatch

### Requirement: Gateway writes must bind to current FlowGuard evidence

FlowGuard SHALL let gateway contracts require step-contract ids, code-boundary
ids, replay observation proof, and proof artifacts for each mediated write.

#### Scenario: Gateway write lacks step contract evidence
- **WHEN** a gateway requires step-contract binding
- **AND** a write observation through that gateway has no step contract ids
- **THEN** the review SHALL report missing step-contract evidence

#### Scenario: Gateway write lacks code-boundary evidence
- **WHEN** a gateway requires code-boundary binding
- **AND** a write observation through that gateway has no code-boundary ids
- **THEN** the review SHALL report missing code-boundary evidence

#### Scenario: Gateway write lacks proof artifact
- **WHEN** a gateway requires proof artifacts
- **AND** a write observation through that gateway has no proof artifact ids
- **THEN** the review SHALL report missing proof-artifact evidence

### Requirement: Stale or non-passing writer observations do not prove adoption

FlowGuard SHALL reject stale, skipped, failed, timeout, not-run, running, or
error writer observations as runtime-gateway adoption evidence.

#### Scenario: Stale writer observation
- **WHEN** a write observation is not current
- **THEN** the review SHALL report a stale writer observation finding

#### Scenario: Non-passing writer observation
- **WHEN** a write observation has a non-passing status
- **THEN** the review SHALL report a non-passing writer observation finding

### Requirement: Runtime gateway adoption report is structured

FlowGuard SHALL return a structured report with status, decision, findings,
surfaces, gateways, observations, adoption level, and a concise text formatter.

#### Scenario: Complete runtime gateway adoption passes
- **WHEN** every critical surface is managed, inventory evidence is present,
  every current write is mediated by the correct gateway, and required evidence
  ids are present
- **THEN** the report SHALL be OK
- **AND** the decision SHALL be `runtime_gateway_adoption_green`
