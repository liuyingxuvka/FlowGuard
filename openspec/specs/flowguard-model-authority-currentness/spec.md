# flowguard-model-authority-currentness Specification

## Purpose
Define how FlowGuard proves that one immutable observed model-system snapshot
matches the current software and how it repairs stale authority through a new
atomic revision without rewriting history.

## Requirements
### Requirement: FlowGuard has one valid observed model-system head

FlowGuard SHALL expose exactly one current observed snapshot whose source inventory, covered model owners, head fingerprint, and activation receipt agree.

#### Scenario: The live snapshot differs from the observed head

- **WHEN** model-system audit detects fingerprint or source-revision drift
- **THEN** the authority SHALL remain blocked until a native revision activation succeeds

### Requirement: Historical snapshots are immutable

FlowGuard SHALL repair authority by creating and activating a new revision while retaining every historical snapshot byte-for-byte.

#### Scenario: Repair is required

- **WHEN** the current head is stale
- **THEN** FlowGuard SHALL create and activate a new revision and SHALL NOT rewrite the historical snapshot
