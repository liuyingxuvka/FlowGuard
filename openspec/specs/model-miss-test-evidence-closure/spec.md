# model-miss-test-evidence-closure Specification

## Purpose
This capability defines FlowGuard's Model Miss Test Evidence Closure behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Model miss closure requires same-class test evidence
FlowGuard SHALL block full closure for an in-scope post-runtime model miss unless the repaired model obligation has current passing test evidence for the observed ContractExhaustionMesh case and every required finite same-class case in the canonical affected relation set.

#### Scenario: Observed and same-class evidence close the miss
- **WHEN** a repaired in-scope model-miss obligation names the canonical observed case id and all required finite same-class case ids
- **THEN** Model-Test Alignment SHALL allow green alignment for that obligation only when each case has current passing evidence bound to the same model obligation and owner code contract

#### Scenario: Exact regression only is insufficient
- **WHEN** a repaired in-scope model-miss obligation has only current passing evidence for the observed case
- **THEN** Model-Test Alignment SHALL report the missing canonical same-class case ids
- **AND** it SHALL NOT return full green alignment

#### Scenario: No canonical related case is required
- **WHEN** ContractExhaustionMesh proves that the bounded relation set contains no additional required same-class member for the declared claim
- **THEN** closure records that finite result without manufacturing an artificial sibling or scan obligation

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

### Requirement: Model miss closure includes legacy path disposition
FlowGuard SHALL block full closure for a repaired model miss until every
in-scope old, alternate, replay, or recovery path is proven deleted, blocked,
delegated to the repaired contract, repaired to the same contract, or explicitly
out of scope.

#### Scenario: Repaired child path does not dispose old path
- **WHEN** a repaired child path has current same-class evidence but an old
  route path remains reachable with unknown disposition
- **THEN** model-miss closure SHALL remain blocked

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

### Requirement: Combination misses promote interaction groups
Model-miss closure SHALL project observed combination-type misses into ContractExhaustionMesh interaction groups and stable generated combination case ids before broad repair confidence can be restored.

#### Scenario: Point fix omits interaction group
- **WHEN** an observed miss depends on more than one model axis or on a child axis plus a parent consumption axis
- **AND** the repair adds only the observed regression test
- **THEN** model-miss closure reports missing interaction-group coverage

#### Scenario: Recurring or high-risk combination miss is deepened
- **WHEN** a combination miss recurs or requires broader confidence
- **THEN** the canonical interaction group names the affected model ids, root-cause dimensions, observed combination case id, required generated case ids, and current evidence
- **AND** ModelMaturation consumes that finite case result without creating a separate family gate

#### Scenario: Combination miss feeds bug family gate
- **WHEN** a caller attempts to send a combination miss to a retired bug-family gate
- **THEN** FlowGuard MUST reject that parallel authority and route the exact observed seed to ContractExhaustionMesh and ModelMaturation
- **AND** the canonical interaction-group and case identities remain the only finite closure path

### Requirement: Model miss closure follows one exact blueprint-gap chain
Every in-scope model miss SHALL resolve the exact behavior plane, commitment, blueprint block, primary model owner, owner code contract, and observed failure before closure work begins. Model Miss Review SHALL emit one typed blueprint gap and observed-problem seed; ContractExhaustionMesh SHALL own the finite observed, same-class, combination, and holdout case identities and their oracles; ModelMaturation SHALL own the model-depth response; Model-Test Alignment SHALL bind the accepted model, owner code, and current test evidence; and replay SHALL cover the canonical affected topology. The chain SHALL produce one current maturation result for final risk review.

#### Scenario: Exact miss chain closes with current evidence
- **WHEN** an observed miss resolves to one current blueprint owner and its canonical affected relations
- **THEN** ContractExhaustionMesh creates or reuses stable case ids and executable oracles for the observed and required finite related cases
- **AND** the accepted model update, owner code contract, current test bindings, and affected-topology replay all reference those case ids before ModelMaturation emits closure

#### Scenario: Owner or relation boundary is unresolved
- **WHEN** the current blueprint cannot resolve the affected owner, commitment, code contract, or bounded relation set
- **THEN** the miss remains a visible model-depth or ownership gap
- **AND** FlowGuard MUST NOT substitute a guessed family, free-form analogous scan, or caller-declared completion gate

#### Scenario: A miss recurs or is high risk
- **WHEN** an observed miss recurs or its impact requires more than a point regression
- **THEN** the same blueprint owner and ContractExhaustionMesh case universe are deepened with the required finite sibling, interaction, boundary, and historical-holdout cases
- **AND** no separate DefectFamily authority or gate is created

### Requirement: Risk Evidence Ledger consumes the canonical maturation result
Risk Evidence Ledger SHALL consume the one current ModelMaturation result together with its exact ContractExhaustionMesh case ids, model-code-test bindings, replay evidence, scoped gaps, and subject identity. It MUST NOT require or accept a parallel defect-family or analogous-scan gate for the same miss.

#### Scenario: Canonical miss result is complete
- **WHEN** the current maturation result binds the observed miss, required finite cases, owner model, owner code contract, current test evidence, replay scope, and all scoped dispositions
- **THEN** Risk Evidence Ledger MAY use that result within its declared claim boundary

#### Scenario: Canonical miss result is missing or scoped
- **WHEN** the maturation result is missing, stale, blocked, or explicitly scoped
- **THEN** Risk Evidence Ledger preserves that state and MUST NOT upgrade it through a second family gate or scan receipt

