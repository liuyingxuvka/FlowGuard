## MODIFIED Requirements

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
