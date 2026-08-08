## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: FlowGuard release uses its completed self blueprint for safe contraction
Before publishing a FlowGuard release, FlowGuard SHALL use the current completed self blueprint and independently discovered implementation inventory to review in-scope repeated routes, branches, adapters, wrappers, facades, helpers, validation paths, and historical product behaviors. The review SHALL classify every discovered surface by current software-DNA necessity and account it with a typed retain, ordinary behavior-preserving contraction, delegating-facade, authorized `retire_behavior`, or unresolved disposition. Public-entrypoint contraction SHALL require StructureMesh parity; intentional behavior retirement SHALL require the complete retirement responsibility proof; both SHALL require affected revalidation. Uncertain, stale, property-only, or incompletely dispositioned candidates SHALL remain visible rather than being silently removed.

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

## REMOVED Requirements

### Requirement: Similarity relation provenance
**Reason**: The standalone Model Similarity authority is retired; relation provenance must come from current blueprint, commitment, or topology owners.
**Migration**: Consume a canonical relation handoff as candidate provenance while Architecture Reduction retains all readiness decisions.

### Requirement: Similarity provenance materializes into concrete reduction candidates
**Reason**: The useful materialization protection remains, but no similarity-engine ids or code obligations remain authoritative.
**Migration**: Materialize each in-scope canonical relation endpoint into a concrete candidate or explicit current disposition.
