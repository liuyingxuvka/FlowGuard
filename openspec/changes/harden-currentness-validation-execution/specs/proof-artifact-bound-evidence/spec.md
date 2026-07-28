## MODIFIED Requirements

### Requirement: Proof artifact reference
FlowGuard SHALL provide a shared proof artifact reference that records the
artifact id, producer route, command identity, result path, declared status,
declared exit code, timestamps, artifact fingerprints, covered obligation ids,
scope, producer receipt id, and freshness metadata for evidence consumed by
confidence gates. The reference is descriptive only. A strict consumer MUST
resolve it to the loaded immutable producer receipt and result artifact and
MUST independently verify terminal status, exit code, fingerprints, inputs,
scope, obligations, and currentness before treating it as proof.

#### Scenario: Current passing artifact supports evidence
- **WHEN** evidence references a loaded producer receipt and result artifact
  whose independent verification passes with exit code zero, current inputs,
  matching fingerprints, and matching covered obligation ids
- **THEN** strict evidence consumers SHALL treat the evidence as
  artifact-backed proof

#### Scenario: Missing artifact blocks strict evidence
- **WHEN** evidence has a caller-declared passing status but no proof artifact
  reference or no resolvable immutable producer receipt
- **THEN** strict evidence consumers SHALL report declaration-only evidence and
  SHALL NOT allow full confidence from that row

### Requirement: Proof artifact status wins over declaration
FlowGuard SHALL require strict evidence consumers to prefer independently
verified producer-receipt and loaded-result status over both caller-declared
status and status fields stored in a proof reference.

#### Scenario: Declared pass conflicts with failed artifact
- **WHEN** an evidence row or proof reference declares `passed` but independent
  verification reports failed, stale, skipped, running, progress-only, not-run,
  a fingerprint mismatch, or non-zero exit code
- **THEN** the strict consumer SHALL block the evidence and report the status
  mismatch

#### Scenario: Reference says current without verification
- **WHEN** a proof reference declares itself current but has no successful
  independent receipt verification result
- **THEN** the strict consumer MUST treat the reference as unresolved rather
  than current proof

### Requirement: Proof artifacts bind reused test result files
Proof artifact evidence SHALL identify the concrete result artifact and
immutable producer receipt for reused test evidence. A strict consumer MUST
load the result, recompute the required fingerprint, and verify the receipt
against current inputs; a reuse-ticket match flag MUST NOT substitute for those
checks.

#### Scenario: Reused result has matching artifact fingerprint
- **WHEN** reused test evidence resolves to an immutable receipt and concrete
  result whose independently computed fingerprint and current inputs match
- **THEN** strict evidence consumers SHALL treat the loaded result as the
  concrete reused result file

#### Scenario: Reused result has no artifact fingerprint
- **WHEN** reused test evidence has no independently verifiable proof artifact
  fingerprint
- **THEN** strict evidence consumers SHALL report the reused result as
  unsupported by concrete proof

#### Scenario: Ticket self-reports a match
- **WHEN** a reuse ticket says the result matches but the loaded result or
  receipt does not match the frozen requirement
- **THEN** the strict consumer MUST reject the reuse

## ADDED Requirements

### Requirement: Planning routes never synthesize execution proof
Planning, projection, and compilation routes SHALL preserve exact existing
proof and receipt references without changing their identities. They MUST NOT
create a proof artifact, producer receipt, result fingerprint, terminal status,
exit code, currentness result, supersession result, or verification result from
plan text, expected outcomes, task state, or caller declarations.

#### Scenario: A plan says that validation passed
- **WHEN** a plan row declares a passing status, result path, or expected exit
  code without loaded producer evidence
- **THEN** downstream evidence MUST remain missing or planned
- **AND** no proof artifact or currentness result may be synthesized

#### Scenario: A plan contains an exact proof reference
- **WHEN** a planner receives an existing proof or receipt id and fingerprint
- **THEN** it MUST project those values unchanged for later independent
  verification and MUST NOT mark them current

