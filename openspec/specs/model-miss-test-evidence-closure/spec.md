# model-miss-test-evidence-closure Specification

## Purpose
TBD - created by archiving change require-same-class-test-evidence. Update Purpose after archive.
## Requirements
### Requirement: Model miss closure requires same-class test evidence
FlowGuard SHALL block full closure for an in-scope post-runtime model miss
unless the repaired model obligation has current passing test evidence for the
observed failure and same-class generalized coverage.

#### Scenario: Observed and same-class evidence close the miss
- **WHEN** a repaired in-scope model-miss obligation names both an observed
  failure regression and same-class generalized test evidence
- **THEN** Model-Test Alignment SHALL allow green alignment for that obligation
  when both evidence rows are current, passing, and externally scoped

#### Scenario: Exact regression only is insufficient
- **WHEN** a repaired in-scope model-miss obligation has only a current passing
  test for the observed failure
- **THEN** Model-Test Alignment SHALL report missing same-class test evidence
  and SHALL NOT return full green alignment

### Requirement: Model-Test Alignment represents model-miss closure roles
FlowGuard SHALL let model obligations and test evidence declare model-miss
closure roles so reports can distinguish observed regression tests from
same-class generalized tests.

#### Scenario: Model-miss obligation declares required closure roles
- **WHEN** a model obligation is marked as originating from a model miss and
  requires same-class closure
- **THEN** the alignment plan SHALL require both observed regression evidence
  and same-class generalized evidence for that obligation

#### Scenario: Same-class evidence has the wrong target
- **WHEN** same-class evidence is current and passing but does not cover the
  model-miss obligation that requires it
- **THEN** Model-Test Alignment SHALL keep the obligation blocked

### Requirement: Development process keeps stale and overclaimed miss evidence visible
FlowGuard SHALL treat model, test, and requirement changes made during
model-miss repair as invalidating earlier closure evidence until the minimum
revalidation plan has current evidence.

#### Scenario: Repaired model stales old alignment evidence
- **WHEN** the model obligation changes after earlier model-test alignment
  evidence was produced
- **THEN** DevelopmentProcessFlow SHALL mark the old alignment evidence stale
  and recommend rerunning the required alignment command

#### Scenario: Old test overclaimed model confidence
- **WHEN** pre-repair test evidence is marked as overclaiming model confidence
- **THEN** Model-Test Alignment SHALL report the overclaim instead of counting
  that row as same-class closure evidence

### Requirement: Large same-class validation routes to TestMesh
FlowGuard SHALL route large, slow, layered, stale-prone, background, or
release-only same-class validation requirements to TestMesh instead of
expanding Model-Test Alignment into a hierarchy.

#### Scenario: Large same-class coverage needs a child suite
- **WHEN** same-class coverage requires parent/child test ownership, release
  suites, background completion artifacts, or leaf matrix cells
- **THEN** the workflow SHALL use TestMesh for the validation hierarchy and
  SHALL feed current TestMesh evidence back into the final confidence claim

#### Scenario: Routine closure reports scoped confidence
- **WHEN** same-class release coverage is deferred during routine validation
- **THEN** the workflow SHALL report scoped routine confidence and SHALL NOT
  claim full release confidence

### Requirement: Recurring model misses promote to a defect-family gate
FlowGuard SHALL require an artifact-backed defect-family gate when the same
same-class model-miss family recurs or when the miss is high risk enough that a
local point fix would overclaim final confidence.

#### Scenario: Recurring family without promotion is blocked
- **WHEN** a same-class model miss has occurred more than once and no
  defect-family gate has been promoted
- **THEN** FlowGuard SHALL report the recurring miss as blocked and SHALL NOT
  allow full confidence for the affected family

#### Scenario: Promoted family has current artifact-backed proof
- **WHEN** a promoted defect family names a model obligation, authority
  boundary, observed failure case, same-class generalized case, historical
  holdout case, current external passing proof evidence, and a current proof
  artifact reference
- **THEN** FlowGuard SHALL allow the defect-family gate to pass

#### Scenario: Declaration-only evidence is insufficient
- **WHEN** a promoted defect family only has caller-declared passing evidence
  without proof artifact binding
- **THEN** FlowGuard SHALL keep the defect-family gate blocked in strict
  closure mode

### Requirement: Model miss closure includes legacy path disposition
FlowGuard SHALL block full closure for a repaired model miss until every
in-scope old, alternate, replay, or recovery path is proven deleted, blocked,
delegated to the repaired contract, repaired to the same contract, or explicitly
out of scope.

#### Scenario: Repaired child path does not dispose old path
- **WHEN** a repaired child path has current same-class evidence but an old
  route path remains reachable with unknown disposition
- **THEN** model-miss closure SHALL remain blocked

### Requirement: Risk Evidence Ledger consumes defect-family gates
FlowGuard SHALL let final risk rows require a current defect-family gate before
the row can support full confidence.

#### Scenario: Required defect-family gate is missing
- **WHEN** a final confidence row requires a defect-family gate but does not
  name one
- **THEN** the Risk Evidence Ledger SHALL block full confidence with a visible
  defect-family finding

#### Scenario: Defect-family gate is scoped
- **WHEN** the defect-family gate is current but has explicit scoped-confidence
  reasons
- **THEN** the Risk Evidence Ledger SHALL downgrade the final claim to scoped
  confidence rather than silently allowing a full claim

### Requirement: Bug repair closure binds model, code, and tests
For an in-scope bug repair, FlowGuard SHALL block broad closure unless the
repaired bug class has a current model obligation, an owner code contract, and
current observed-regression plus same-class test evidence bound to the same
behavior.

#### Scenario: Model-code-test repair chain passes
- **WHEN** a repaired bug class has a model-miss-origin obligation
- **AND** an owner code contract implements that obligation
- **AND** current observed-regression and same-class generalized test evidence
  cover both the model obligation and the owner code contract
- **THEN** Model-Test Alignment may report the repair row as green

#### Scenario: Test does not bind code owner
- **WHEN** a bug repair has model and test evidence
- **AND** the test evidence does not cover the owner code contract that
  implements the repaired obligation
- **THEN** full bug repair closure is blocked or scoped

### Requirement: Bug repair closure records old-path disposition
FlowGuard SHALL require existing compatibility classification and
LegacyPathDisposition evidence before full confidence is restored for an
in-scope bug repair with reachable old paths, fallbacks, aliases, replay paths,
recovery paths, or compatibility adapters.

#### Scenario: Old path is dispositioned
- **WHEN** a repaired bug class had an old or fallback path that remains
  reachable
- **THEN** closure evidence records whether the path was deleted, blocked,
  delegated to the repaired contract, repaired to the same contract, or
  explicitly scoped out

#### Scenario: Old path remains unknown
- **WHEN** an old or fallback path may still execute with unknown disposition
- **THEN** full bug repair closure remains blocked

