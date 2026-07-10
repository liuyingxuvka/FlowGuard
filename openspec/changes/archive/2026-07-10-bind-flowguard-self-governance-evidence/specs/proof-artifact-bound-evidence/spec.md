## ADDED Requirements

### Requirement: Proof Artifacts Bind To Verification Inputs
A proof artifact used for governance SHALL bind to the contract hash, check-manifest hash, suite-map hash, producer/checker version, command, exit code, environment fingerprint, covered obligation ids, result fingerprint, and required input snapshots.

#### Scenario: Checker version changes
- **WHEN** the checker version differs from the version bound into an otherwise passing proof artifact
- **THEN** the proof is stale for current closure until rerun or an explicitly scoped reuse rule passes

### Requirement: Covered Obligations Are Explicit
Every proof artifact SHALL list the exact obligation ids it proves. A parent MUST NOT infer coverage from a command name, file path, task checkbox, or aggregate green status.

#### Scenario: Test command passes without obligation map
- **WHEN** a test run exits zero but its proof artifact lists no covered obligation ids
- **THEN** it remains diagnostic evidence and satisfies no required governance obligation

### Requirement: Raw And Semantic Hash Policies Are Declared
Each watched artifact SHALL declare whether raw byte equality, normalized semantic equality, or both are required. Semantic equality MUST NOT mask a raw mismatch where distribution parity requires identical bytes.

#### Scenario: Installed prompt differs only by line endings
- **WHEN** semantic content matches but raw bytes differ for an artifact requiring raw parity
- **THEN** distribution proof fails raw parity while reporting semantic equality separately
