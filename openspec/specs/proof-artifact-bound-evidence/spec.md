# proof-artifact-bound-evidence Specification

## Purpose
This capability defines FlowGuard's Proof Artifact Bound Evidence behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Proof artifact reference
FlowGuard SHALL provide a shared proof artifact reference that records the
artifact id, producer route, command identity, result path, status, exit code,
timestamps, artifact fingerprints, covered obligation ids, scope, and freshness
metadata for evidence consumed by confidence gates.

#### Scenario: Current passing artifact supports evidence
- **WHEN** evidence references a proof artifact with passing status, exit code
  zero, current artifact metadata, and matching covered obligation ids
- **THEN** strict evidence consumers SHALL treat the evidence as artifact-backed
  proof

#### Scenario: Missing artifact blocks strict evidence
- **WHEN** evidence has a caller-declared passing status but no proof artifact
  reference
- **THEN** strict evidence consumers SHALL report declaration-only evidence and
  SHALL NOT allow full confidence from that row

### Requirement: Proof artifact status wins over declaration
FlowGuard SHALL let strict evidence consumers compare caller-declared status
with proof artifact status and prefer the proof artifact when they disagree.

#### Scenario: Declared pass conflicts with failed artifact
- **WHEN** an evidence row declares `passed` but its proof artifact status is
  failed, stale, skipped, running, progress-only, not-run, or has non-zero exit
  code
- **THEN** the strict consumer SHALL block the evidence and report the status
  mismatch

### Requirement: Proof artifact freshness is explicit
FlowGuard SHALL distinguish current proof artifacts from stale, missing,
progress-only, internal-path-only, and route-gap evidence before final
confidence.

#### Scenario: Stale artifact is visible
- **WHEN** a proof artifact has stale reasons, route gap codes, missing result
  path, missing fingerprints required by the consumer, or non-current route
  evidence
- **THEN** the strict consumer SHALL report the proof artifact as stale or
  incomplete

### Requirement: Proof artifacts bind reused test result files
Proof artifact evidence SHALL serve as the concrete result artifact reference
for reused test evidence.

#### Scenario: Reused result has matching artifact fingerprint
- **WHEN** reused test evidence references a proof artifact with a result path
  and artifact fingerprints
- **AND** the test-result reuse ticket says the result fingerprint still matches
- **THEN** strict evidence consumers SHALL treat the proof artifact as the
  concrete reused result file

#### Scenario: Reused result has no artifact fingerprint
- **WHEN** reused test evidence has no proof artifact fingerprint
- **THEN** strict evidence consumers SHALL report the reused result as
  unsupported by concrete proof

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
