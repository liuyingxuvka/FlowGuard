## ADDED Requirements

### Requirement: Same-intent validation inventories require complete current evidence
FlowGuard TestMesh SHALL treat the complete required inventory for a stable
business intent as the parent evidence boundary. The inventory SHALL include
every required same-intent surface, materialized model/test obligation, family
member, transition cell, contract-exhaustion case, and coverage shard routed to
TestMesh. A caller-selected subset or a broad parent command SHALL NOT support
green confidence for the complete inventory.

#### Scenario: Complete inventory has current child evidence
- **WHEN** every required inventory item is owned by a registered child suite or
  shard with current passing evidence for the same inventory revision
- **THEN** TestMesh MAY treat the inventory evidence boundary as current
- **AND** semantic coverage remains owned by the corresponding Model-Test
  Alignment, ObligationFamily, Primary Path Authority, or ContractExhaustionMesh
  reviewer

#### Scenario: Required inventory item is omitted
- **WHEN** a same-intent validation inventory omits a required surface,
  materialized obligation, family member, transition cell, case, or shard
- **THEN** TestMesh MUST report incomplete required inventory evidence
- **AND** the parent gate MUST NOT return full green confidence

#### Scenario: Locally green subset is not complete coverage
- **WHEN** all declared child suites pass but the declared inventory does not
  prove completeness against its required source inventory
- **THEN** TestMesh MUST keep the parent confidence blocked or scoped instead
  of promoting the locally green subset

#### Scenario: Inventory changes after evidence
- **WHEN** the required inventory revision changes after child or shard evidence
  was produced
- **THEN** TestMesh MUST mark the affected evidence stale and require current
  evidence for the revised inventory

### Requirement: Background regressions provide liveness until a final receipt passes
TestMesh SHALL record background regression progress as liveness only. A
background run MUST NOT satisfy current passing evidence until a final receipt
records the run identity, terminal status or exit code, result artifact,
artifact fingerprint, covered inventory or shard ids, and covered artifact and
verifier versions.

#### Scenario: Background regression is still running
- **WHEN** a background regression emits progress, logs, a process id, or a
  heartbeat but has no final receipt
- **THEN** TestMesh MUST report liveness without counting the run as passed
- **AND** done, release, archive, and publish confidence MUST remain unsupported
  by that run

#### Scenario: Final receipt is incomplete or non-passing
- **WHEN** a background run has a receipt that lacks a terminal result artifact,
  fingerprint, covered required ids, or passing terminal status
- **THEN** TestMesh MUST treat the run as incomplete, failed, or stale according
  to the receipt instead of treating prior progress as completion

#### Scenario: Current final receipt covers the complete inventory
- **WHEN** a final receipt has a passing terminal status and current proof for
  every required inventory item or shard under the current artifact versions
- **THEN** TestMesh MAY count the run as current passing evidence for that
  declared TestMesh boundary

