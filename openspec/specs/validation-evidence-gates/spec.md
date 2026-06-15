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
