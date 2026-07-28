## Context

FlowGuard already has the right technical pieces:

- ContractExhaustionMesh is the canonical finite bad-case generator.
- DevelopmentProcessFlow is the development-process simulator front door.
- ExistingModelPreflight can consume model-angle and model-similarity evidence.
- ArchitectureReduction can classify old aliases, wrappers, prompt paths, and
  compatibility-like surfaces before deletion or facade retention.
- RiskEvidenceLedger owns final broad confidence claims.

The remaining problem is the public control plane. `FLOWGUARD_ROUTE_API`,
`ROUTE_STARTER_API`, route profiles, reusable AGENTS snippets, model-first
guidance, templates, and tests still expose some helper layers as if they were
independent public routes. That creates an ambiguous route graph where an AI
agent can choose an old helper-first route even though the stronger existing
owner route should consume that helper internally.

The project also has a latest-schema-first rule: old artifacts can be upgraded
at the boundary, but normal route logic must not keep long-lived compatibility
branches, aliases, wrappers, or fallback prompt paths unless current evidence
proves a real public contract.

## Goals / Non-Goals

**Goals:**

- Make the AI-facing route graph smaller and deterministic.
- Add explicit route role metadata so public owner routes and internal helpers
  are machine-distinguishable.
- Keep existing specialist helpers where they add real decomposition value, but
  prevent them from acting as competing generic first stops.
- Preserve ContractExhaustionMesh as the only canonical bad-case generation
  surface.
- Make composite handoff acceptance visible whenever a generated case must cross
  more than one route.
- Remove or rewrite stale prompt wording, templates, and docs that imply old
  hand-written same-class, analogous-bug, helper-route, or closure paths count
  as complete current coverage.
- Sync the repository, shadow workspace, installed skills, version metadata, and
  GitHub release after validation.

**Non-Goals:**

- Do not delete domain helpers that still own declaration, projection, or review
  logic.
- Do not replace Model-Test Alignment, TestMesh, ModelMesh, StructureMesh,
  UIFlowStructure, FieldLifecycleMesh, ArchitectureReduction, or RiskEvidenceLedger.
- Do not promise infinite bug discovery. ContractExhaustionMesh exhausts
  declared finite boundaries and finite equivalence classes only.
- Do not keep a fallback route from the new public control plane back to old
  helper-first paths.

## Decisions

### Decision: Add explicit route-role metadata

Add first-class route-role fields to `RouteProfile`:

- `route_role`: `public_owner`, `delegated_mode`, `internal_feeder`,
  `data_helper`, or `archive_only`;
- `entry_policy`: `direct`, `via_owner`, or `internal_only`;
- `canonical_owner_route`;
- `absorbed_by_route`;
- `cleanup_disposition`: `keep`, `absorb`, `delete`, or `facade_review`.

Rationale: role and entry behavior are control-plane semantics, not incidental
display metadata. Keeping them as typed fields lets tests and route docs enforce
the same public/internal split.

Alternative considered: store roles only inside `metadata`. Rejected because
the public API surface and prompt generation need stable direct access.

### Decision: Keep public API discovery owner-only

`FLOWGUARD_ROUTE_API` and `ROUTE_STARTER_API` should become the AI-facing
public-owner surface. Full helper groups may remain reachable through
`ROUTE_ADVANCED_API`, `MODELING_HELPER_API`, `REPORTING_HELPER_API`, and route
owner starter slices, but internal feeders should not appear as default route
starters.

Rationale: AI agents need a short route choice table. Advanced internal helpers
remain importable for code and tests, but they stop competing for route
selection.

Alternative considered: keep every route group in `FLOWGUARD_ROUTE_API` and add
warnings. Rejected because stale warnings are not enough to prevent route drift.

### Decision: Fold the process simulator into DevelopmentProcessFlow

Keep `review_development_process_simulator()` and its report types, but expose
them through the `development_process_flow` starter. Do not keep
`development_process_simulator` as a separate public route id.

Rationale: current specs already define DevelopmentProcessFlow as the process
front door. Two public route ids for the same front door recreate the ambiguity.

### Decision: Fold angle and similarity into ExistingModelPreflight

Keep model-angle and similarity helpers as structured evidence producers. Full
ExistingModelPreflight consumes current angle rows and similarity relations
before deciding reuse, extension, child model, family variant, shared kernel,
ArchitectureReduction, or separate boundary.

Rationale: angle and similarity answer "which existing boundary owns this?"
They are preflight evidence, not separate implementation routes.

### Decision: Keep ContractExhaustionMesh as the only canonical bad-case owner

StateClosure, ScenarioMatrix, ObligationFamily, ModelMissReview,
ArtifactPayload, TransitionCoverage, and ModelMesh closure may still declare or
project seeds. Canonical case ids and oracle handoffs must be
`ContractMutationCase` rows from ContractExhaustionMesh.

Rationale: one canonical case language prevents old same-class paths from
becoming silent fallback coverage.

### Decision: Put final broad confidence through RiskEvidenceLedger

RiskEvidenceLedger remains the final broad confidence owner. Closure contract,
maintenance obligations, post-change scans, generated case matrices, and
sibling route evidence are support rows. A closure helper pass or a single-route
matrix pass cannot become whole-chain confidence without ledger and composite
handoff acceptance closure.

Rationale: final claims need one proof-accounting owner.

### Decision: Use ArchitectureReduction for old surface disposition

Old helper prompts, aliases, route ids, template commands, wrappers, and
compatibility-like entries must be classified before they are kept. Valid
dispositions are delete, absorb into owner route, convert to internal helper,
or preserve as an explicitly proven facade.

Rationale: this follows existing latest-schema-first and default-replacement
rules without keeping fallback branches.

## Risks / Trade-offs

- Public route list shrinkage may break tests that intentionally asserted the
  old inventory. Mitigation: update tests to assert public-owner routes plus
  advanced/internal helper availability separately.
- Existing users may know helper template names. Mitigation: keep only proven
  public facades; otherwise remove helper-first prompts and document the owner
  route that now consumes the helper.
- Route-role fields touch API exports and self-maintenance templates. Mitigation:
  add focused tests for serialization, API surface, route profile review, and
  skill docs before broader pytest.
- Release work may encounter unrelated existing git changes. Mitigation: treat
  the current ContractExhaustionMesh working tree as part of this requested
  release scope, review status before staging, and do not revert unrelated user
  edits.

## Migration Plan

1. Add OpenSpec specs for the helper control plane and owner/internal route
   requirements.
2. Add route-role metadata to `RouteProfile` and update default route profiles.
3. Split public owner route groups from advanced/internal helper groups in the
   API registry.
4. Update skill prompts, docs, templates, and AGENTS snippets to use owner
   routes only in the hot path.
5. Update tests that currently expect internal helpers in public route lists.
6. Rerun ContractExhaustionMesh, API surface, skill docs, trigger routing,
   DevelopmentProcessFlow, ExistingModelPreflight, RiskEvidenceLedger, and full
   test validation.
7. Run FlowGuard self-maintenance and project audit, then sync the shadow
   workspace and installed skills.
8. Bump package version, update changelog and README version row, commit, tag,
   push, and create the GitHub release.

Rollback strategy is to revert this OpenSpec change and implementation commit
as one unfinished change. Do not leave both helper-first and owner-first public
route maps active as compatibility alternatives.

## Open Questions

- None for implementation. Any public facade that is discovered during cleanup
  will be classified by ArchitectureReduction or StructureMesh evidence rather
  than kept by default.
