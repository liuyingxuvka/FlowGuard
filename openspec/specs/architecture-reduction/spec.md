# architecture-reduction Specification

## Purpose
This capability defines FlowGuard's Architecture Reduction behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Observable architecture contract
FlowGuard SHALL require an architecture reduction review to declare the source model, source code boundary, observable public entrypoints, observable outputs, observable state, observable side effects, validation boundaries, and rationale before reporting a reduction as ready.

#### Scenario: Complete observable contract
- **WHEN** an architecture reduction review includes source model identity, source structure identity, observable behavior fields, validation boundaries, and rationale
- **THEN** the review may classify reduction candidates by proof status

#### Scenario: Missing observable contract blocks reduction
- **WHEN** an architecture reduction review omits the observable behavior contract or validation boundaries
- **THEN** the review reports missing-contract findings and does not return a ready decision

### Requirement: Code contraction candidates
FlowGuard SHALL represent model-backed code contraction opportunities as
structured candidates with candidate type, target code node, source model
element, rationale, affected public entrypoints, affected state, affected side
effects, proof status, required next route, and current lifecycle disposition.
When a candidate is linked to an old, alternate, or compatibility-like surface,
Architecture Reduction SHALL classify that surface before reporting the
candidate as ready.

#### Scenario: Safe candidate is reported with proof status
- **WHEN** a handler, module, branch, adapter, or state field has a declared
  reduction candidate with behavior-preserving evidence and no completed
  implementation evidence
- **AND** any linked compatibility surface has a classification that permits
  contraction
- **THEN** the review reports the candidate with a proof status and the next
  route needed before code changes

#### Scenario: Current contract blocks removal
- **WHEN** a reduction candidate removes or collapses a surface classified as a
  current contract
- **THEN** the review blocks the candidate instead of treating it as safe code
  contraction

#### Scenario: Negative legacy test remains visible
- **WHEN** a reduction candidate removes a surface classified as negative
  legacy test evidence
- **THEN** the review blocks or downgrades the candidate unless replacement
  rejection evidence is cited

#### Scenario: Evidence-needed surface blocks readiness
- **WHEN** a reduction candidate is linked to a compatibility surface whose
  classification is evidence-needed
- **THEN** the review does not report that candidate as ready

### Requirement: Target structure handoff
FlowGuard SHALL produce a target architecture summary that can be consumed by Code Structure Recommendation or StructureMesh, including merge, collapse, remove, keep-facade, and manual-review actions.

#### Scenario: Reduction feeds target structure
- **WHEN** all ready candidates have required proof status and observable contract coverage
- **THEN** the review includes target actions that can be translated into module ownership, facade, and validation-boundary recommendations

#### Scenario: Public entrypoint requires facade gate
- **WHEN** a candidate affects a public entrypoint
- **THEN** the review requires a StructureMesh or equivalent public-entrypoint parity gate before code contraction can be claimed complete

### Requirement: Companion route triggers
FlowGuard SHALL define complexity-growth triggers that allow DevelopmentProcessFlow, Existing Model Preflight, Code Structure Recommendation, StructureMesh, ModelMesh, Model-Test Alignment, and UI Flow Structure to invoke architecture reduction without making it a universal gate.

#### Scenario: Development process complexity trigger
- **WHEN** staged development adds repeated phases, adapters, branches, or validation layers around the same behavior before implementation or done/release claims
- **THEN** DevelopmentProcessFlow guidance points to architecture reduction before more structure is added

#### Scenario: Existing boundary duplicate trigger
- **WHEN** Existing Model Preflight detects duplicate ownership or a proposed boundary overlaps an existing responsibility
- **THEN** the agent can route to architecture reduction to consider merging or deleting the duplicate structure

#### Scenario: Structure refactor trigger
- **WHEN** a large code refactor is proposed and the target structure may be smaller than the current module graph
- **THEN** StructureMesh or Code Structure Recommendation can consume architecture reduction output before implementation

### Requirement: No automatic code rewrite
FlowGuard SHALL treat architecture reduction as a review and handoff capability, not as automatic production code rewriting.

#### Scenario: Candidate requires implementation gate
- **WHEN** an architecture reduction report identifies safe code contraction candidates
- **THEN** production code changes still require the appropriate StructureMesh, DevelopmentProcessFlow, tests, and conformance evidence before completion is claimed

### Requirement: Compatibility surface classification
FlowGuard SHALL let Architecture Reduction classify old aliases, alternate
paths, migration branches, pass-through compatibility adapters, public facades,
retired validation artifacts, and legacy rejection tests before contraction is
claimed ready. Compatibility-only fields, aliases, wrappers, or guidance MAY be
removed when the classification proves they are obsolete and not a current
contract, safety classifier, public facade, runtime-authoritative archive, or
negative legacy test without replacement evidence.

#### Scenario: Boundary adapter is kept at the edge
- **WHEN** a compatibility surface is classified as a boundary adapter
- **AND** it affects a public entrypoint
- **THEN** the review requires StructureMesh or equivalent public-entrypoint
  parity before contraction can be claimed complete

#### Scenario: Archive-only surface has runtime authority
- **WHEN** a compatibility surface is classified as archive-only
- **AND** the surface still has runtime authority
- **THEN** the review blocks the classification until the authority is removed
  or the classification changes

#### Scenario: Prune candidate follows proof status
- **WHEN** a compatibility surface is classified as a prune candidate
- **AND** the linked reduction candidate has safe equivalence, public-facade
  proof status, or a complete authorized retirement proof
- **THEN** Architecture Reduction may report the candidate as ready subject to
  the ordinary next-route requirements

#### Scenario: Classification appears in report
- **WHEN** Architecture Reduction reviews compatibility surfaces
- **THEN** the report includes the surface classifications, recommendations,
  evidence references, and missing evidence so downstream routes can preserve
  the decision boundary

#### Scenario: Obsolete compatibility field is removed
- **WHEN** a field, alias, wrapper, or prompt instruction exists only to
  preserve an old FlowGuard surface
- **AND** the current route-first API or an exact current `CanonicalRelation`
  emitted by the observed blueprint, behavior-commitment, or topology owner
  covers the same maintenance obligation
- **AND** the surface is not a current contract, safety classifier, public
  facade, runtime-authoritative archive, or unreplaced negative legacy test
- **THEN** FlowGuard may remove the old surface instead of preserving parallel
  compatibility paths

#### Scenario: Safety classifier is not removed as compatibility bloat
- **WHEN** a rule classifies current contracts, public facades,
  runtime-authoritative archives, negative legacy tests, or unknown
  compatibility surfaces before deletion
- **THEN** the rule remains part of Architecture Reduction unless a newer
  current guard provides equivalent protection and tests prove the handoff
  boundary

### Requirement: Architecture Reduction classifies old fields
Architecture Reduction SHALL classify old fields, field aliases, compatibility
field adapters, migration field branches, and retired field validation evidence
before contraction or replacement cleanup is claimed ready.

#### Scenario: Old field is a prune candidate
- **WHEN** an old field exists only for a replaced behavior
- **AND** current field lifecycle and model-code-test evidence prove the new
  field covers the behavior
- **THEN** Architecture Reduction MAY classify the old field as a prune
  candidate subject to implementation and validation gates

#### Scenario: Old field has runtime authority
- **WHEN** an archive-only or compatibility field can still affect runtime
  behavior
- **THEN** Architecture Reduction MUST block removal readiness until runtime
  authority is removed, delegated, migrated, or explicitly preserved with
  evidence

### Requirement: Obsolete case-generation surfaces are cleanup candidates
FlowGuard ArchitectureReduction MUST classify old same-class generators,
fallback prompt paths, aliases, wrappers, and compatibility-like case surfaces
as cleanup candidates unless they are current public contracts, safety
classifiers, public facades, archives, or negative legacy tests with current
evidence.

#### Scenario: Old generator is not current contract
- **WHEN** an old same-class generator duplicates ContractExhaustionMesh and is
  not a public contract or safety classifier
- **THEN** ArchitectureReduction can classify it as a prune candidate

#### Scenario: Public facade routes through structure proof
- **WHEN** an old surface must stay reachable as a public facade
- **THEN** FlowGuard requires StructureMesh or equivalent parity evidence
  instead of treating the facade as a fallback generator

### Requirement: ArchitectureReduction classifies old helper surfaces
ArchitectureReduction SHALL classify old helper prompts, route ids, aliases,
template commands, wrappers, and compatibility-like surfaces before they remain
reachable after a route-control-plane consolidation.

#### Scenario: Helper route is absorbed
- **WHEN** an old helper route duplicates a current public owner route
- **THEN** ArchitectureReduction MUST classify it as absorb, delete,
  internal-helper, or facade-review before implementation claims completion

#### Scenario: Fallback prompt is not retained
- **WHEN** an old prompt path only exists to keep a legacy route available
- **THEN** ArchitectureReduction MUST classify it as a prune candidate unless
  current public-contract evidence proves it is a facade

### Requirement: Retained facades require route evidence
ArchitectureReduction SHALL require current owner-route evidence before an old
helper surface can remain as a public facade.

#### Scenario: Public facade is kept
- **WHEN** a retained helper surface is user-facing or externally documented
- **THEN** ArchitectureReduction MUST require StructureMesh or equivalent
  public-entrypoint parity evidence before the facade remains public

### Requirement: Architecture reduction disposes fallback surfaces
ArchitectureReduction SHALL classify old paths, aliases, wrappers, helper
routes, compatibility facades, and fallback candidates that overlap a primary
business intent and require a target action before broad confidence.

#### Scenario: Silent runtime fallback requires removal or blocking
- **WHEN** an architecture candidate can run as an alternate implementation
  after primary failure
- **THEN** ArchitectureReduction SHALL classify it as a silent runtime fallback
  or equivalent blocking surface

#### Scenario: Public facade delegates to primary
- **WHEN** a public compatibility facade remains in scope
- **THEN** ArchitectureReduction SHALL require evidence that it delegates to
  the primary path and does not own business behavior

### Requirement: Reduction consumes observed-system ownership
Architecture Reduction SHALL derive duplicate authority, obsolete route,
compatibility discovery, shared-kernel, and orphan candidates from the
validated observed model-system snapshot and its owner evidence.

#### Scenario: Two helpers are syntactically identical but semantically owned by different contracts
- **WHEN** duplicate code lacks observable-contract equivalence or a shared-kernel relation with parity evidence
- **THEN** Architecture Reduction keeps the candidate blocked

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

#### Scenario: Compatibility discovery duplicates the current manifest authority
- **WHEN** all supported runners are explicitly registered and undeclared runners fail visibly
- **THEN** the obsolete compatibility discovery path MAY be removed with manifest and runner parity evidence

### Requirement: Architecture Reduction accounts the complete same-intent candidate inventory
FlowGuard SHALL require an Architecture Reduction plan driven by Existing Model Preflight, the independent same-intent surface inventory, or canonical relation handoffs to declare the complete expected set of duplicate, same-workflow, adapter, alias, wrapper, helper, fallback, and facade candidates for each in-scope stable business intent.

#### Scenario: Expected reduction candidate is omitted
- **WHEN** preflight, the same-intent surface inventory, or a current canonical relation identifies an in-scope surface but no reduction candidate or explicit keep, false-friend, manual-review, or scoped disposition represents it
- **THEN** Architecture Reduction SHALL report the expected candidate as missing
- **AND** it SHALL NOT treat the caller-selected candidate subset as a complete contraction review

#### Scenario: Complete candidate inventory has dispositions
- **WHEN** every expected same-intent candidate is materialized and classified as merge, collapse, remove, delegate, keep-facade, retire_behavior, manual-review, or scoped with reason
- **THEN** Architecture Reduction MAY report candidate-inventory completeness
- **AND** the report SHALL expose the expected, materialized, and scoped candidate ids

#### Scenario: Candidate inventory evidence is stale
- **WHEN** the source surface inventory, canonical relations, affected business-intent boundary, or owner identity changes after candidate classification
- **THEN** Architecture Reduction SHALL mark the candidate inventory stale
- **AND** no broad contraction-readiness claim SHALL rely on that inventory

### Requirement: Retained same-intent facades prove delegation to the selected primary path
FlowGuard SHALL allow a public facade, alias, adapter, or wrapper to remain after contraction only when it preserves the external entrypoint by delegating to the selected primary path and does not retain independent business authority.

#### Scenario: Facade is retained as a delegating boundary
- **WHEN** a same-intent public surface must remain for compatibility
- **AND** current evidence binds the surface to the stable business intent, active behavior commitment, selected primary path, and owner code contract
- **THEN** Architecture Reduction MAY classify the surface as keep-facade or delegate
- **AND** the target action SHALL preserve only the delegating boundary

#### Scenario: Facade can succeed independently
- **WHEN** a retained facade can return business success, perform the primary side effect, or mutate the business terminal without invoking the selected primary path
- **THEN** Architecture Reduction SHALL classify it as parallel business authority or silent fallback
- **AND** the candidate SHALL NOT be ready as a retained facade

#### Scenario: Facade delegates to a different path for the same intent
- **WHEN** facade evidence names the expected `business_intent_id` but delegates to a primary-path id different from the selected path
- **THEN** Architecture Reduction SHALL report same-intent path drift
- **AND** the facade SHALL require repair, removal, or a genuinely different typed business intent before readiness

### Requirement: FlowGuard release uses its completed self blueprint for safe contraction
Before publishing a FlowGuard release, FlowGuard SHALL use the current completed self blueprint and independently discovered implementation inventory to review in-scope repeated routes, branches, adapters, wrappers, facades, helpers, validation paths, and historical product behaviors. The review SHALL classify every discovered surface by current software-DNA necessity and account it with a typed retain, ordinary behavior-preserving contraction, delegating-facade, authorized `retire_behavior`, or unresolved disposition. Public-entrypoint contraction SHALL require StructureMesh parity; intentional behavior retirement SHALL require the complete retirement responsibility proof; both SHALL require affected revalidation. Uncertain, stale, property-only, or incompletely dispositioned candidates SHALL remain visible rather than being silently removed.

#### Scenario: Duplicate path is safely contracted before release
- **WHEN** the current self blueprint identifies repeated implementation paths for the same modeled obligation
- **AND** current evidence proves observable equivalence or a facade that only delegates to the selected primary owner
- **THEN** ArchitectureReduction may hand the ordinary contraction to StructureMesh and DevelopmentProcessFlow
- **AND** the release SHALL revalidate every affected model, public entrypoint, state, side effect, and test boundary before completion

#### Scenario: Historical behavior is intentionally retired before release
- **WHEN** the current self blueprint proves that a historical behavior is no longer necessary for the current product goal
- **AND** an authorized retirement proof dispositions every active responsibility, consumer, negative case, interface, model, code, test, topology, prompt, skill, and release claim
- **THEN** ArchitectureReduction may hand the intentional retirement to DevelopmentProcessFlow without claiming observable equivalence for the removed behavior
- **AND** the release SHALL reject every old current name directly and revalidate every responsibility-transfer owner

#### Scenario: Apparent duplication lacks behavior-equivalence evidence
- **WHEN** a route, branch, behavior, adapter, wrapper, helper, facade, or validation path appears unnecessary
- **BUT** current evidence proves neither ordinary equivalence/facade delegation nor complete intentional-retirement authority
- **THEN** FlowGuard SHALL retain the surface as an unresolved typed disposition
- **AND** the candidate SHALL NOT be deleted merely to reduce code size

### Requirement: Blueprint-driven reduction candidates are independently complete
ArchitectureReduction SHALL derive each contraction candidate from the current observed blueprint, independent implementation inventory, exact same-intent surface inventory, and current model-semantic-code-test evidence. Each candidate SHALL name the retained owner, proposed removed or delegated surfaces, observable contract, state and side effects, callers and consumers, proof status, and required affected revalidation.

#### Scenario: Duplicate-looking helpers have different effects
- **WHEN** two helpers share structure or names but current blueprint evidence shows different state writes, side effects, errors, or consumers
- **THEN** they are not an equivalence-ready contraction candidate
- **AND** similarity alone does not authorize merging or deletion

#### Scenario: One facade delegates completely
- **WHEN** a public facade has no independent success behavior and current evidence proves complete delegation to the retained primary path
- **THEN** ArchitectureReduction MAY classify the facade for retained-delegating or removable treatment according to its external contract
- **AND** the selected disposition remains explicit

#### Scenario: Candidate inventory omits a same-intent path
- **WHEN** independent discovery finds a same-intent adapter, wrapper, helper, alias, or public entrypoint absent from the candidate inventory
- **THEN** candidate completeness is blocked
- **AND** no contraction action is reported ready

### Requirement: Contraction requires behavior-preserving proof and lineage repair
An ordinary contraction SHALL require equivalence-proven replacement or facade-proven delegation. An intentional product-behavior removal SHALL instead require target action `retire_behavior` plus an authorized complete retirement proof. After either action, the same current model lineage, implementation inventory, bindings, contracts, tests, topology, consumers, and affected evidence SHALL be updated together; uncertain or incomplete candidates SHALL remain typed unresolved obligations.

#### Scenario: Removal would orphan a model or test binding
- **WHEN** a proposed removed surface is still the sole implementation, consumer, CodeContract target, or test target for an active obligation
- **THEN** reduction is blocked until a valid replacement or intentional retirement disposition is modeled and evidenced
- **AND** the surface is not deleted as dead code

#### Scenario: Evidence-ready contraction is applied
- **WHEN** an authorized ordinary contraction preserves the observable contract and every affected owner has a current target disposition
- **THEN** the resulting candidate revision updates the implementation inventory and all affected bindings
- **AND** affected model, test, topology, structure, installation, and process evidence is revalidated before closure

#### Scenario: Evidence-ready behavior retirement is applied
- **WHEN** an authorized `retire_behavior` action has a complete responsibility inventory and every still-required protection has one current owner
- **THEN** the resulting candidate revision removes the retired current behavior and updates every affected binding and consumer disposition
- **AND** the release preserves only immutable history while old runtime, API, CLI, route, prompt, skill, and model identities fail visibly

#### Scenario: A candidate remains uncertain
- **WHEN** equivalence, facade delegation, current necessity, external use, side-effect ownership, or retirement responsibility cannot be established
- **THEN** ArchitectureReduction records the exact unresolved question and owner
- **AND** it does not convert uncertainty into a cleanup recommendation

### Requirement: Self-reduction review is fingerprinted machine evidence
A FlowGuard pre-release self-reduction review SHALL bind the exact self-blueprint fingerprint, independently declared candidate denominator, observable contracts, proof status, target action, required next route, and residual risk for every candidate. Narrative notes SHALL NOT substitute for this report.

#### Scenario: Narrative lists three completed reductions
- **WHEN** a self-audit document names reductions but no current machine report binds their candidate universe and proof
- **THEN** reduction review SHALL remain not run for release purposes

#### Scenario: Candidate lacks equivalence evidence
- **WHEN** a candidate may reduce code but current behavior-preservation evidence is incomplete
- **THEN** it SHALL remain `blocked_by_missing_evidence` or `manual_review`
- **AND** no cleanup SHALL occur automatically

### Requirement: Self-reduction reviews the complete duplicate-path denominator
Blueprint-guided self-reduction SHALL discover candidate duplicate command routes, branches, adapters, wrappers, facades, helpers, validation paths, and repeated structures within the declared FlowGuard boundary. Every candidate SHALL receive an explicit retain, contract, or unresolved disposition.

#### Scenario: Duplicate path is not an oversized module
- **WHEN** two command or validation paths appear to own the same externally visible intent without forming an oversized module or identical syntax tree
- **THEN** the candidate inventory SHALL still include the relation for review

### Requirement: Broader discovery does not authorize deletion
No reduction candidate SHALL be contracted unless current observable-contract, primary-owner, equivalence or delegation, caller, lifecycle, and required-validation evidence licenses the action.

#### Scenario: Similar helpers lack equivalence proof
- **WHEN** two helpers look similar but their behavior equivalence and caller migration are unproven
- **THEN** the reduction report SHALL keep them unresolved
- **AND** no cleanup step SHALL delete or merge them

### Requirement: Self-reduction caller discovery is indexed once
The self-reduction reviewer SHALL derive caller ownership from one deterministic reverse call-alias index over the current governed implementation surfaces. It SHALL NOT rescan the complete surface inventory separately for every candidate member, and the indexed result SHALL preserve the exact caller identities produced by the declared call-matching semantics.

#### Scenario: A large self-blueprint contains many candidate members
- **WHEN** the reviewer evaluates caller relations for multiple oversized, route, branch, adapter, wrapper, helper, or validation candidates
- **THEN** each governed surface contributes its call aliases to the reverse index once
- **AND** candidate lookup returns the same exact caller set without a member-by-all-surfaces nested scan

### Requirement: Composed self-maintenance reuses one exact blueprint
When one invocation requests both self-blueprint qualification and architecture-reduction review, the command SHALL build the self-blueprint once and pass that exact fingerprinted bundle to the reduction reviewer. Reuse SHALL remain invocation-local and SHALL NOT create a fallback or second authority.

#### Scenario: Blueprint and reduction are reviewed together
- **WHEN** a caller selects the composed self-maintenance option
- **THEN** the result reports the same self-blueprint fingerprint in both bounded reviews
- **AND** no second self-blueprint build is executed

#### Scenario: A governed input changes before another invocation
- **WHEN** source, test, resource, model, or intent evidence changes
- **THEN** the next composed invocation builds a new current blueprint
- **AND** no prior in-memory or serialized bundle is silently accepted

### Requirement: Compact self-maintenance projects bounded fields directly
When compact output is requested, the composed self-maintenance command SHALL derive its bounded summary directly from the in-memory blueprint and reduction objects. It SHALL NOT first expand the complete blueprint or complete reduction payload merely to discard most of that material.

#### Scenario: A complete self-blueprint contains many code and test bindings
- **WHEN** the caller requests compact composed self-maintenance output
- **THEN** the command emits the declared bounded status and identity fields without invoking complete-payload expansion
- **AND** the full-detail path remains available only when the caller explicitly omits compact mode

### Requirement: Immutable large evidence fingerprints are computed once
Large immutable blueprint evidence consumed by more than one stage SHALL compute its canonical fingerprint once per object and reuse that exact value for downstream composition. Reuse SHALL NOT alter the fingerprint payload or create a mutable cache authority.

#### Scenario: Behavior evidence feeds both blueprint qualification and reduction
- **WHEN** the same immutable behavior report is consumed by both stages in one composed invocation
- **THEN** its complete fingerprint payload is evaluated once
- **AND** both stages receive the exact same canonical fingerprint

### Requirement: Large canonical payloads are fingerprinted without complete-copy amplification
Canonical fingerprint and byte-count calculation for a large blueprint payload SHALL stream the exact canonical JSON representation. The implementation SHALL NOT retain several complete serialized copies of the same logical payload while constructing its normalized physical projection.

#### Scenario: A normalized blueprint contains many exact coverage edges
- **WHEN** normalization computes logical identity, logical size, source size, and physical size
- **THEN** the canonical encoder feeds each fingerprint and count incrementally
- **AND** the logical payload is released before the physical projection is materialized

### Requirement: Cleanup completeness uses an independent candidate denominator
A whole-target or self-cleanup review SHALL derive its expected candidates independently from the review that classifies proof. The denominator SHALL cover applicable command routes, branches, adapters, wrappers, facades, helpers, repeated validations, duplicate owners, and oversized boundaries, and every member SHALL end as `retain`, `contract`, or `unresolved`.

#### Scenario: Discovery source is disabled and candidates become empty
- **WHEN** one required discovery source is unavailable and the candidate list is empty
- **THEN** cleanup completeness SHALL be unknown or incomplete
- **AND** it SHALL NOT claim that nothing needs cleanup

### Requirement: Self-reduction dispositions are explicit current evidence
Every denominator surface and signal SHALL receive an independently produced typed disposition bound to the exact current self-blueprint, target revision, implementation inventory, denominator fingerprint, and candidate identity when the signal forms a contraction candidate. A singleton signal MAY be retained only when its exact source surface has a current public contract, behavior owner, or unique delegation owner. A signal that forms a contraction candidate SHALL NOT be retained merely because its source surface exists; it requires either candidate-specific evidence that the compared members have different commitments or observable contracts, or current contraction proof. Absence of either authority SHALL remain `unresolved` and block cleanup release readiness.

#### Scenario: Unmatched branch is automatically labeled retain
- **WHEN** independent discovery finds a branch signal that has no current typed retain record and no verified contraction proof
- **THEN** the branch SHALL remain `unresolved`
- **AND** the cleanup report SHALL NOT become release-ready

#### Scenario: Caller supplies a label-only self-blueprint
- **WHEN** a caller supplies an object with passing labels or fingerprints that is not the exact typed blueprint rebuilt from the current target root
- **THEN** self-reduction SHALL reject the object before candidate classification

#### Scenario: An owned singleton helper has no contraction relation
- **WHEN** one helper signal does not form a multi-surface contraction candidate
- **AND** its exact source surface has a current behavior owner and current source evidence
- **THEN** self-reduction MAY emit a typed retain disposition for that exact signal
- **AND** an otherwise identical signal without current ownership evidence SHALL remain `unresolved`

#### Scenario: Similar surfaces form a contraction candidate
- **WHEN** two or more surfaces form one candidate with the same observable-contract identity
- **THEN** current existence or source ownership alone SHALL NOT retain the candidate signals
- **AND** the candidate SHALL require exact different-commitment retain evidence or verified contraction proof

### Requirement: Reduction proof is non-circular and externally bounded
Only current observable equivalence or public-facade delegation evidence independent from candidate generation SHALL authorize `contract`. Same-origin fingerprints, code size, lexical similarity, or internal happy-path equality SHALL NOT authorize contraction.

#### Scenario: Candidate and safety proof come from the same blueprint row
- **WHEN** no independent behavior contract, execution evidence, or facade-delegation proof supports a candidate
- **THEN** the candidate SHALL remain `unresolved` with a risky-keep boundary

#### Scenario: External consumer still uses an internal-looking facade
- **WHEN** internal tests pass after removing a facade but a current external consumer contract fails
- **THEN** the reduction SHALL be blocked

### Requirement: Reduction proof is independently verified and execution-unique
Self-reduction SHALL accept proof authority only from the repository's one current canonical validation-owner store. A candidate proof SHALL be a child-bound aggregate over independently executed, exact-current owner receipts: at minimum one test execution bound to the candidate's own observable-contract coverage and candidate-level parity evidence covering caller/consumer, state, side effect, and error obligations. The producer SHALL execute each child under bounded process-tree supervision before saving a passing receipt; a caller-authored leaf receipt, alternate temporary store, relabeled suite receipt, timeout, cancellation, failed command, skipped child, blocked child, or cleanup-unconfirmed process tree SHALL NOT authorize contraction. The consumer SHALL reload the aggregate and every child from the canonical store, rebuild their current owner contexts, run the native verifier, and compare exact receipt identities and obligations. Different candidates SHALL NOT reuse one aggregate, proof artifact, result fingerprint, child execution, or execution-owner identity through different wrappers.

#### Scenario: Typed proof wrapper contains caller-authored current booleans
- **WHEN** a structurally valid proof carries a caller-authored passing verification but the canonical receipt or current context does not verify
- **THEN** the candidate SHALL remain `unresolved`

#### Scenario: Two candidates rewrap one proof execution
- **WHEN** two candidate proof records use different receipt ids but share one proof artifact, result fingerprint, or execution identity
- **THEN** both candidates SHALL be blocked from contraction readiness until independently owned evidence exists

#### Scenario: Caller writes a passing leaf receipt without running its command
- **WHEN** a caller stores a passing validation-owner leaf whose payload merely asserts test and four-way parity success
- **THEN** self-reduction SHALL reject it because no supervised child executions and child-bound aggregate exist

#### Scenario: A current test is unrelated to the candidate
- **WHEN** a passing test receipt names a current global test that is absent from the candidate's observable-contract coverage
- **THEN** the test SHALL NOT satisfy the candidate proof

#### Scenario: One parity child is missing
- **WHEN** the aggregate omits caller/consumer, state, side-effect, or error parity evidence required for the candidate
- **THEN** contraction readiness SHALL remain blocked

### Requirement: Cleanup evidence is refreshed before and after contraction
Any implemented contraction SHALL invalidate affected model, inventory, topology, resource, binding, consumer-parity, and test evidence and SHALL require current before-and-after identities before release. A read-only review SHALL also recheck its governed source and proof-owner identities immediately before publication so a concurrent write cannot turn an earlier bundle into a current result.

#### Scenario: Source changes after a green cleanup review
- **WHEN** a candidate is implemented after the review fingerprint was created
- **THEN** the pre-change review SHALL become stale
- **AND** affected post-change evidence SHALL be required before acceptance

#### Scenario: Source changes during a cleanup review
- **WHEN** another writer changes a governed source or proof input after the review begins but before its result is published
- **THEN** the final currentness recheck SHALL block publication of a green review

### Requirement: Candidate proof executes exact tests and behavior parity
A contraction proof SHALL execute every exact candidate-related test node and every candidate-bound behavior replay under the explicit proof producer. Test evidence SHALL report the requested and collected node identities, require every collected node to pass, require zero skipped, xfailed, xpassed, deselected, missing, or unrelated nodes, and prove execution of the exact nontrivial oracle members bound by current coverage. Process exit zero, an empty collection, `assert True`, and caller-authored pass counts SHALL NOT establish test authority. Candidate parity SHALL execute every affected implementation member and public entrypoint reached by the candidate and SHALL compare its current input, output, state, effect, and error case oracles; checking only metadata labels or dimension names SHALL NOT establish parity.

#### Scenario: Exit zero hides an xfailed candidate test
- **WHEN** the exact candidate command exits zero but one requested node is xfailed, skipped, deselected, missing, or backed only by a trivial assertion
- **THEN** the test child SHALL be rejected
- **AND** the candidate SHALL remain unresolved

#### Scenario: Parity script checks dimension names only
- **WHEN** a parity child confirms that five dimension labels are present without executing every candidate member and its bound oracle lines
- **THEN** the parity child SHALL be rejected as metadata-only evidence

### Requirement: Facade and caller authority is derived and unambiguous
Public-facade proof facts SHALL be derived from the current self blueprint, current BehaviorCommitmentLedger source surface and commitment, and exact behavior/code binding. A proof caller SHALL NOT submit delegation, intent, commitment, primary-path, owner-contract, or independent-authority facts. Caller discovery SHALL resolve calls to canonical implementation surface ids. A qualified or short symbol MAY be normalized only when it resolves to exactly one current surface; a call matching several surfaces SHALL produce an explicit candidate caller-resolution gap.

#### Scenario: Caller fills every facade field with passing values
- **WHEN** a caller supplies internally consistent facade delegation fields that are absent from or contradict the current ledger or code binding
- **THEN** no public-facade proof SHALL be produced

#### Scenario: One short call matches two helpers
- **WHEN** a raw short call can name two current surfaces
- **THEN** neither surface SHALL silently inherit that caller
- **AND** the affected candidate SHALL expose an ambiguity gap until a canonical surface-id edge exists

### Requirement: Candidate actions have one primary owner per code member
When several current candidates include the same code member, self-reduction SHALL derive at most one independently selected primary candidate action for that member. If no current authority selects one primary, every conflicting action SHALL remain blocked and the member SHALL remain unresolved.

#### Scenario: One helper is both a remove and merge target
- **WHEN** two proof-bearing candidates assign different actions to the same helper without one current primary-candidate binding
- **THEN** neither action SHALL be contraction-ready
- **AND** the conflict SHALL be named in the cleanup review

### Requirement: Canonical proof storage is repository-confined and non-reparse
The self-reduction consumer and producer SHALL derive the sole canonical validation-owner store from the repository root and SHALL expose no caller-selectable receipt-root input. The store, receipt, proof artifact, and every existing path component SHALL remain inside the resolved repository and SHALL NOT be a symlink, junction, mount substitution, or other reparse point.

#### Scenario: Canonical store name is a junction to another directory
- **WHEN** the expected store path or a proof artifact traverses a junction, symlink, reparse point, absolute path, or parent escape
- **THEN** proof publication and consumption SHALL fail visibly

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

### Requirement: Intentional behavior retirement is evidence-bound
Architecture Reduction SHALL support a `retire_behavior` disposition when a current product behavior is no longer necessary, without requiring observable-behavior equivalence. The disposition MUST identify the retired behavior commitment, current product-goal rationale, public and internal consumers, affected model/code/test/interface surfaces, replacement or responsibility-transfer owner when one exists, and the exact validation routes required before removal.

#### Scenario: Historical behavior is no longer necessary
- **WHEN** a reduction candidate owns behavior that is no longer required by the current product goal
- **THEN** Architecture Reduction may authorize `retire_behavior` only after every active commitment, consumer, model relation, code owner, test obligation, public entrypoint, and evidence claim receives an explicit retirement, replacement, migration, or retained-history disposition
- **AND** behavior-equivalence proof is not required for the intentionally removed behavior

#### Scenario: Retirement proof is incomplete
- **WHEN** any active commitment, current consumer, negative case, model relation, code binding, test binding, public surface, or release claim still depends on the candidate
- **THEN** Architecture Reduction MUST block retirement and identify the unresolved owner

#### Scenario: Old name is called after retirement
- **WHEN** a caller uses a retired API, CLI, route, prompt, model owner, or data field
- **THEN** FlowGuard MUST fail visibly rather than selecting an alias, forwarder, compatibility reader, fallback, or replacement by guess

### Requirement: Protection migration precedes route deletion
Architecture Reduction SHALL distinguish a redundant route from the protection it historically carried and SHALL require each still-necessary protection to be accepted by exactly one current owner before the old route is removed.

#### Scenario: Duplicate route carries a useful negative case
- **WHEN** a historical route is redundant but one of its negative cases remains necessary
- **THEN** the negative case and its oracle MUST first bind to the canonical owner that now enforces the protection
- **AND** the retired route MUST disappear from the current model, code, test, route, API, CLI, documentation, and regression inventories

#### Scenario: Protection has no current owner
- **WHEN** a historical protection cannot be assigned to one current owner with executable evidence
- **THEN** the route remains unresolved and MUST NOT be deleted

### Requirement: Retained routes are reduced at exact internal-step boundaries
Architecture Reduction SHALL treat internal branches, repeated scans, reflection passes, helper chains, evidence projections, serialization/fingerprint work, and large payload materialization as reduction candidates even when their enclosing route remains current. Every candidate SHALL identify its current obligation, caller and consumer set, negative cases, side effects, evidence owner, replacement or delegation owner, trigger, and operation/payload/time cost evidence. The action SHALL be one of retain, merge, delegate, remove, explicit-on-demand, or unresolved.

#### Scenario: Retained route repeats another owner's work
- **WHEN** an internal step recomputes, rescans, reclassifies, or republishes a result already produced by one exact-current owner with equivalent current evidence
- **THEN** the step SHALL be removed, merged, or delegated to that owner
- **AND** affected tests SHALL prove the retained route still satisfies its observable contract without a second authority or fallback

#### Scenario: High-cost step is useful only on explicit demand
- **WHEN** a deep search, exhaustive expansion, large projection, publication check, or reusable-template analysis has no consumer on the ordinary path but remains useful for an explicit user request or named depth profile
- **THEN** the step SHALL move behind that explicit trigger rather than execute or materialize by default
- **AND** operation-count or payload-size evidence SHALL prove the lightweight path does not perform the deep work

#### Scenario: Expensive step is the unique current protection
- **WHEN** a costly step is the sole current safety classifier, source verifier, failure oracle, side-effect guard, or terminal evidence producer for an active obligation
- **THEN** cost alone MUST NOT authorize removal
- **AND** the candidate SHALL be retained, safely partitioned, or cached only over an exact immutable identity until a proved replacement owner exists

#### Scenario: Internal step has no current necessity
- **WHEN** an internal branch or helper has no active obligation, caller, consumer, negative case, side effect, evidence claim, or explicit on-demand trigger
- **THEN** Architecture Reduction MAY authorize its direct removal with complete affected-surface accounting
- **AND** the enclosing route MAY remain current without preserving the obsolete step

#### Scenario: Large module has no model-derived split target
- **WHEN** the independent inventory reports an oversized module but no named FlowGuard FunctionBlock partition supplies target child modules, single owners, facade boundaries, and parity boundaries
- **THEN** the oversized boundary SHALL remain a visible StructureMesh trigger with current cost evidence
- **AND** size alone SHALL NOT manufacture an Architecture Reduction candidate, deletion proof batch, or claim that a mechanical file split is more efficient

### Requirement: Canonical relation provenance informs reduction candidates
Architecture Reduction SHALL consume bounded canonical relation handoffs as candidate provenance for duplicate-boundary, adapter-only, same-intent, shared-owner, and false-friend findings. A relation SHALL retain exact endpoint, source-authority, behavior-plane, currentness, and affected-member identities, but SHALL NOT prove contraction readiness by itself.

#### Scenario: Canonical relation feeds a reduction candidate
- **WHEN** a current canonical relation identifies duplicate ownership, adapter-only difference, or same-intent surfaces
- **THEN** the reduction review records the relation id on the concrete candidate and preserves the observable contract, ownership, consumer, and evidence requirements

#### Scenario: Relation is not proof by itself
- **WHEN** a candidate cites only a canonical relation and lacks authorized retirement evidence, safe equivalence, public-facade delegation, conformance, or validation-boundary evidence
- **THEN** Architecture Reduction MUST NOT report the candidate as ready

### Requirement: Canonical relation provenance materializes into concrete reduction candidates
Every in-scope canonical relation used for Architecture Reduction SHALL bind to one or more concrete reduction candidates, target code nodes, and target actions, or to an explicit keep, false-friend, manual-review, or scoped disposition.

#### Scenario: Relation produces concrete candidates
- **WHEN** a duplicate-boundary, same-intent, adapter-only, shared-owner, or overlapping-ownership relation is handed to Architecture Reduction
- **THEN** every in-scope endpoint appears on a concrete candidate or explicit disposition
- **AND** each candidate identifies its target node, primary owner, and intended reduction action

#### Scenario: Relation remains plan-level metadata
- **WHEN** a reduction plan cites a canonical relation id but no concrete candidate or disposition consumes an in-scope endpoint
- **THEN** Architecture Reduction reports unmaterialized relation provenance
- **AND** the id alone MUST NOT support contraction readiness

### Requirement: Architecture Reduction consumes but does not own model path quality
Architecture Reduction SHALL consume a current model-path-quality result as provenance only when exact blueprint bindings identify corresponding implementation, helper, module, adapter, public-entrypoint, or validation-layer candidates. It SHALL apply its own consumer, facade, side-effect, equivalence, retirement, and evidence requirements and SHALL NOT run a second model optimizer.

#### Scenario: Model-only contraction has no code effect
- **WHEN** an equivalent model representation contracts without changing a mapped implementation surface
- **THEN** ModelMaturation owns the revised model and Architecture Reduction makes no code-contraction claim

#### Scenario: Model result exposes duplicate code
- **WHEN** exact bindings map a proved model contraction to duplicate implementation surfaces
- **THEN** Architecture Reduction materializes concrete candidates and validates them under its own contract
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

#### Scenario: Test and model validation evidence use distinct current owners
- **WHEN** an implementation-necessity witness cites ordinary test nodes together with the model-regression result for its exact model element
- **THEN** the ordinary tests SHALL resolve in the current test inventory while the model-regression identity and fingerprint SHALL resolve through the exact current path-quality/model owner
- **AND** an unknown identity, a foreign model-regression id, or a model-regression label without current path-quality evidence SHALL block the witness
- **AND** model-validation evidence SHALL NOT be looked up as an ordinary test node or cause every implementation surface to appear untested

#### Scenario: Model validation proves current necessity without claiming ordinary test completion
- **WHEN** an implementation surface has current intent, semantics, oracles, an exact caller or external commitment, and the exact current model-regression/path-quality evidence but no ordinary test node bound to that surface
- **THEN** that model-validation evidence MAY support the surface's current-necessity witness so the live implementation is not treated as safely removable
- **AND** the witness SHALL keep its ordinary test-node set empty instead of manufacturing a test binding
- **AND** the missing ordinary execution evidence SHALL remain visible to model-test alignment and SHALL NOT support contraction parity, test-completion, or release-readiness claims

#### Scenario: Unreferenced-helper review uses finite member batches
- **WHEN** one module contains more unreferenced private helpers than the declared cleanup-candidate member limit
- **THEN** the candidate inventory SHALL partition those exact helpers into deterministic non-overlapping batches within the limit
- **AND** each helper SHALL appear exactly once in that signal family while the module path and batch ordinal remain explicit
- **AND** no batch SHALL expand to unrelated module members or claim that absence of a static caller proves safe removal

#### Scenario: Similar-looking routes require one exact bounded relation
- **WHEN** wrapper, facade, helper, validation, adapter, serialization, builder, branch, or route surfaces are considered for comparison
- **THEN** they SHALL share both the same current call signature and the same current structure fingerprint before entering one relation group
- **AND** a relation group larger than the declared candidate member limit SHALL be partitioned into deterministic non-overlapping finite batches
- **AND** one bounded batch MAY authorize only its own members; later convergence requires a fresh current audit rather than an unbounded or cross-batch inference

#### Scenario: Receiver-qualified call cannot manufacture an unreferenced helper
- **WHEN** a call such as `self._helper` or `object._helper` has no exact current symbol match but its final name matches one or more current local helper surfaces
- **THEN** the caller index SHALL record an explicit resolution gap for those possible targets instead of silently discarding the call or binding an arbitrary target
- **AND** a helper with that unresolved receiver-qualified call SHALL NOT enter the unreferenced-helper candidate family
- **AND** only an exact canonical surface edge MAY serve as a current consumer or necessity witness

### Requirement: Historical-looking names are signals rather than singleton candidates
A maintenance-like name SHALL contribute a discovery signal only. The review SHALL materialize a historical-path reduction candidate only when at least two current surfaces have an exact shared call or structure relation; it SHALL NOT create a singleton candidate solely because a symbol contains `legacy`, `compat`, `fallback`, `alias`, or a similar word.

#### Scenario: One isolated helper has a historical-looking name
- **WHEN** one current surface has a maintenance-like name but no exact related current surface
- **THEN** the surface SHALL retain its typed discovery classification without producing a reduction candidate
- **AND** candidate and proof counts SHALL remain unchanged by the isolated name

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
