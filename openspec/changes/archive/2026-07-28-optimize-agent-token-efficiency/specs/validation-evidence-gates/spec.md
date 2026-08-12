## ADDED Requirements

### Requirement: Terminal validation output is compact and artifact-backed
Validation aggregators SHALL emit a compact terminal envelope by default while
preserving complete canonical results and complete captured streams in
immutable result artifacts.

#### Scenario: Every child passes
- **WHEN** a validation aggregation completes successfully
- **THEN** terminal output SHALL include status, counts, run and result
  identities, result path and hash, and zero non-pass child ids without
  embedding successful child stdout or duplicate parsed payloads

#### Scenario: A child does not pass
- **WHEN** a child is failed, blocked, stale, skipped, timed out, cancelled, or
  not run
- **THEN** the terminal envelope SHALL identify that child and preserve a
  bounded diagnostic plus the complete result-artifact reference

#### Scenario: Full evidence is needed
- **WHEN** a consumer needs successful child details
- **THEN** it SHALL read the referenced canonical result artifact rather than
  invoke an alternate verbose success authority

### Requirement: Successful diagnostics do not duplicate streams
Persistent evidence receipts SHALL retain complete deterministic stream
sidecars but SHALL NOT copy a success-tail diagnostic into every nested result
row.

#### Scenario: Producer exits successfully
- **WHEN** complete stdout and stderr objects have been stored and fingerprinted
- **THEN** the bounded receipt diagnostic MAY be empty and SHALL preserve the
  object identities needed for audit

### Requirement: Parallel model execution is proof-gated
An isolated-output model regression SHALL be marked shard-safe only when a
current executable proof demonstrates serial/parallel semantic equivalence,
disjoint artifact ownership, stable input identities, and zero shared
repository mutation.

#### Scenario: The UI aggregate is proposed for parallel execution
- **WHEN** its manifest entry changes to `shard_safe=true`
- **THEN** the entry SHALL identify a machine-checkable proof contract and the
  proof SHALL run one serial baseline plus at least two simultaneous isolated
  copies

#### Scenario: A concurrent copy changes shared state
- **WHEN** the proof observes a repository mutation, overlapping output path,
  changed input fingerprint, non-terminal child, or semantic mismatch
- **THEN** the proof SHALL fail and the model SHALL remain ineligible for
  parallel regression execution

#### Scenario: The proof passes
- **WHEN** every copy passes with equivalent projected results, disjoint
  artifacts, current inputs, and no repository mutation
- **THEN** the receipt SHALL bind the model id, proof contract, source
  fingerprint, result projections, and claim boundary for the current release
