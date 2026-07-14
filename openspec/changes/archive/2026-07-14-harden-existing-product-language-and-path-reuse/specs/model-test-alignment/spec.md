## ADDED Requirements

### Requirement: Similarity handoff ids materialize into model-code-test alignment rows
FlowGuard SHALL require every in-scope similarity relation, similarity test-obligation id, and similarity code-obligation id consumed by Model-Test Alignment to materialize as concrete model obligations, owner code-contract bindings, test targets, or explicit scoped dispositions.

#### Scenario: Similarity obligation is fully materialized
- **WHEN** a similarity handoff requires test and code obligations for impacted models or same-intent surfaces
- **THEN** Model-Test Alignment SHALL resolve those ids to concrete `ModelObligation`, owner `CodeContract`, and current `TestEvidence` or binding rows
- **AND** the final binding report SHALL expose the originating similarity relation and obligation ids

#### Scenario: Similarity id remains opaque
- **WHEN** a plan lists a similarity relation, test-obligation, or code-obligation id but no concrete alignment row consumes it
- **THEN** Model-Test Alignment SHALL report an unmaterialized similarity obligation
- **AND** the opaque id SHALL NOT satisfy model-code-test coverage

#### Scenario: Impacted similarity member is omitted
- **WHEN** a current similarity handoff identifies an impacted model or same-intent surface but no materialized obligation or explicit scoped disposition covers it
- **THEN** Model-Test Alignment SHALL report the omitted impacted member
- **AND** the alignment decision SHALL remain blocked or scoped according to the declared claim boundary

### Requirement: Alignment preserves one exact behavior authority identity
FlowGuard SHALL preserve and compare the stable `business_intent_id`, `behavior_commitment_id`, and selected `primary_path_id` across behavior-backed model obligations, UI transition obligations, runtime-path evidence, owner code contracts, and final binding rows.

#### Scenario: Exact authority identity aligns
- **WHEN** a required obligation, its behavior commitment, selected primary path, owner code contract, and current test or runtime evidence resolve to the same stable authority identity
- **THEN** Model-Test Alignment MAY report that authority binding as aligned
- **AND** the binding row SHALL expose the stable intent, commitment, and path ids

#### Scenario: Same intent drifts to another primary path
- **WHEN** two obligations or evidence rows name the same `business_intent_id` but resolve to different selected primary-path ids
- **THEN** Model-Test Alignment SHALL report same-intent primary-path drift
- **AND** it SHALL NOT treat both paths as valid owner implementations

#### Scenario: Authority identity is inferred only from text
- **WHEN** a path-sensitive alignment claim supplies a free-text intent, label, route, or function name without stable intent, commitment, and selected-path ids
- **THEN** Model-Test Alignment SHALL report incomplete behavior-authority identity
- **AND** broad alignment confidence SHALL remain unavailable

### Requirement: Family evidence proves the obligations used by alignment
FlowGuard SHALL accept obligation-family evidence for Model-Test Alignment only when each required family member is present and each accepted evidence row's `covered_obligations` resolves to the same concrete obligations used by the alignment plan.

#### Scenario: Family matrix and alignment obligations agree
- **WHEN** every expected family member is materialized
- **AND** each current family evidence row covers the corresponding alignment obligation ids with allowed provenance
- **THEN** Model-Test Alignment SHALL preserve the family-member, mechanism, and obligation binding in its report

#### Scenario: Family evidence names a different obligation
- **WHEN** a family cell is marked covered but its evidence does not list the aligned member obligation in `covered_obligations`
- **THEN** Model-Test Alignment SHALL report a family-to-alignment obligation mismatch
- **AND** the family cell SHALL NOT satisfy the aligned obligation

#### Scenario: Required family member is absent from alignment
- **WHEN** a family declares an expected required member but the alignment plan contains no obligation for that member and no explicit scoped disposition
- **THEN** Model-Test Alignment SHALL report the missing family member obligation
- **AND** full family-level alignment SHALL remain unavailable

### Requirement: Facade alignment proves delegation instead of parallel ownership
FlowGuard SHALL treat a retained facade, alias, adapter, or wrapper code contract for a path-sensitive business intent as a delegating boundary and SHALL require current evidence that it reaches the selected primary-path owner contract without becoming a second owner implementation.

#### Scenario: Facade contract delegates to the owner contract
- **WHEN** a facade code contract is retained for an external surface
- **AND** current model, runtime, and test evidence bind the facade to the selected primary path and its owner code contract
- **THEN** Model-Test Alignment MAY record the facade as a delegating contract
- **AND** the owner code contract SHALL remain the single primary implementation for that intent

#### Scenario: Facade owns independent success behavior
- **WHEN** a retained facade or adapter can return business success, mutate the business terminal, or perform the primary side effect without delegating to the selected owner contract
- **THEN** Model-Test Alignment SHALL report parallel facade ownership or alternate success
- **AND** the path-sensitive alignment SHALL remain blocked

#### Scenario: Facade delegation proof is not current
- **WHEN** the facade, owner code contract, selected primary path, or delegation evidence changes after the binding row was produced
- **THEN** Model-Test Alignment SHALL treat the facade binding as stale
- **AND** it SHALL require current delegation evidence before restoring alignment confidence
