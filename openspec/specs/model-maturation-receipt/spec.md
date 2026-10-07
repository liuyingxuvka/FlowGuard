# model-maturation-receipt Specification

## Purpose
Provide one immutable, content-addressed, independently verifiable authority for an exact model maturation result and all downstream readiness consumers.
## Requirements
### Requirement: Terminal maturation is published as a canonical receipt
A closed or blocked maturation run SHALL publish a content-addressed receipt binding the exact task, coverage demand, candidate model, input set, evidence set, decision, confidence scope, open gaps, producer, and covered obligations.

#### Scenario: Receipt content changes
- **WHEN** any bound identity, evidence, decision, gap, or obligation changes
- **THEN** the receipt fingerprint changes and the prior receipt cannot represent the new run

### Requirement: Currentness and decision are verifier-derived
Consumers SHALL obtain currentness, eligibility, decision, confidence scope, and open gaps from independent receipt verification and MUST NOT accept those authority fields from a caller-authored mapping.

#### Scenario: Caller presents a fabricated current flag
- **WHEN** supplied data claims `current=true` without a matching canonical receipt and current snapshots
- **THEN** verification fails and no readiness consumer may treat the maturation as current

### Requirement: Understanding status is a read-only receipt projection
The system SHALL provide a status projection over explicitly supplied task, model, demand, resolution, maturation, and receipt identities. Reading status SHALL NOT execute an owner, publish or renew a receipt, change current authority, or convert missing evidence into success.

#### Scenario: No maturation receipt is supplied
- **WHEN** status is requested for a task with no matching verified maturation receipt
- **THEN** understanding sufficiency is reported as not-run or unresolved and no receipt is created

#### Scenario: Receipt identity is stale
- **WHEN** the supplied receipt does not match the current task, model, demand, or resolution identity
- **THEN** status reports stale with the mismatched identity fields

### Requirement: Responsibility directions require independent context evidence
Maturation SHALL compare responsibilities only within finite declared applicable input classes using independently current semantic, code-binding, oracle and native conformance evidence. Overlapping context and equal hard semantics with independent primary implementations SHALL produce a bounded `duplicate_boundary` candidate; disjoint contexts or an exact permitted variant relation SHALL preserve `legitimate_variant`. Same-name or same-mechanism responsibilities with different hard behavior SHALL remain `false_friend` and ineligible for equivalent-path ranking. Unknown context or missing independent evidence SHALL block the claimed relation.

#### Scenario: Same semantics overlap across two boundaries
- **WHEN** two independently bound current primary implementations share evidenced hard semantics and a nonempty finite context intersection
- **THEN** maturation records `equivalent_responsibility_paths` and a bounded duplicate candidate
- **AND** current observed owners remain intact while any merge or delegation awaits explicit proof and implementation

#### Scenario: Legitimate variants have disjoint contexts
- **WHEN** responsibility bindings apply to nonoverlapping declared input classes
- **THEN** maturation preserves both variants without a duplicate finding or merge suggestion

#### Scenario: Similar mechanisms have different permissions
- **WHEN** mechanism names match but independently evidenced permission or effect semantics differ
- **THEN** the relation remains `false_friend` and does not enter equivalent-cost ranking

### Requirement: Shared mechanism closure requires one real primary
A shared-mechanism objective SHALL require one canonical primary implementation and exact current delegation relations from every declared scoped consumer. Identical fingerprints on independent copies SHALL NOT establish shared-primary closure. Evidence SHALL bind the current primary code contract, mechanism, consumer roles, finite contexts and independently verified delegation closure.

#### Scenario: Two identical copies claim sharing
- **WHEN** two independent primary implementations have equal mechanism fingerprints without exact delegation to one canonical primary
- **THEN** the shared-mechanism objective remains unmet

### Requirement: Accepted observation cannot satisfy required architecture closure
A verified maturation receipt SHALL expose observation fidelity and required improvement closure separately while retaining its exact confidence and open-gap identities. A required objective gap, unknown complete objective scope or unverified required improvement SHALL block completion and release even if observation is accepted. Optional unresolved improvement SHALL remain visible without creating an undeclared required objective.

#### Scenario: Receipt accepts current observation with a required gap
- **WHEN** observation is accepted and a required objective is still unmet
- **THEN** downstream completion and release consumers remain blocked
- **AND** they identify the objective, affected elements, retained obligations and exact next native owner rather than treating observed acceptance as improvement success


### Requirement: Functional sufficiency consumes existing verified closure
A pure understanding view SHALL map actual requested outcomes to active contribution obligation/invariant/terminal targets, implementation bindings and original native proof. Success SHALL require the existing MODEL_MATURATION_DECISION_CLOSED_FOR_TASK and current eligible verifier-created VerifiedModelMaturation with exact task/demand/candidate/input/evidence/result-set/owner-resolution identities and no required gap. Constructible report.ok, caller boolean, scoped-out required gap and iteration exhaustion SHALL NOT create success.

#### Scenario: Complete task A has no dependency on B
- **WHEN** task A obligations and current proof are complete and B is independent/untriggered
- **THEN** the view closes using existing verified task evidence with zero B reads/producers and no whole-software claim

#### Scenario: Verification is missing or belongs to another task
- **WHEN** report.ok is asserted without matching current verified proof or with foreign task/demand/candidate evidence
- **THEN** the view remains non-success and names exact missing input/owner

### Requirement: Partial overlap preserves legitimate contextual remainder
Comparison SHALL index only independently admitted contexts and hard semantic content, retaining each remaining context. Different contextual hard behavior SHALL use separately admitted facts under the current strict semantic source schema. Whole-fact hash SHALL NOT manufacture local equivalence.

#### Scenario: Online overlaps while recovery and batch differ
- **WHEN** independently verified online semantics match and recovery/batch are separately grounded
- **THEN** only online becomes duplicate candidate and both differences/obligations remain
- **AND** absent local proof remains needs_evidence without unconditional merge


### Requirement: Exact resolution basis
Maturation SHALL authenticate resolutions against the original demand basis and bind the exact derived closed demand to its plan, report and canonical receipt. A task-context producer SHALL publish actual closed or blocked maturation evidence independently of native execution.

#### Scenario: A coverage resolution closes an original obligation
- **WHEN** a coverage resolution closes an original obligation
- **THEN** The original basis remains authenticated and the closed demand cannot be substituted or forged.
