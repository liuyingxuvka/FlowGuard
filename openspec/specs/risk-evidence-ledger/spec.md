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

### Requirement: Human-operability risks require explicit evidence gates
RiskEvidenceLedger SHALL support a human-operability gate for UI risks where
confusing affordance, missing task coverage, ambiguous action grammar, missing
dialog return, missing keyboard/focus behavior, or failed walkthrough evidence
can invalidate a broad UI claim.

#### Scenario: Required risk has no operability proof
- **WHEN** a required UI risk depends on human-operability
- **AND** no current task coverage, affordance, action grammar, dialog,
  keyboard, or walkthrough proof is linked
- **THEN** the risk ledger blocks broad UI done/release confidence

### Requirement: Risk ledger consumes UI source-baseline evidence
RiskEvidenceLedger SHALL support a generic UI source-baseline interaction gate for source-based UI risks where missing source inventory, unapproved target drift, missing interaction branches, no-handler controls, or observed-source mismatch can invalidate a broad UI claim.

#### Scenario: Source-based UI risk lacks baseline proof
- **WHEN** a required UI risk depends on source-based parity or approved source differences
- **AND** no current source-baseline, target mapping, or observed-source alignment evidence is linked
- **THEN** the risk ledger blocks broad UI done/release confidence

#### Scenario: Source-baseline gate is blocked
- **WHEN** a required UI risk references a blocked or stale source-baseline interaction gate
- **THEN** the risk ledger blocks or scopes the risk according to the ledger confidence policy

### Requirement: Risk ledger uses generic source-baseline gate names
RiskEvidenceLedger SHALL use generic source-baseline gate constants and findings in public APIs, docs, and templates.

#### Scenario: Risk gate names one source technology
- **WHEN** a current risk gate constant, finding code, docs row, or template names one source technology as the generic UI source evidence gate
- **THEN** the risk ledger surface is incomplete until the name is generalized

### Requirement: Risk evidence ledger consumes business path evidence
Risk evidence ledger closure SHALL allow final confidence rows to depend on
current business-path topology and runtime evidence when path duplication,
conflict, old-path disposition, or wrong-path runtime proof can affect the
claim.

#### Scenario: Missing business path hazard review limits confidence
- **WHEN** a final claim depends on a path-sensitive workflow and business-path topology review is missing, stale, or blocked
- **THEN** the risk evidence ledger records the gap and limits or blocks broad confidence

#### Scenario: Current business path evidence supports closure
- **WHEN** topology hazard review and runtime path evidence both bind to the expected business path
- **THEN** the risk evidence ledger can use those current evidence rows to support final closure

### Requirement: Risk ledger consumes UI functional capability coverage
RiskEvidenceLedger SHALL provide a UI functional capability coverage gate for final UI done, release, or runnable-confidence claims.

#### Scenario: Capability gate supports confidence
- **WHEN** every in-scope required UI capability has current coverage, output contract evidence, implementation binding evidence, and accepted scope boundaries
- **THEN** the risk ledger may treat UI capability coverage as supporting evidence for the declared UI claim

#### Scenario: Capability gate is missing or scoped
- **WHEN** the UI capability coverage gate is missing, stale, failed, planned-only, or scoped below the final claim
- **THEN** the risk ledger blocks or scopes final UI confidence instead of accepting visible-control or screenshot evidence alone

### Requirement: Final UI confidence consumes real-surface and implementation evidence
Risk Evidence Ledger SHALL require broad UI done, release, or full-confidence
claims to consume current observed-surface inventory, UI implementation
validation, functional-chain, source-baseline interaction evidence when relevant, and
final done-claim review evidence.

#### Scenario: Ledger has current UI evidence
- **WHEN** a broad UI claim has current passing real-surface inventory,
  implementation validation, functional-chain, and done-claim evidence
- **THEN** the risk ledger may support full UI confidence if no other in-scope
  risk gate blocks

#### Scenario: Ledger lacks UI implementation validation
- **WHEN** a broad UI claim lacks current `UIImplementationValidation`
- **THEN** the risk ledger blocks or scopes the claim even if labels, APIs, or
  static tests exist

#### Scenario: Planned evidence cannot support ledger confidence
- **WHEN** UI evidence is marked planned, not-run, running, stale, skipped, or
  progress-only
- **THEN** the risk ledger cannot count it as passing evidence

### Requirement: Final risk evidence consumes UI and payload gates
RiskEvidenceLedger SHALL require current proof or route-gate evidence for UI
action and artifact payload risks before full confidence.

#### Scenario: UI risk lacks click-through proof
- **WHEN** a final risk row depends on implemented UI behavior
- **AND** no current UI implementation validation proof or scoped blindspot is
  attached
- **THEN** the ledger MUST block or scope full confidence

#### Scenario: Payload risk lacks payload proof
- **WHEN** a final risk row depends on file import/export, generated artifact,
  or AI work-package behavior
- **AND** no current artifact payload validation proof or scoped blindspot is
  attached
- **THEN** the ledger MUST block or scope full confidence

### Requirement: Risk rows consume contract-exhaustion evidence
FlowGuard RiskEvidenceLedger MUST be able to require current
ContractExhaustionMesh reports and case evidence before granting full risk
confidence for same-class or finite-boundary claims.

#### Scenario: Blocked exhaustion blocks full risk confidence
- **WHEN** a risk row depends on contract-exhaustion coverage and the report is
  blocked by missing oracles or model gaps
- **THEN** the risk row cannot report full confidence

#### Scenario: Current report supports scoped risk row
- **WHEN** all required cases for the claim have current evidence and no
  blocking findings
- **THEN** the risk row can consume the report as part of its final decision

### Requirement: RiskEvidenceLedger owns final broad confidence
RiskEvidenceLedger SHALL be the final broad confidence owner for done, release,
archive, publish, production, or full claims that depend on FlowGuard route
evidence.

#### Scenario: Closure helper pass is insufficient
- **WHEN** a closure helper, maintenance scan, or child report is passing
- **THEN** a broad claim MUST still be unsupported until RiskEvidenceLedger
  consumes current proof rows for the relevant risks

#### Scenario: Single-route matrix is insufficient
- **WHEN** ContractExhaustionMesh generated cases pass a single route matrix
- **THEN** RiskEvidenceLedger MUST require composite handoff acceptance for
  any case that needs multi-route closure before broad confidence is allowed

### Requirement: Ledger consumes owner-route evidence only
RiskEvidenceLedger SHALL consume current evidence from public owner routes or
explicitly identified helper evidence that has been consumed by a public owner.

#### Scenario: Internal helper evidence bypasses owner
- **WHEN** a risk row cites only internal helper evidence that no owner route
  consumed
- **THEN** the ledger MUST report unsupported confidence for that row

### Requirement: Risk ledger consumes all-model Cartesian coverage
RiskEvidenceLedger SHALL require current all-model Cartesian coverage evidence
before granting broad done, release, publish, production, archive, or full
confidence for a FlowGuard-managed model hierarchy.

#### Scenario: Missing model receipt blocks full confidence
- **WHEN** a final risk row requires all-model Cartesian coverage
- **AND** any in-scope model lacks a current coverage receipt
- **THEN** RiskEvidenceLedger reports a missing model coverage finding
- **AND** full confidence is blocked

#### Scenario: Unclosed shard blocks full confidence
- **WHEN** a final risk row depends on a coverage receipt with unfinished
  required shards
- **THEN** RiskEvidenceLedger reports unclosed Cartesian shard evidence
- **AND** full confidence is blocked or scoped according to policy

#### Scenario: Complete all-model coverage supports confidence
- **WHEN** every in-scope model receipt is current
- **AND** every required generated case has semantic and test evidence
- **AND** every child receipt is consumed by its parent
- **THEN** RiskEvidenceLedger may treat all-model Cartesian coverage as
  supporting final confidence

### Requirement: Ledger rejects child-local coverage bypass
RiskEvidenceLedger SHALL reject final confidence when a claim cites child-local
Cartesian coverage but no parent ModelMesh evidence consumed that child
coverage.

#### Scenario: Child local receipt bypasses parent mesh
- **WHEN** a risk row cites a child coverage receipt directly for a parent or
  root claim
- **AND** no current parent consumption evidence exists
- **THEN** RiskEvidenceLedger reports unconsumed child coverage

### Requirement: Risk ledger consumes primary path authority
RiskEvidenceLedger SHALL support a primary-path authority gate for final risk
rows that depend on path-sensitive behavior.

#### Scenario: Missing authority gate blocks broad confidence
- **WHEN** a final risk row requires primary-path authority
- **AND** no current primary-path authority evidence id is attached
- **THEN** the ledger SHALL report a missing primary-path authority gate

#### Scenario: Blocked authority evidence blocks confidence
- **WHEN** a final risk row references primary-path authority evidence with
  blocked findings
- **THEN** the ledger SHALL block or scope confidence according to ledger
  policy

### Requirement: Risk ledger consumes primary-path Cartesian coverage
RiskEvidenceLedger SHALL require current primary-path Cartesian coverage
receipts before granting broad confidence for no-fallback claims.

#### Scenario: Missing primary-path coverage receipt blocks
- **WHEN** a risk row requires primary-path Cartesian coverage
- **AND** a required coverage receipt or shard id is missing, stale, skipped,
  progress-only, or unconsumed
- **THEN** the ledger SHALL report a primary-path Cartesian coverage gap

#### Scenario: Current authority and coverage support closure
- **WHEN** primary-path authority evidence is current and all required coverage
  receipts, shards, and composite handoff ids are consumed
- **THEN** the ledger MAY use those evidence rows to support the declared
  path-sensitive confidence boundary

### Requirement: Risk ledger gates behavior commitment coverage
FlowGuard SHALL expose a behavior-commitment coverage risk gate and SHALL
block broad confidence when required ledger coverage is missing or blocked.

#### Scenario: Ledger gate passes
- **WHEN** a RiskEvidenceLedger row references a current passing behavior ledger report
- **THEN** the risk gate SHALL be eligible to support broad confidence

#### Scenario: Ledger gate blocks
- **WHEN** a RiskEvidenceLedger row references missing, stale, or blocked behavior ledger coverage
- **THEN** the risk gate SHALL block release, publish, archive, production, and full-confidence claims

