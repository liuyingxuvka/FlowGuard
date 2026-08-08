## MODIFIED Requirements

### Requirement: Publication rechecks exact governed inputs without rebuilding results
The read-only review SHALL never execute proof commands. The composed builder SHALL carry the exact identity of the governed inputs it actually consumed. Immediately before returning its result, the review SHALL capture that same input identity once from the repository root and compare it with the builder identity. It SHALL NOT rebuild a second self blueprint, independent denominator, candidate inventory, caller graph, or review result for currentness.

#### Scenario: A new governed source appears during review
- **WHEN** a source, test, model, ledger, binding, provider contract, or reduction-denominator input changes after the reviewed build consumed it
- **THEN** the final exact input comparison SHALL block publication of the earlier review
- **AND** no second result build or fallback authority SHALL be created

#### Scenario: Governed inputs remain unchanged
- **WHEN** the final fresh input identity exactly equals the identity carried by the reviewed build
- **THEN** the one deterministic in-memory review MAY be published
- **AND** currentness SHALL NOT require a duplicate blueprint or denominator materialization

## ADDED Requirements

### Requirement: Exact repeated internal steps may contract to one kernel
Architecture Reduction MAY contract repeated internal steps only when their complete observable contracts match and affected evidence proves the shared kernel preserves the same input, output, ordering, coercion, empty-value, failure, and side-effect behavior. The kernel SHALL remain internal and SHALL NOT create another public route or behavior authority.

#### Scenario: Repeated private normalization steps have one exact contract
- **WHEN** several internal helpers have the same input domain, output value, ordering, coercion, empty-value behavior, side-effect boundary, and failure behavior
- **AND** affected tests prove that replacing each helper with one internal shared kernel preserves those exact semantics
- **THEN** Architecture Reduction MAY replace the repeated helpers with that shared kernel
- **AND** the shared kernel SHALL remain an internal implementation detail rather than becoming a second public route or a new behavior owner

#### Scenario: One helper group is also reported as its own duplicate branch
- **WHEN** the same exact private-helper member set and structural relation is discovered as both a helper path and a duplicate branch
- **THEN** Architecture Reduction SHALL review that member group once through the helper path, whose required routes include the complete branch obligations
- **AND** distinct signals with different behavior questions or downstream routes SHALL remain separately visible rather than being broadly collapsed

#### Scenario: Model and independent checker contain the same helper
- **WHEN** one model implementation and its independently executable checker contain an identical internal helper that participates in the checked operation
- **THEN** Architecture Reduction SHALL retain their separate implementations when sharing the helper would couple the oracle to the implementation
- **AND** the retain decision SHALL bind both current necessity witnesses and the exact model/checker role boundary rather than using similarity or candidate identity as authority

### Requirement: Large boundaries remain structure triggers until a concrete split exists
An oversized source boundary SHALL remain visible to StructureMesh, but Architecture Reduction SHALL consume it as a contraction candidate only after a named FlowGuard FunctionBlock partition provides a concrete target child structure, single owners, facade boundaries, validation boundaries, and a target action.

#### Scenario: Large module has no model-derived split target
- **WHEN** the independent inventory reports an oversized module but no named FlowGuard FunctionBlock partition supplies target child modules, single owners, facade boundaries, and parity boundaries
- **THEN** the oversized boundary SHALL remain a visible StructureMesh trigger with current cost evidence
- **AND** size alone SHALL NOT manufacture an Architecture Reduction candidate, deletion proof batch, or claim that a mechanical file split is more efficient

### Requirement: Ambiguity evidence is complete without Cartesian representation
When several callers reference the same ambiguous raw alias, the reduction review SHALL preserve every exact caller and every exact candidate surface while representing the shared alias ambiguity once. Physical aggregation SHALL NOT select a target, remove a caller, or downgrade the ambiguity blocker.

#### Scenario: Many callers share one ambiguous alias
- **WHEN** multiple governed callers reference one raw alias that resolves to multiple current surfaces
- **THEN** one ambiguity record SHALL contain the complete caller set and complete candidate set
- **AND** candidate members SHALL reference that shared blocker without repeating the complete candidate set for every caller

### Requirement: Full review identity and bounded projection identity are distinct
The architecture-reduction result SHALL expose one stable identity for the complete reviewed facts and a separate identity for any bounded publication projection. A compact projection SHALL consume an already stored full-review identity and SHALL fail if that identity is absent; it SHALL NOT invoke complete-payload expansion or silently substitute its own projection identity.

#### Scenario: Release validation requests compact output
- **WHEN** the complete review has finished and release validation requests its bounded projection
- **THEN** the result SHALL carry both the full review fingerprint and the projection fingerprint
- **AND** the complete candidate, proof, retain, denominator, and readiness checks SHALL remain performed

#### Scenario: Static checker design is closed but execution is planned
- **WHEN** the full review proves static model-code-test design ready while exact leaf execution remains `not_run`
- **THEN** the compact projection SHALL preserve the `not_run` findings as bounded execution-gap counts and examples
- **AND** it SHALL NOT count those execution gaps as static architecture blockers or imply that they passed
- **AND** every genuine static binding, ownership, oracle, or design gap SHALL remain in the blocking counts

### Requirement: Composed and standalone review paths are direct
The standalone review SHALL build one current self blueprint for itself. The composed review SHALL consume the exact bundle and build-input identity created by its caller. A public argument that appears to accept a supplied blueprint while rebuilding another complete blueprint SHALL NOT remain as an alternate path.

#### Scenario: A composed caller already holds the current bundle
- **WHEN** architecture reduction is invoked as part of the self-maintenance composition
- **THEN** the reviewer SHALL consume that exact bundle without rebuilding it
- **AND** invocation-local reuse SHALL remain the only authority path

### Requirement: Candidate review indexes exact shared identities and conflicts once
One candidate-review invocation SHALL freeze each current blueprint identity once and SHALL construct exact membership and conflict lookup structures before using them across candidates. It SHALL NOT recompute a complete manifest fingerprint, rebuild a ready-candidate set, merge the complete contract set, or scan the complete candidate sequence once per candidate.

#### Scenario: Many candidates share one current blueprint and overlapping members
- **WHEN** the reviewer materializes many candidates from one current self blueprint
- **THEN** every candidate SHALL reference the same exact manifest, behavior, implementation, and test identities
- **AND** shared membership and conflict decisions SHALL be derived from one-time exact indexes without removing candidates, actions, or blockers

### Requirement: Shared candidate evidence neighborhoods have one direct-current representation
When multiple self-reduction candidates consume an identical coverage-derived evidence neighborhood, the review SHALL store the exact test ids, coverage ids, covered dimensions, and current receipt ids once in a content-addressed catalog. Each candidate SHALL carry one exact catalog id and fingerprint instead of an inline duplicate. Its canonical observable-contract identity SHALL be a typed composite of the candidate-local caller, behavior, model, owner, state, effect, and error fields plus that exact neighborhood fingerprint. Resolving the reference SHALL reproduce the candidate's complete semantic observable contract without changing any caller, behavior block, model element, owner, state, effect, error, test, coverage, dimension, or receipt fact.

#### Scenario: Many candidates share one behavior evidence neighborhood
- **WHEN** multiple candidates consume the same exact coverage-derived test neighborhood
- **THEN** the physical catalog SHALL contain one exact neighborhood row and each candidate SHALL reference it
- **AND** resolving every reference SHALL reproduce the same complete semantic contracts that an unnormalized representation would express while the canonical identity hashes each shared neighborhood once

#### Scenario: Candidate evidence reference is missing or inconsistent
- **WHEN** a candidate reference is missing, duplicated, unknown, stale, ambiguous, accompanied by an inline fallback copy, or resolves to a contract whose fingerprint differs from the candidate binding
- **THEN** self-reduction review and proof consumption SHALL fail closed
- **AND** no compatibility reader, alternate catalog, inferred neighborhood, or silent downgrade SHALL authorize the candidate

### Requirement: Audit completion, action authorization, and cleanup readiness are separate claims
A whole-target or self-reduction report SHALL distinguish: (1) whether the current source, blueprint, denominator, and every candidate disposition were completely audited; (2) whether one exact candidate has independent current evidence authorizing a contraction action; and (3) whether cleanup is release-ready. A complete audit MAY pass while proofless candidates remain explicitly `unresolved` with a risky-keep boundary, but `cleanup_release_ready` SHALL remain false. A proof-authorized candidate that has not yet been applied SHALL remain visible and SHALL block the release self-maintenance audit. Cleanup SHALL be release-ready only when the audit is complete, no unresolved candidate remains, and no authorized cleanup action remains unapplied.

#### Scenario: Complete audit finds only proofless contraction candidates
- **WHEN** the source and blueprint are current, the independent denominator is complete, every candidate is accounted for, and the remaining candidates lack independent contraction proof
- **THEN** the audit status SHALL pass and preserve those candidates as `unresolved` risky keep without changing code
- **AND** `cleanup_release_ready` SHALL remain false

#### Scenario: A safe candidate has not been applied
- **WHEN** current independent evidence authorizes one contraction but the action has not been applied and revalidated
- **THEN** the release self-maintenance audit SHALL remain blocked
- **AND** the exact authorized action SHALL stay visible rather than being treated as completed or unresolved

#### Scenario: An audit input or denominator member is missing
- **WHEN** source currentness, blueprint qualification, independent candidate discovery, or disposition accounting is incomplete
- **THEN** the audit itself SHALL be blocked
- **AND** neither action authorization nor cleanup readiness SHALL be inferred

#### Scenario: Every candidate is resolved and every authorized action is complete
- **WHEN** the audit is complete, no unresolved candidate remains, and no authorized cleanup action remains unapplied
- **THEN** the report SHALL pass and `cleanup_release_ready` SHALL be true
- **AND** that cleanup conclusion SHALL remain separate from the audit fingerprint and each candidate's proof identity

### Requirement: Reduction keeps behavior ownership, execution ownership, and receipts distinct
The self-reduction denominator SHALL interpret test and checker fields according to their declared layer. A supporting or legally scoped-out test node MAY have no exact behavior owner and SHALL remain represented by its independent test identity. A behavior-coverage disposition SHALL carry its required behavior owner. Native execution ownership SHALL come only from `CoverageExecutionEvidence.execution_owner_id`, and terminal receipt evidence SHALL remain a separate execution-currentness fact.

#### Scenario: A required ordinary test is supporting evidence
- **WHEN** the independent test inventory contains a required test node whose disposition is `supporting` and whose behavior owner set is empty
- **THEN** the reduction universe SHALL keep that test node once using its current source identity
- **AND** it SHALL NOT create a missing check owner, infer an owner from file globs, or duplicate the node as a checker-design member

#### Scenario: Many planned checks share one native execution owner
- **WHEN** multiple exact behavior-coverage rows name the same native execution owner
- **THEN** the reduction universe SHALL contain one execution-owner member with one exact aggregate design fingerprint over its covered rows
- **AND** any passing receipts MAY attach as separate execution evidence without being required to prove that the owner exists

#### Scenario: A coverage disposition lacks its required behavior owner
- **WHEN** a `behavior_coverage` or `cross_owner_integration` disposition has no required exact behavior owner
- **THEN** the reduction audit SHALL report a typed coverage-owner gap
- **AND** it SHALL NOT mislabel that gap as a native execution-owner failure

### Requirement: Current necessity is proven independently of structural identity
Every retained implementation surface SHALL carry one direct-current necessity witness binding current intent authority, one exact behavior/model/code owner, source-independent semantic specifications, and model-code-test evidence. Current-consumer and active reviewed external-commitment evidence SHALL remain exact member-local contraction context rather than a universal prerequisite for representing current software: framework callbacks, protocol methods, properties, and externally invoked surfaces MAY have no statically resolved Python caller. A candidate-level aggregate caller set SHALL remain discovery context and SHALL NOT be copied onto every member as necessity authority. An external commitment counts only when one current BCL review binds its exact primary model, the same blueprint owner contract, and current test evidence; the ledger SHALL be loaded and reviewed once for the audit rather than once per candidate. Candidate identity, source path, symbol, owner/model/spec/oracle/test/receipt ids, and raw structure-derived semantics SHALL remain evidence only and SHALL NOT contribute to the normalized semantic-obligation fingerprint. Any contraction candidate SHALL still preserve exact caller parity and SHALL block on unresolved caller identity before merge or removal is authorized.

#### Scenario: Different structures implement the same current semantics
- **WHEN** two candidate members have different paths, symbols, owner ids, model ids, semantic-spec ids, oracle ids, tests, or receipts but their normalized source-independent semantics are identical
- **THEN** those identity differences SHALL NOT authorize a different-current-semantics retain decision
- **AND** the candidate SHALL remain unresolved until it is split or receives current contraction proof

#### Scenario: Every member has genuinely different current semantics
- **WHEN** every candidate member has one complete current necessity witness and their normalized semantic-obligation fingerprints are pairwise different
- **THEN** one typed `different_current_semantics` disposition MAY retain the members independently
- **AND** the candidate id SHALL scope the comparison without acting as authority or changing any member witness

#### Scenario: Retention does not need contraction caller proof
- **WHEN** a structural candidate's members have pairwise different current semantics but the bounded static caller graph contains unresolved dynamic caller identities
- **THEN** the typed `different_current_semantics` disposition MAY retain the unchanged members because no merge, removal, or delegation is being authorized
- **AND** the caller gaps SHALL remain visible as contraction-only context instead of blocking the retain decision or triggering semantic proof execution

#### Scenario: Unreferenced helper still has direct-current necessity
- **WHEN** an `unreferenced_helper` candidate has one complete current necessity witness per member even though the bounded static caller graph does not identify an exact caller
- **THEN** the existing member-local `current_necessity_witness` dispositions SHALL retain the unchanged helper steps
- **AND** FlowGuard SHALL NOT execute deletion-equivalence proofs merely to justify keeping behavior whose current model, owner, semantics, and test bindings are already complete

#### Scenario: A candidate group contains a partial semantic repeat
- **WHEN** at least two members share one normalized semantic obligation even if another member differs
- **THEN** the whole candidate group SHALL NOT receive a different-current-semantics retain decision
- **AND** the repeated subset SHALL remain available for splitting or contraction review

#### Scenario: A public role has no current promise
- **WHEN** an entrypoint or export is selected as a contraction candidate but has neither a resolved current consumer nor an active current Behavior Commitment Ledger promise bound to its exact model/code owner
- **THEN** the public role alone SHALL NOT authorize merge or removal
- **AND** the candidate SHALL retain explicit public-facade, BCL-anchor, and caller-parity proof obligations

#### Scenario: A candidate caller belongs to only one member
- **WHEN** a candidate-level caller set proves that one group member is consumed but does not bind that caller to another member
- **THEN** the aggregate caller SHALL NOT satisfy the other member's current necessity witness
- **AND** the other member SHALL remain unresolved unless its exact implementation binding or active reviewed external commitment supplies current necessity

#### Scenario: A protocol method has no statically resolved Python caller
- **WHEN** one framework callback, protocol method, property, or externally invoked surface has exact current intent, semantics, owner binding, validation evidence, and path-quality evidence but the bounded static reference graph has no exact caller edge
- **THEN** the current-necessity witness SHALL remain valid and SHALL record the empty or incomplete caller context honestly
- **AND** any later contraction candidate containing that surface SHALL still require caller-consumer parity and resolution of every caller ambiguity before an action is authorized

#### Scenario: An external promise is not bound to the current code owner
- **WHEN** an active BCL commitment names the current primary model but its evidence does not include the exact owner contract used by the current blueprint or lacks current test evidence
- **THEN** the commitment SHALL NOT satisfy the implementation necessity witness
- **AND** the audit SHALL report the missing model-code-test bridge rather than retaining the surface from the model name alone

#### Scenario: Sibling implementation surfaces share one behavior block
- **WHEN** several implementation surfaces participate in one behavior block but its coverage edges name different exact implementation-surface and test-node pairs
- **THEN** each necessity witness SHALL consume only coverage edges whose implementation surface equals that witness member
- **AND** another surface's planned test SHALL NOT block the member or be inherited as its coverage evidence

#### Scenario: One surface omits its own executable coverage test
- **WHEN** a coverage edge names the exact implementation surface and one current ordinary test-inventory node but that surface's implementation binding omits the test identity
- **THEN** the necessity witness SHALL report a typed planned-coverage binding mismatch
- **AND** a sibling surface's test, a model-regression identity, or a block-level aggregate SHALL NOT fill the missing exact edge

#### Scenario: Planned checker design and executable evidence use different identities
- **WHEN** one exact surface has current `checker-design:` coverage rows while its implementation binding carries current `test-node:` and `check:` evidence
- **THEN** the necessity witness SHALL retain both layers without requiring their ids to be equal
- **AND** the planned checker SHALL NOT be projected as an executed test, passing receipt, or ordinary coverage edge

#### Scenario: A model owner has an additional native validation check
- **WHEN** an implementation binding carries its exact `check:model-regression:<model_id>` identity plus another current fingerprinted owner-native `check:` identity
- **THEN** both validation identities SHALL remain accepted current evidence
- **AND** the owner-native check SHALL NOT be misclassified as an unknown ordinary test or replace the canonical model-regression identity

#### Scenario: A module-level branch is outside every nested function
- **WHEN** the complete syntax scan observes a branch at module scope beyond the declaration line reported for the Python `ast.Module` surface
- **THEN** the module surface SHALL own that branch in the complete denominator
- **AND** a narrower current class or function surface SHALL still own every branch inside its exact line interval

### Requirement: Historical-looking names are signals rather than singleton candidates
A maintenance-like name SHALL contribute a discovery signal only. The review SHALL materialize a historical-path reduction candidate only when at least two current surfaces have an exact shared call or structure relation; it SHALL NOT create a singleton candidate solely because a symbol contains `legacy`, `compat`, `fallback`, `alias`, or a similar word.

#### Scenario: One isolated helper has a historical-looking name
- **WHEN** one current surface has a maintenance-like name but no exact related current surface
- **THEN** the surface SHALL retain its typed discovery classification without producing a reduction candidate
- **AND** candidate and proof counts SHALL remain unchanged by the isolated name

### Requirement: Self-reduction proofs have one canonical persistent authority
The read-only self-reduction audit SHALL discover strict proof records only from exact-current aggregate receipts in the canonical validation-owner store. It SHALL reconstruct records from the aggregate evidence context, ignore stale historical receipts as history, block multiple exact-current producers, and SHALL NOT accept a caller-injected proof registry. Proof execution SHALL be a separate explicit batch action that freezes one bundle and candidate inventory, selects exact candidate ids and fingerprints, reuses an exact-current receipt before execution, and otherwise publishes one aggregate owner receipt.

#### Scenario: A current aggregate proof already exists
- **WHEN** one canonical aggregate receipt exactly matches the current subject, bundle, candidate inventory, selected candidates, toolchain, environment, obligations, and child evidence
- **THEN** the producer SHALL reuse it without rerunning proof commands
- **AND** the next read-only audit SHALL discover the same strict proof authority automatically

#### Scenario: Stale and duplicate proof receipts exist
- **WHEN** stale historical receipts are present and more than one receipt claims the same exact-current proof authority
- **THEN** stale receipts SHALL remain non-authoritative history
- **AND** duplicate exact-current authority SHALL block rather than selecting by timestamp, filename, or declaration order

### Requirement: Compact self-reduction gaps are typed and bounded
When a current implementation surface cannot obtain a necessity witness, the full self-reduction review SHALL record one deterministic first-failure gap kind for that surface. The compact projection SHALL aggregate exact counts by gap kind and SHALL include only a bounded number of representative member ids for each kind. It SHALL NOT emit the complete unresolved member set, omit the reason distribution, or rerun candidate discovery merely to explain the blocker.

#### Scenario: Thousands of surfaces lack the same witness component
- **WHEN** many current implementation surfaces fail the same exact necessity-witness condition
- **THEN** the compact review SHALL report their exact aggregate count under one typed gap kind
- **AND** it SHALL expose at most the declared bounded number of representative member ids for that kind
- **AND** the omitted member identities SHALL remain available only in the already materialized full review

#### Scenario: A surface becomes independently necessary
- **WHEN** the current review can construct a complete necessity witness for a previously blocked surface
- **THEN** that surface SHALL contribute no necessity-gap row
- **AND** stale gap state from an earlier candidate or review SHALL NOT remain in the current aggregation
