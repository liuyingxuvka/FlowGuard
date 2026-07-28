## Context

FlowGuard already has separate owners for UI content admission and interaction
structure, existing-model discovery, model similarity, external behavior
commitments, and primary runtime path authority. Those owners currently exchange
labels and evidence ids, but they do not consistently share one stable exact
business-intent identity or a complete inventory of the UI, API, CLI, alias,
adapter, wrapper, and helper surfaces that expose that intent.

This gap allows several locally valid but product-level inconsistent outcomes:

- the same exact user intent can be represented by multiple active behavior
  commitments;
- two different runtime paths can each be described as primary because their
  path ids differ;
- a new UI surface can invent a new action grammar or handler even though an
  equivalent current path already exists;
- similarity or handoff ids can be present without materialized candidate,
  surface, terminal, state-write, side-effect, and evidence records; and
- product-language work can accidentally introduce a new visibility taxonomy or
  a parallel design/runtime owner.

The change must strengthen the existing owners and their handoffs. It must not
create a Product Design Language route, a functional-path-reuse route, an intent
ledger, a delegate-commitment layer, a second evidence engine, or a second
runtime authority. UI content admission remains exactly
`user_visible`, `user_on_demand`, or `internal`.

The primary stakeholders are FlowGuard users reviewing product behavior,
maintainers extending the existing model and checker APIs, and AI agents that
must make a reuse decision before proposing or implementing a new surface.

## Goals / Non-Goals

**Goals:**

- Give every exact external business intent one stable identity owned by the
  existing Behavior Commitment Ledger.
- Require exactly one active commitment and one current green primary runtime
  path for that exact intent.
- Inventory the affected same-intent surface family before a new model or
  implementation boundary is admitted.
- Reuse an equivalent current-passing primary path across additional UI, API,
  CLI, alias, adapter, wrapper, and helper surfaces.
- Compare product-scope typography, component, navigation, interaction,
  feedback, recovery, and transition semantics inside the existing UI Flow
  Structure route.
- Preserve material evidence and typed differences across Preflight, Similarity,
  BCL, PPA, UI, and downstream evidence owners.
- Migrate path-sensitive BCL bindings to one singular `primary_path_id` without
  accepting ambiguous legacy lists for broad confidence.

**Non-Goals:**

- Creating a new route, skill, ledger, owner, CLI command, or evidence engine.
- Creating a commitment for each delegating surface or compatibility facade.
- Adding audience, role, persona, expert-mode, authorization, or other UI
  visibility classes.
- Defining brand colors, visual tokens, pixel-level component styling, or a new
  design-system owner.
- Automatically merging models or rewriting production code from similarity
  evidence alone.
- Treating every local UI interaction, such as expand or collapse, as an
  external business commitment.

## Decisions

### Decision 1: Preserve the existing owner graph

The change extends the existing owners in place:

- Existing Model Preflight inventories affected surfaces and selects the reuse,
  extension, or separate-boundary direction.
- Model Similarity compares materialized identity and behavior evidence and
  produces typed handoffs, but does not select runtime authority.
- Behavior Commitment Ledger owns the stable exact business-intent identity and
  the single active external commitment.
- Primary Path Authority owns the single selected runtime path and candidate
  dispositions.
- UI Flow Structure owns product-scope UI grammar comparison and binds
  business-bearing UI surfaces to the existing commitment and primary path.

Downstream RuntimePathEvidence, Model-Test Alignment, ObligationFamily,
ContractExhaustionMesh, TestMesh, and Architecture Reduction continue to own
their existing evidence, parity, case-generation, test, and contraction duties.

Alternative considered: create one Product Design Language or Validated Path
Reuse route. Rejected because it would duplicate discovery, commitment,
authority, UI, and evidence responsibilities and create another successful
workflow for agents to choose.

### Decision 2: BCL identity is the canonical exact-intent identity

An exact business intent is the same external promise after comparing its actor,
trigger and preconditions, expected result and terminal, failure boundary, and
material externally relevant state writes and side effects. BCL owns the stable
identity and exactly one active commitment for that promise. Different surface
forms do not create different commitments.

A proposed difference supports a separate intent only when the externally
observable semantics differ and the difference is typed with an owner,
validation boundary, rationale, and current evidence. Historical, removed, or
replaced rows may remain for disposition evidence, but they cannot act as a
second active success owner.

Alternative considered: create one delegate commitment per UI, API, CLI, or
compatibility surface. Rejected because a delegate commitment would turn an
entrypoint into a second behavior-accounting layer and would obscure whether all
surfaces expose the same promise.

### Decision 3: Preflight performs affected-family discovery and Similarity remains advisory

Before admitting a new boundary, Existing Model Preflight inventories the
affected same-intent family across declared UI, API, CLI, alias, adapter,
wrapper, and helper surfaces. The inventory records the known commitment,
business path, terminal, state-write, side-effect, owner, and evidence bindings,
plus explicit unknown or scoped surfaces.

Model Similarity compares the materialized rows. It may recommend reuse,
extension, a false-friend separation, or Architecture Reduction, but it cannot
prove inventory completeness or current runtime success by itself. Its handoff
must carry the concrete surface and evidence obligations rather than only an
opaque relation id.

Alternative considered: let each downstream caller provide a candidate list.
Rejected because caller-selected lists can omit the existing path or a competing
surface and still appear locally complete.

### Decision 4: PPA selects one current path per exact intent

PPA uniqueness is keyed by the stable exact `business_intent_id`, not by the
pair of intent and path id. Two different `business_path_id` values cannot both
be primary for the same exact intent.

When the affected-family inventory contains an equivalent path with current
passing RuntimePathEvidence and a complete proof artifact, that path is reused
as the primary authority. Selecting a different path requires an explicit
replacement or migration disposition for the former path, current parity or
transition evidence, and no interval in which both paths remain independent
successful authorities.

Additional surfaces are PPA candidates or facades. They may delegate to the
primary path, remain manual-only, be removed, migrate, or be scoped with a typed
reason; they do not receive a delegate commitment.

Alternative considered: allow a new path to be declared primary as long as the
old path is later removed. Rejected because it permits implementation to precede
the reuse decision and temporarily creates two successful authorities.

### Decision 5: Product language is a projection inside UI Flow Structure

For complete-product claims, UI Flow Structure compares the declared product
surfaces and reuses canonical typography, component, navigation, interaction,
feedback, recovery, and transition semantics for the same exact intent. A
bounded platform, accessibility, native-control, or safety difference is
recorded as a typed UI exception; it does not create a new runtime owner.

Business-bearing UI capabilities, action grammars, functional chains, and
transition projections bind to the existing BCL commitment id and singular PPA
primary path id. Pure UI behavior may remain owned only by UI Flow Structure
when it creates no external business promise.

Content admission continues to use exactly `user_visible`, `user_on_demand`,
and `internal`. Product-language comparison cannot add role or persona classes,
and internal content cannot become user-facing merely because an observed UI
already displays it.

Alternative considered: model product language as a new design-system schema.
Rejected because the requested consistency is semantic and behavioral, while
visual brand styling remains a separate downstream concern.

### Decision 6: Evidence is materialized through existing evidence owners

An id is a reference, not proof. Full-confidence handoffs preserve the affected
surface ids, commitment id, exact business-intent id, selected primary path id,
expected terminal, material state writes and side effects, current result
status, covered revision, and proof-artifact reference. Existing
RuntimePathEvidence and proof-artifact checks establish current path success;
Similarity, UI observation, or a free-form evidence id alone cannot.

Alternative considered: add a path-reuse evidence schema. Rejected because it
would duplicate RuntimePathEvidence, ProofArtifact, MTA, and TestMesh.

### Decision 7: Singular path binding is current-only

The canonical path-sensitive BCL runtime binding accepts and emits one
`primary_path_id`; it has no plural alias or compatibility state. The exact
historical BCL artifact upgrader owns the only retired `primary_path_ids`
input. It materializes zero or one value at the upgrade boundary and blocks
multiple values pending one evidence-bound current disposition.

Alternative considered: retain a list indefinitely and require callers to
interpret the first item. Rejected because ordering cannot establish authority
and preserves ambiguity by design.

## Risks / Trade-offs

- [Nearby but distinct intents are over-collapsed] → Compare external actor,
  trigger/preconditions, terminal, failure boundary, state writes, and side
  effects; preserve a typed false-friend or intentional-variant decision.
- [Affected-family inventory becomes expensive] → Require the affected intent
  family for ordinary changes and the full declared product surface only for
  complete-product or broad claims.
- [Old opaque ids appear to satisfy new gates] → Require materialized current
  RuntimePathEvidence and proof-artifact coverage before green PPA or runnable
  UI confidence.
- [UI consistency suppresses legitimate platform behavior] → Allow bounded,
  typed platform, native-control, accessibility, and safety exceptions while
  retaining the same commitment and primary path when business semantics match.
- [The singular field breaks existing callers] → Upgrade old files once
  through the exact historical artifact owner, update callers and fixtures to
  the singular field, and reject retired input in normal runtime.
- [Cross-owner findings are mistaken for a new workflow] → Keep one typed
  handoff chain and document each existing owner's claim boundary in skills,
  specs, and reports.

## Migration Plan

1. Extend the existing Preflight and Similarity records to carry stable
   commitment/intent/path identities and affected-family inventory evidence.
2. Strengthen BCL exact-intent uniqueness and introduce the singular
   `primary_path_id` output while reading deterministic one-item legacy input.
3. Strengthen PPA uniqueness, candidate accounting, selection, and current
   RuntimePathEvidence requirements.
4. Extend existing UI action grammar, functional-chain, and transition
   projections to consume the BCL/PPA identities and compare declared product
   surfaces without changing the three visibility classes.
5. Update existing downstream obligations, tests, templates, skills, and docs;
   verify focused known-bad cases before broad regression claims.
6. Keep legacy ambiguous inputs blocked. Rollback may disable the new broad
   claim while preserving recorded identities and evidence, but must not
   restore a second active commitment or primary path.

## Open Questions

No blocking architecture question remains. Implementation may choose the
smallest field placement in the existing dataclasses, but it must preserve the
owner graph, singular identity/path invariants, material evidence, and the
three-class visibility boundary defined here.
