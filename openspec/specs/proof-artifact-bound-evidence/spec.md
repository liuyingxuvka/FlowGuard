# proof-artifact-bound-evidence Specification

## Purpose
TBD - created by archiving change require-proof-artifact-bound-evidence. Update Purpose after archive.
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
