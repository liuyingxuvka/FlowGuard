# risk-evidence-ledger Specification

## Purpose
TBD - created by archiving change add-risk-evidence-ledger. Update Purpose after archive.
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
