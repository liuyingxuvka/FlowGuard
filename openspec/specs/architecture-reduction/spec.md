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
- **AND** the linked reduction candidate has safe equivalence or public-facade
  proof status
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
- **AND** the current route-first API or `SimilarityHandoff` covers the same
  maintenance obligation
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

### Requirement: Similarity relation provenance
Architecture Reduction SHALL be able to consume model-similarity relations as
candidate provenance for duplicate-boundary, adapter-only, shared-kernel, and
duplicate-validation contraction candidates.

#### Scenario: Similarity relation feeds reduction candidate
- **WHEN** an Architecture Reduction candidate cites a model-similarity
  relation that identifies duplicate ownership or adapter-only difference
- **THEN** the review includes the relation id as candidate provenance while
  still requiring observable architecture contract coverage

#### Scenario: Similarity code obligation feeds reduction candidate
- **WHEN** an Architecture Reduction candidate is motivated by a
  duplicate-boundary or adapter-only model-similarity obligation
- **THEN** the candidate records the code obligation id as provenance while
  Architecture Reduction still owns the contraction readiness decision

#### Scenario: Similarity is not proof by itself
- **WHEN** a reduction candidate only cites a similarity relation and lacks
  safe equivalence, public facade, conformance, or validation-boundary evidence
- **THEN** the review does not report the candidate as ready

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

#### Scenario: Compatibility discovery duplicates the current manifest authority
- **WHEN** all supported runners are explicitly registered and undeclared runners fail visibly
- **THEN** the obsolete compatibility discovery path MAY be removed with manifest and runner parity evidence

### Requirement: Architecture Reduction accounts the complete same-intent candidate inventory
FlowGuard SHALL require an Architecture Reduction plan driven by existing-model or model-similarity evidence to declare the complete expected set of duplicate, same-workflow, adapter, alias, wrapper, helper, fallback, and facade candidates for each in-scope stable business intent.

#### Scenario: Expected reduction candidate is omitted
- **WHEN** Existing Model Preflight or Model Similarity identifies an in-scope same-intent surface but no reduction candidate or explicit keep/scoped disposition represents it
- **THEN** Architecture Reduction SHALL report the expected candidate as missing
- **AND** it SHALL NOT treat the caller-selected candidate subset as a complete contraction review

#### Scenario: Complete candidate inventory has dispositions
- **WHEN** every expected same-intent candidate is materialized and classified as merge, collapse, remove, delegate, keep-facade, manual-review, or scoped with reason
- **THEN** Architecture Reduction MAY report candidate-inventory completeness
- **AND** the report SHALL expose the expected, materialized, and scoped candidate ids

#### Scenario: Candidate inventory evidence is stale
- **WHEN** the source surface inventory, similarity relations, or affected business-intent boundary changes after candidate classification
- **THEN** Architecture Reduction SHALL mark the candidate inventory stale
- **AND** no broad contraction-readiness claim SHALL rely on that inventory

### Requirement: Similarity provenance materializes into concrete reduction candidates
FlowGuard SHALL require every in-scope similarity relation id and similarity code-obligation id used for Architecture Reduction to bind to one or more concrete reduction candidates, target code nodes, and target actions.

#### Scenario: Similarity relation produces concrete candidates
- **WHEN** a duplicate-boundary, same-workflow, adapter-only, or overlapping-ownership relation is handed to Architecture Reduction
- **THEN** the relation and any required similarity code-obligation ids SHALL be recorded on the concrete candidates derived from that relation
- **AND** each candidate SHALL identify its target node and intended reduction action

#### Scenario: Similarity ids remain plan-level metadata
- **WHEN** a reduction plan cites similarity relation or code-obligation ids only as plan metadata and no concrete candidate consumes them
- **THEN** Architecture Reduction SHALL report unmaterialized similarity provenance
- **AND** the ids alone SHALL NOT support contraction readiness

#### Scenario: Relation side has no candidate or rationale
- **WHEN** one in-scope side of a similarity relation has neither a materialized candidate nor an explicit keep/scoped rationale
- **THEN** Architecture Reduction SHALL report incomplete relation coverage
- **AND** the relation SHALL remain an open reduction obligation

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
Before publishing the FlowGuard patch release, FlowGuard SHALL use the current completed self blueprint and independently discovered implementation inventory to review in-scope repeated routes, branches, adapters, wrappers, facades, helpers, and validation paths. The review SHALL declare the observable contract, account every discovered candidate with a typed disposition, and permit edits only for candidates proven safe by current equivalence or delegating-public-facade evidence. Public-entrypoint contraction SHALL require StructureMesh parity and affected revalidation. Uncertain, stale, property-only, or behavior-changing candidates SHALL remain visible rather than being silently removed.

#### Scenario: Duplicate path is safely contracted before release
- **WHEN** the current self blueprint identifies repeated implementation paths for the same modeled obligation
- **AND** current evidence proves observable equivalence or a facade that only delegates to the selected primary owner
- **THEN** ArchitectureReduction may hand the contraction to StructureMesh and DevelopmentProcessFlow
- **AND** the release SHALL revalidate every affected model, public entrypoint, state, side effect, and test boundary before completion

#### Scenario: Apparent duplication lacks behavior-equivalence evidence
- **WHEN** a route, branch, adapter, wrapper, helper, facade, or validation path appears redundant
- **BUT** current evidence proves only selected properties or leaves observable behavior uncertain
- **THEN** FlowGuard SHALL retain the surface and record its typed maintenance disposition
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
Only equivalence-proven replacement or facade-proven delegation SHALL be eligible for contraction. After an authorized contraction, the same model lineage, implementation inventory, bindings, contracts, tests, and affected evidence SHALL be updated together; uncertain candidates SHALL remain typed unresolved obligations.

#### Scenario: Removal would orphan a model or test binding
- **WHEN** a proposed removed surface is still the sole implementation, consumer, CodeContract target, or test target for an active obligation
- **THEN** reduction is blocked until a valid replacement or retirement disposition is modeled and evidenced
- **AND** the surface is not deleted as dead code

#### Scenario: Evidence-ready contraction is applied
- **WHEN** an authorized contraction preserves the observable contract and every affected owner has a current target disposition
- **THEN** the resulting candidate revision updates the implementation inventory and all affected bindings
- **AND** affected model, test, topology, structure, installation, and process evidence is revalidated before closure

#### Scenario: A candidate remains uncertain
- **WHEN** equivalence, facade delegation, external use, or side-effect ownership cannot be established
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
