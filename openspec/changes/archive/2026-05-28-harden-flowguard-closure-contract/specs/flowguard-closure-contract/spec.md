## ADDED Requirements

### Requirement: Executable Closure Contract Review

FlowGuard SHALL provide an executable closure contract review for broad done,
release, publish, or production-confidence claims.

#### Scenario: All required closure evidence is current

- **WHEN** a closure plan has current runtime trace mapping, artifact freshness,
  model quality, same-class miss, runtime gateway, and risk ledger evidence for
  every required in-scope item
- **THEN** the review returns full confidence

#### Scenario: Required closure evidence is missing

- **WHEN** a closure plan omits a required in-scope evidence area
- **THEN** the review blocks full confidence and reports the missing area

### Requirement: Runtime Trace Model Mapping

FlowGuard SHALL require runtime traces used for production confidence to map to
declared model obligations.

#### Scenario: Runtime trace maps to model obligation

- **WHEN** a runtime trace row is current, in scope, and names a model obligation
- **THEN** the closure review accepts the trace mapping evidence

#### Scenario: Runtime trace has no model obligation

- **WHEN** an in-scope runtime trace row has no model obligation
- **THEN** the closure review reports the trace as a model-miss boundary

### Requirement: Artifact Invalidation Review

FlowGuard SHALL treat changed artifacts as invalidation evidence for dependent
model, test, gateway, code-boundary, and ledger proof.

#### Scenario: Changed artifact has revalidation evidence

- **WHEN** an artifact invalidation row names changed artifacts and has current
  revalidation evidence for the dependent proof
- **THEN** the closure review accepts the freshness evidence

#### Scenario: Changed artifact lacks revalidation evidence

- **WHEN** an artifact invalidation row marks prior proof stale or lacks current
  revalidation evidence
- **THEN** the closure review blocks full confidence

### Requirement: Model Quality Signals

FlowGuard SHALL surface model-quality gaps before broad confidence is claimed.

#### Scenario: Model quality signals are resolved

- **WHEN** hidden state, missing side-effect, owner ambiguity, helper-only proof,
  missing public boundary, and parent-child evidence signals are either absent
  or resolved
- **THEN** the closure review accepts model-quality evidence

#### Scenario: Model is too coarse

- **WHEN** a required in-scope model-quality signal remains unresolved
- **THEN** the closure review blocks full confidence or downgrades to scoped
  confidence when scoped claims are allowed

### Requirement: Same-Class Model Miss Closure

FlowGuard SHALL require in-scope runtime/model misses to include observed
failure evidence and same-class closure evidence before broad confidence is
restored.

#### Scenario: Same-class miss closure passes

- **WHEN** a model-miss closure row names the observed failure and current
  same-class proof evidence
- **THEN** the closure review accepts the miss closure

#### Scenario: Same-class proof is missing

- **WHEN** an in-scope model-miss closure row lacks same-class proof evidence
- **THEN** the closure review blocks full confidence

### Requirement: Runtime Gateway Inventory Closure

FlowGuard SHALL require runtime-gateway confidence to include writer inventory
source evidence, gateway coverage, and resolved path-owner conflicts.

#### Scenario: Runtime gateway inventory is complete

- **WHEN** a runtime gateway closure row names current inventory source evidence,
  current gateway adoption evidence, and no unresolved path-owner conflicts
- **THEN** the closure review accepts runtime gateway support

#### Scenario: Runtime gateway inventory source is missing

- **WHEN** a runtime gateway closure row lacks current inventory source evidence
- **THEN** the closure review blocks runtime-protected confidence

#### Scenario: Runtime gateway path-owner conflict remains open

- **WHEN** a runtime gateway closure row has unresolved path-owner conflicts
- **THEN** the closure review blocks full confidence

### Requirement: Risk Ledger Final Boundary

FlowGuard SHALL require Risk Evidence Ledger support before reporting full
confidence for a broad claim.

#### Scenario: Risk ledger supports full confidence

- **WHEN** a closure plan includes a current risk ledger report with full
  confidence
- **THEN** the closure review may return full confidence if all other required
  gates pass

#### Scenario: Risk ledger is scoped or missing

- **WHEN** a closure plan has no risk ledger evidence or only scoped risk ledger
  confidence
- **THEN** the closure review blocks or scopes the final claim according to the
  plan's scoped-claim policy
