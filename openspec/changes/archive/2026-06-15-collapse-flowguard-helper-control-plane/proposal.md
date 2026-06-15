## Why

FlowGuard now has the stronger ContractExhaustionMesh path, but the AI-facing
control plane still exposes older helper routes as if they were independent
public entry points. That keeps the route map noisy and allows future agents to
choose old same-class, simulator, model-angle, maintenance, or closure paths
instead of the current owner routes.

This change collapses those helper surfaces into the existing FlowGuard routes
that already own them. The goal is a smaller, clearer, latest-schema-first
control plane with no fallback case-generation or compatibility prompt path.

## What Changes

- Add first-class route-profile role metadata so FlowGuard can distinguish
  public owner routes, delegated simulator modes, internal feeders, data
  helpers, and archive-only cleanup surfaces.
- **BREAKING**: remove internal helper routes from the AI-facing
  `FLOWGUARD_ROUTE_API` and `ROUTE_STARTER_API` public-owner surface.
- Fold `development_process_simulator` into `development_process_flow` as an
  internal simulator helper and mode selector.
- Fold `model_angle_deliberation` and `model_similarity_consolidation` into
  `existing_model_preflight` as consumed rows or feeder evidence, not generic
  first-stop routes.
- Treat `maintenance_scan_router` as DevelopmentProcessFlow post-change owner
  scan input instead of a separate final confidence route.
- Treat `maintenance_obligation_memory` and evidence-field helpers as data
  shapes consumed by owner routes.
- Treat `flowguard_closure_contract` as guard-family child closure support
  consumed by RiskEvidenceLedger and DevelopmentProcessFlow, not as the final
  confidence owner.
- Keep StateClosure, ScenarioMatrix, ObligationFamily, ArtifactPayload,
  TransitionCoverage, and ModelMesh closure as feeder/declaration owners while
  preserving ContractExhaustionMesh as the only canonical finite bad-case
  generator.
- Clean route maps, installed skill prompts, public docs, templates, tests, and
  topology notes so old same-class, analogous-bug, helper-route, and fallback
  wording cannot be mistaken for current canonical coverage.
- Preserve no long-lived compatibility branch: old prompt routes are deleted,
  absorbed, converted to internal feeder status, or explicitly sent through
  ArchitectureReduction/StructureMesh facade review.

## Capabilities

### New Capabilities
- `flowguard-helper-control-plane`: Defines public-owner route roles,
  delegated modes, internal feeders, data helpers, archive-only surfaces, and
  no-fallback cleanup expectations for AI-facing FlowGuard route discovery.

### Modified Capabilities
- `flowguard-global-routing`: Public route selection must expose owner routes
  only and route helper evidence through those owners.
- `flowguard-api-registry`: API discovery must separate public owner starters
  from advanced/internal helper inventories.
- `development-process-flow`: DevelopmentProcessFlow must be the sole public
  process front door and consume simulator, scan, freshness, and final process
  claim inputs.
- `existing-model-preflight`: ExistingModelPreflight must consume model-angle
  and similarity evidence before route selection instead of listing those as
  standalone hot-path routes.
- `architecture-reduction`: ArchitectureReduction must classify old helper
  prompt surfaces, route aliases, templates, and compatibility-like entries
  before deletion, absorption, or facade retention.
- `risk-evidence-ledger`: RiskEvidenceLedger must remain the final broad
  confidence owner and must not let closure helpers or single-point matrices
  stand in for whole-chain proof.
- `flowguard-codex-skill-satellites`: Installed skill shells must reflect the
  public-owner/delegated/internal split and remove stale helper-first wording.
- `contract-exhaustion-mesh`: ContractExhaustionMesh remains the only
  canonical bad-case generation route and receives feeder projections from
  older case sources.

## Impact

- Public API discovery: `FLOWGUARD_ROUTE_API`, `ROUTE_STARTER_API`,
  `default_flowguard_route_profiles()`, and route-surface tests.
- FlowGuard self-maintenance metadata: `RouteProfile`, self-maintenance review
  checks, AI maintenance profiles, and route graph docs.
- Codex-facing prompts and installed skills under `.agents/skills/` and the
  synced local Codex skills installation.
- OpenSpec specs and docs for global routing, API surface, DevelopmentProcessFlow,
  ExistingModelPreflight, ArchitectureReduction, RiskEvidenceLedger, and
  ContractExhaustionMesh.
- Tests covering API surface shape, skill docs, trigger routing, public
  templates, ContractExhaustionMesh handoffs, RiskEvidenceLedger confidence,
  and DevelopmentProcessFlow simulator behavior.
- Release artifacts: package version, changelog, git tag, GitHub release, and
  shadow workspace/install synchronization.
