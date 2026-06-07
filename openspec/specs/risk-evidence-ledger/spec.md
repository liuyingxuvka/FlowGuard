# risk-evidence-ledger Specification

## Purpose
This capability defines FlowGuard's Risk Evidence Ledger behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Risk evidence rows bind model, code, and proof evidence

FlowGuard SHALL provide a risk evidence ledger that records each user-meaningful
risk with its model obligation owner, optional public code contract, proof
evidence, freshness state, and disposition.

#### Scenario: Complete risk evidence row
- **WHEN** a required risk row has a model obligation, a required code contract
  when code is in scope, current passing external proof evidence, and no stale
  or skipped blockers
- **THEN** the ledger review reports that row as fully supported

#### Scenario: Missing model obligation
- **WHEN** a required risk row has proof evidence but no model obligation owner
- **THEN** the ledger review reports a model coverage gap instead of treating
  the passing proof evidence as full FlowGuard confidence

#### Scenario: Missing code contract
- **WHEN** production code is in scope and a required risk row has no public
  code contract owner
- **THEN** the ledger review reports a code contract gap

#### Scenario: Missing proof evidence
- **WHEN** a required risk row has a model obligation and code contract but no
  current passing test, replay, or accepted manual evidence
- **THEN** the ledger review reports a proof evidence gap

### Requirement: Evidence freshness and scope affect confidence
FlowGuard SHALL distinguish current proof evidence from stale, skipped,
progress-only, internal-path-only, not-run, declaration-only, missing-artifact,
and explicitly out-of-scope evidence before full confidence is claimed.

#### Scenario: Stale evidence blocks full confidence
- **WHEN** a risk row's proof evidence is stale or covers an older artifact
  version
- **THEN** the ledger review reports stale evidence and does not return full
  confidence

#### Scenario: Declaration-only evidence blocks strict full confidence
- **WHEN** strict ledger proof is required and a risk row's passing evidence
  does not include a current proof artifact reference
- **THEN** the ledger review reports declaration-only evidence and does not
  return full confidence

#### Scenario: Internal-path-only proof is not external proof
- **WHEN** a risk row's proof evidence only exercises an internal helper or
  implementation path while a public code contract is required
- **THEN** the ledger review reports internal-path-only evidence

### Requirement: Ledger consumes route-specific evidence without replacing routes

FlowGuard SHALL let ledger rows reference evidence produced by Model-Test
Alignment, TestMesh, ModelMesh, DevelopmentProcessFlow, Model-Miss Review,
conformance replay, ordinary tests, or manual validation without replacing
those routes' own checks.

#### Scenario: Model-Test Alignment handoff
- **WHEN** a ledger row references a Model-Test Alignment report that found
  missing code-contract test evidence
- **THEN** the ledger review keeps that gap visible in the final confidence
  decision

#### Scenario: TestMesh handoff
- **WHEN** a ledger row relies on a parent test gate whose child evidence is
  stale, skipped, or release-only
- **THEN** the ledger review reports the proof evidence as not fully current

#### Scenario: ModelMesh handoff
- **WHEN** a ledger row relies on child model evidence that the parent has not
  consumed or reattached
- **THEN** the ledger review reports a parent model evidence gap

### Requirement: Adoption records include ledger summaries

FlowGuard adoption evidence SHALL be able to include a risk evidence ledger
summary that records fully supported risks, partial risks, scoped-out risks,
and required next actions.

#### Scenario: Completed adoption with partial confidence
- **WHEN** model checks and tests pass but one required risk row has no current
  external proof evidence
- **THEN** the adoption record can be completed only as scoped or partial
  confidence and must list the missing evidence as a next action

#### Scenario: Completed adoption with full confidence
- **WHEN** every required in-scope risk row is fully supported and evidence is
  current
- **THEN** the adoption record may claim full confidence for the declared
  ledger boundary

### Requirement: Risk rows can require family parity gates

Risk Evidence Ledger SHALL let a risk row require a current family parity gate before full confidence is granted.

#### Scenario: Missing family gate blocks confidence
- **WHEN** a required risk row declares that a family parity gate is required
- **AND** no family gate id is present
- **THEN** the ledger reports a missing family gate finding.

#### Scenario: Blocked family gate blocks confidence
- **WHEN** a required risk row references a family gate with blocked confidence
- **THEN** the ledger blocks full confidence for that risk.

#### Scenario: Scoped family gate remains scoped
- **WHEN** a required risk row references a family gate with scoped or partial confidence
- **THEN** the ledger reports scoped confidence
- **AND** if scoped confidence is not allowed, the ledger blocks the claim.

### Requirement: Risk rows can require analogous defect scan gates

Risk Evidence Ledger SHALL let a risk row require a current analogous defect scan before full confidence is granted after a model miss.

#### Scenario: Missing analogous scan blocks confidence
- **WHEN** a required risk row declares that an analogous defect scan is required
- **AND** no analogous scan id is present
- **THEN** the ledger reports a missing analogous scan finding.

#### Scenario: Blocked analogous scan blocks confidence
- **WHEN** a required risk row references an analogous defect scan with blocked confidence
- **THEN** the ledger blocks full confidence for that risk.

#### Scenario: Scoped analogous scan remains scoped
- **WHEN** a required risk row references an analogous defect scan with scoped or partial confidence
- **THEN** the ledger reports scoped confidence
- **AND** if scoped confidence is not allowed, the ledger blocks the claim.

### Requirement: Self-maintenance final claim boundary
Risk Evidence Ledger SHALL surface self-maintenance gaps, stale evidence, unsupported route claims, install sync gaps, shadow workspace gaps, and local git limitations before final broad confidence.

#### Scenario: Install sync not verified
- **WHEN** source changes are complete but editable install, import path, metadata version, feature availability, or shadow workspace sync is not verified
- **THEN** the ledger SHALL block or scope the final release/install confidence claim

### Requirement: Risk ledger consumes model-angle evidence
Risk Evidence Ledger SHALL consume model-angle review evidence when a final
claim relies on the agent having considered additional model angles.

#### Scenario: Model-angle review is required but unnamed
- **WHEN** a risk row requires model-angle review
- **AND** no model-angle evidence id is named
- **THEN** the ledger MUST report missing model-angle review before full confidence

#### Scenario: Model-angle review is not current or not full
- **WHEN** a named model-angle review is stale, scoped, partial, or blocked
- **THEN** the ledger MUST keep the claim scoped or blocked rather than treating the review as full evidence

### Requirement: Risk ledger consumes relevant open maintenance obligations
Risk Evidence Ledger SHALL consider relevant unresolved maintenance obligations
before granting broad done, release, publish, archive, production, or full
confidence claims.

#### Scenario: Relevant open obligation blocks or scopes full confidence
- **WHEN** a risk ledger row or plan references an unresolved open obligation
  for the same risk, model, code contract, proof evidence, public entrypoint, or
  route boundary
- **THEN** `review_risk_evidence_ledger(...)` MUST block or scope full
  confidence according to the ledger scoped-confidence policy
- **AND** the finding MUST identify the open obligation

#### Scenario: Irrelevant obligation does not affect row
- **WHEN** an open obligation is anchored to a different model, code contract,
  public entrypoint, or out-of-scope artifact
- **THEN** the ledger MUST NOT use that obligation to block the unrelated risk
  row

#### Scenario: Resolved obligation needs current proof
- **WHEN** a ledger row relies on a resolved obligation
- **THEN** the resolved obligation MUST have current owner-route evidence or an
  explicit scoped disposition
- **AND** stale, missing, declaration-only, or progress-only resolution evidence
  MUST NOT support full confidence

### Requirement: Risk ledger consumes topology hazard review evidence

FlowGuard SHALL allow each final-risk row to require a current model-topology
hazard review before broad done, release, publish, archive, or full-confidence
claims.

#### Scenario: Required topology hazard review is missing

- **GIVEN** a `RiskEvidenceRow` marks topology hazard review as required
- **WHEN** no topology hazard review id is present
- **THEN** `review_risk_evidence_ledger(...)` MUST block the broad risk claim
- **AND** it MUST report `missing_topology_hazard_review`.

#### Scenario: Blocked or scoped topology hazard evidence remains visible

- **GIVEN** a required topology hazard review id is present
- **WHEN** the review is stale, blocked, or scoped
- **THEN** the risk ledger MUST report the corresponding topology hazard
  finding
- **AND** full confidence MUST be blocked or downgraded according to ledger
  scoped-confidence policy.

