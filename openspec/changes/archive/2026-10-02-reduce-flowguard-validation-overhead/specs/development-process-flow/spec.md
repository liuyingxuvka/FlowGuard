## MODIFIED Requirements

### Requirement: DevelopmentProcessFlow triggers for staged work with validation
FlowGuard SHALL present DevelopmentProcessFlow as the route for any non-trivial staged development or modification task where step ordering, touched artifacts, validation evidence, evidence freshness, peer writes, or minimum revalidation affects whether the agent can safely continue or claim done.

#### Scenario: Rough plan trigger enters simulator
- **WHEN** an agent is asked to discuss, refine, or accept a non-trivial rough plan
- **THEN** the Codex-facing guidance enters `flowguard-development-process-flow` first
- **AND** it records and executes the owner's internal `plan_detailing` mode

#### Scenario: Multi-skill trigger enters simulator
- **WHEN** a task may require several Codex skills, tools, plugins, external actions, or skipped-skill consequences
- **THEN** the Codex-facing guidance enters `flowguard-development-process-flow` first
- **AND** it records the owner's internal `agent_workflow` mode only when explicit rehearsal, shared-write, post-validation-invalidating-write, agent/route-workflow-change, or multiple-independent-owner irreversible-risk facts are present
- **AND** capability labels or a cross-owner handoff alone leave the mode `not_triggered`

#### Scenario: Ordinary cross-owner handoff requires freshness but not rehearsal
- **WHEN** an implementation task transfers work between owners and no shared-write, post-validation-invalidating-write, agent/route-workflow-change, multiple-owner irreversible-risk, or explicit rehearsal fact is present
- **THEN** DevelopmentProcessFlow records the affected owner and handoff identity for freshness review
- **AND** it does not create an `agent_workflow` rehearsal plan or receipt

#### Scenario: Handoff with a separate risk requires rehearsal
- **WHEN** a cross-owner handoff also has a shared-write, post-validation-invalidating-write, agent/route-workflow-change, multiple-owner irreversible-risk, or explicit rehearsal fact
- **THEN** DevelopmentProcessFlow admits `agent_workflow` for that separate risk fact
- **AND** the handoff remains subject to freshness review

#### Scenario: Staged implementation trigger
- **WHEN** an agent is asked to complete a non-trivial task with staged actions such as plan, edit, test, fix, and verify
- **THEN** the Codex-facing DevelopmentProcessFlow guidance says to use `flowguard-development-process-flow` during planning

#### Scenario: Not reserved for release readiness
- **WHEN** a task is not yet at release, archive, publish, or final readiness but has multiple meaningful development stages and validation
- **THEN** the DevelopmentProcessFlow guidance still treats the route as applicable

#### Scenario: Trivial work can skip
- **WHEN** the task is a single-step typo, formatting-only edit, or pure explanation with no meaningful validation or artifact freshness risk
- **THEN** the guidance permits skipping DevelopmentProcessFlow with a clear reason

### Requirement: Author assurance checkpoints bind the exact declared source inputs
An author-assurance checkpoint SHALL bind the maintained member and unit, the author contract bytes, the exact status and byte digest of every contract-declared input, the author toolchain identity, and the persistent state root. A checkpoint SHALL be reusable only after a read confirms the exact accepted identity. Full and plan-only admission SHALL reject an absent, invalid, repository-contained, or repository-ancestor author state root before starting an owner. If a mutation succeeds but checkpoint persistence is interrupted, recovery MAY commit the checkpoint only from one exact durable invocation record after a current read confirms the same accepted identity; it SHALL NOT repeat the mutation, reset the compare-and-swap token, or infer success when the record is missing.

#### Scenario: Exact current author inputs reuse one accepted result
- **WHEN** contract-declared source bytes, contract, toolchain, member, unit, and state binding all match the checkpoint identity
- **THEN** the wrapper verifies the accepted ID with one read and starts no change or release producer

#### Scenario: Declared source bytes change while inventory shape stays the same
- **WHEN** a declared author input's bytes change but the structural inventory hash and contract structure remain unchanged
- **THEN** the old checkpoint SHALL NOT be reused as current
- **AND** the wrapper SHALL observe the existing accepted ID before issuing a change with that compare-and-swap token

#### Scenario: Invalid state root is supplied for full or plan-only admission
- **WHEN** the author state root is missing, nonexistent, inside the repository, or an ancestor of the repository
- **THEN** admission SHALL return a typed invalid-input result before starting the full owner plan or any child

#### Scenario: Accepted mutation has an exact durable invocation record
- **WHEN** a change or release returned terminal success and its exact request/result record was saved but the wrapper checkpoint update was interrupted
- **THEN** recovery SHALL perform one current read and update the checkpoint only when the accepted ID matches that exact successful record
- **AND** it SHALL continue with the next required operation without replaying the accepted mutation

#### Scenario: Accepted mutation result was not durably recorded
- **WHEN** the accepted state may have advanced but no exact successful invocation record exists
- **THEN** the wrapper SHALL remain blocked with the prior state retained and SHALL NOT guess, reset, or replay a mutation

### Requirement: Current revision preflights prepared semantics and preserves an accepted boundary contract
The current change lifecycle SHALL validate the complete typed revision preparation, including the exact predecessor-transition inventory, accepted replacement/disposition pairing, current source fingerprints, and exact dispositions for every removed governed identity, before starting any model owner. When the observed current authority has an accepted boundary contract, the current change candidate SHALL preserve its axes, interaction groups, and explicit group-to-relation mapping while rebinding them to the candidate snapshot through the typed boundary-contract builder and structural validator. The preview, regression plan, owner evidence, and revision builder SHALL consume that same candidate contract identity. If the prior contract cannot be validated against the candidate topology, the change SHALL block before model-owner execution. The minimal current change route SHALL NOT silently retire or scope out the accepted contract; semantic edits to its partition require a separately typed authoring path.

#### Scenario: Invalid transition or removal preparation blocks before owners
- **WHEN** a current change preparation omits or duplicates a current predecessor transition, has a replacement without one accepted fingerprint-matching disposition, or fails to disposition an exact removed governed identity
- **THEN** current-change admission SHALL return a typed blocked result before creating owner evidence or running a model owner
- **AND** it SHALL report the exact missing, duplicate, mismatched, or removed identity

#### Scenario: Existing boundary contract is carried forward by typed rebind
- **WHEN** the observed authority has one accepted boundary contract and the candidate retains every declared group relation
- **THEN** the candidate SHALL reuse the accepted axes, interaction groups, and explicit group-relation mapping
- **AND** it SHALL recompute coverage and topology bindings from the candidate and pass the shared structural validator before model owners start
- **AND** the exact resulting contract fingerprint SHALL be used by preview, regression planning, owner evidence, and revision construction

#### Scenario: Candidate no longer supports an accepted boundary contract
- **WHEN** a candidate removes a relation used by the accepted contract or otherwise fails its structural validation
- **THEN** current-change admission SHALL block before model-owner execution
- **AND** it SHALL NOT mark the contract retired or out of scope as an implicit fallback

#### Scenario: Missing or retired selection blocks
- **WHEN** a request has no unique current subject, names a retired entry, or omits a required accepted identity
- **THEN** FlowGuard reports a typed blocker with zero producer and zero write effects; it does not widen the scope or try another route.

### Requirement: Process actions record lifecycle reads and writes
FlowGuard SHALL allow projects to declare ordered development process actions with read artifacts, written artifacts, invalidated artifacts, produced evidence, required evidence, actor metadata, and decision scope. FlowGuard SHALL require each action that writes or invalidates a registered artifact with a non-empty owner to declare that exact owner in `ProcessAction.actor`. The check SHALL cover the complete action write set, including writes before any validation evidence is produced. An owner mismatch SHALL block the process review independently of evidence freshness. Reads, actions that do not write artifacts, and artifacts without an explicit owner are outside this check.

#### Scenario: Ordered lifecycle action
- **WHEN** an action writes a registered artifact
- **THEN** DevelopmentProcessFlow records that the artifact version changed for later evidence freshness checks

#### Scenario: Named writer matches the artifact owner
- **WHEN** an action writes an explicitly owned artifact and its actor exactly matches the artifact owner
- **THEN** the writer-ownership check reports no mismatch

#### Scenario: Foreign writer changes an owned artifact before validation
- **WHEN** an action writes an explicitly owned artifact before validation and its named actor differs from the artifact owner
- **THEN** DevelopmentProcessFlow reports a blocking writer-owner mismatch for that action and artifact
- **AND** the result does not depend on stale-evidence analysis

#### Scenario: Unowned artifacts and read-only handoffs remain unconstrained
- **WHEN** an action only reads an artifact, or writes an artifact whose owner is empty
- **THEN** the named-writer ownership check reports no mismatch

#### Scenario: Out-of-order lifecycle action
- **WHEN** an action declares an `order_after` dependency on an action that has not already occurred
- **THEN** DevelopmentProcessFlow reports an out-of-order process finding

## ADDED Requirements

### Requirement: Release admission binds one valid archived completion objective
Release readiness and release full/plan-only admission SHALL require a non-empty OpenSpec change name that resolves to exactly one valid dated archive objective. An active-only objective, an objective present both active and archived, multiple matching archives, a malformed matching archive date, or a matching reparse-point target SHALL block before any readiness gate or child owner starts. Full/plan-only admission SHALL recheck archive state after readiness is supplied because objective content identity does not encode its active/archive location. Local validation SHALL remain usable before archival and SHALL NOT claim release readiness from an active-only objective.

#### Scenario: Release readiness requires one archived objective
- **WHEN** release readiness is requested for an empty change name, an active-only change, or an unknown change
- **THEN** admission SHALL return a typed blocked result before starting any gate or owner
- **AND** a non-empty name with exactly one valid dated archive and no active copy SHALL resolve to that archived objective

#### Scenario: Duplicate or malformed archive identity blocks release admission
- **WHEN** the named change exists both active and archived, has multiple matching dated archive directories, or has a matching archive directory with an invalid calendar date
- **THEN** release readiness or full/plan-only admission SHALL return a typed blocked result before starting any gate or owner

#### Scenario: Objective moved back to active after readiness
- **WHEN** release readiness was produced for one archived objective and the same-content objective is moved back to its active path before full/plan-only admission
- **THEN** release admission SHALL recheck archive state and return a typed blocked result before any child owner starts

#### Scenario: Reparse-point archive target blocks release readiness
- **WHEN** the named active or matching archived objective, archive directory, or an artifact under that objective is a symlink or reparse point
- **THEN** admission SHALL return a typed blocked result before starting any gate or owner

#### Scenario: Local validation runs before archival without release claims
- **WHEN** local validation is requested for an active OpenSpec change before archive
- **THEN** local validation MAY proceed through its declared local checks
- **AND** it SHALL NOT claim that release readiness has been achieved

### Requirement: Cached readiness reuse is bound to current admission identity
When a completion-readiness output directory already contains a readiness object and evidence envelope, the producer SHALL return a passing reuse result only when the readiness fingerprint is bound identically by the evidence and completion-run manifest, the saved current-read gate is valid and remains bound through the owner-DAG gate to the current fixed read request and observed authority head, the complete manifest invocation matches the current invocation, and any named completion objective still has the same fingerprint. A mismatch SHALL return a typed blocked result without rerunning gates or overwriting the immutable envelope.

#### Scenario: Exact cached readiness reuses its immutable envelope
- **WHEN** the current read request, authority head, author-state root, objective, invocation fields, and manifest fingerprints match the saved envelope
- **THEN** the producer returns the saved readiness and manifest references without starting a gate

#### Scenario: Authority head changes after readiness was written
- **WHEN** the fixed current read request resolves to a different authority head than the saved producer-free current-read gate
- **THEN** cached readiness SHALL return a typed blocked result before reporting `status=pass`
- **AND** it SHALL leave the saved readiness, evidence, and manifest bytes unchanged

#### Scenario: Author state or objective changes after readiness was written
- **WHEN** the current invocation selects a different author-state root or a named completion objective has a different content fingerprint than the saved manifest
- **THEN** cached readiness SHALL return a typed blocked result before reporting `status=pass`
- **AND** it SHALL leave the saved readiness, evidence, and manifest bytes unchanged

## REMOVED Requirements

### Requirement: Release readiness binds one valid archived completion objective
**Reason**: The stronger current requirement `Release admission binds one valid archived completion objective` replaces this narrower readiness-only requirement and preserves its existing scenarios while adding full/plan-only archive-location revalidation.
**Migration**: Replace this canonical requirement with the exact current `Release admission binds one valid archived completion objective` block. No compatibility route, alternate admission, or second requirement authority is retained.


### Requirement: Selected work ends at verified functional sufficiency
Process order SHALL consume existing task demand/current verified maturation, inspect triggered dependencies and complete required-goal scope, and end once the requested outcome is proven. Untriggered blueprint/UI/database domains SHALL start no producer. Required gaps SHALL not be scoped out or waived by cost/iteration/annotation. Whole inventory remains an explicit task or named release obligation.

#### Scenario: Small task has no unrelated deep trigger
- **WHEN** current task proof is complete within its actual dependency closure
- **THEN** the process delivers scope/currentness/finding/action pointers and ends without unrelated expansion or repeated full evidence text
