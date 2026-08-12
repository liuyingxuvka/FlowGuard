# validation-evidence-gates Specification

## Purpose
Define validation evidence gates for UI click-through, artifact payloads,
manual/native boundaries, installed prompt synchronization, and proof artifacts
so broad confidence cannot rest on planned, fake, stale, or incomplete checks.
## Requirements
### Requirement: Cross-route validation evidence gate
FlowGuard SHALL define a shared evidence gate for implemented UI actions,
external artifact payloads, AI work packages, conditional manual checks, and
final broad confidence claims.

#### Scenario: Claim includes UI or payload boundary
- **WHEN** a completion claim includes implemented UI behavior, file
  import/export, artifact payload parsing, generated output files, or AI work
  packages
- **THEN** the claim MUST identify route-owned evidence for that boundary or a
  scoped blindspot

#### Scenario: Prose-only validation is insufficient
- **WHEN** a claim relies on manual or browser validation without a current
  evidence id, boundary, steps or cases, result, and revision/freshness marker
- **THEN** FlowGuard MUST treat the claim as scoped or blocked rather than full
  confidence

### Requirement: Representative synthetic payload packs
FlowGuard SHALL require representative synthetic payload packs when artifact
payload behavior is part of a broad confidence claim.

#### Scenario: Payload cases are declared
- **WHEN** a file format, import/export flow, or AI work package is in scope
- **THEN** the evidence plan MUST name representative valid, empty or missing,
  malformed, unknown-field, old-version, round-trip, and boundary cases or
  state why a case is out of scope

#### Scenario: Payload pack is missing
- **WHEN** a payload-bearing claim has no current synthetic payload evidence
- **THEN** the claim MUST remain scoped or blocked until evidence exists

### Requirement: Conditional manual review gate
FlowGuard SHALL require manual evidence only for boundaries that automation
cannot inspect reliably.

#### Scenario: Native or external boundary is not automatable
- **WHEN** a native file picker, download target, clipboard, desktop shell,
  third-party login, system permission, or human visual judgment is required
- **THEN** the validation plan MUST include structured manual evidence or an
  explicit blindspot

#### Scenario: Automated evidence covers the boundary
- **WHEN** browser, desktop, replay, or test evidence fully covers the declared
  boundary
- **THEN** FlowGuard MUST NOT require extra manual review only for ceremony

### Requirement: Final confidence consumes UI and payload gates
FlowGuard final broad confidence SHALL consume UI action and artifact payload
gate evidence when those risks are in scope.

#### Scenario: Final claim lacks gate evidence
- **WHEN** a risk row names implemented UI or artifact payload behavior
- **AND** no current route evidence or scoped blindspot is attached
- **THEN** final confidence MUST be blocked or scoped

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
