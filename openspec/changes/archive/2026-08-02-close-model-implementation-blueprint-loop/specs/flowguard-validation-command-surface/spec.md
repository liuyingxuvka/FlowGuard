## ADDED Requirements

### Requirement: Blueprint command surfaces separate read-only checks from explicit export
The command surface SHALL provide a read-only implementation-inventory audit, a read-only model-blueprint check, and an explicitly invoked deterministic export. Read-only commands SHALL NOT write artifacts, publish evidence, change model authority, execute missing owners, or launch reconstruction. Export SHALL write only to the explicit bounded output path and SHALL verify its manifest and shards before success.

#### Scenario: Read-only blueprint check finds missing evidence
- **WHEN** a blueprint check lacks a required current binding or resource
- **THEN** it reports the exact incomplete or stale gap and performs no write or owner execution

#### Scenario: Explicit projection export succeeds
- **WHEN** the user supplies a current complete manifest and an allowed output path
- **THEN** the command writes deterministic content-addressed projection material and verifies every emitted reference

#### Scenario: Reconstruction receipt is omitted
- **WHEN** a blueprint check does not require empirical reconstruction and no reconstruction receipt is supplied
- **THEN** static closure is evaluated and empirical status remains not-run without launching work
