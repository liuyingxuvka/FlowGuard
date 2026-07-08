## 1. Route Role Model

- [x] 1.1 Add first-class route-role, entry-policy, owner, absorption, and cleanup-disposition fields to `RouteProfile`.
- [x] 1.2 Update default route profiles so public owner routes, delegated modes, internal feeders, data helpers, and archive-only surfaces are classified explicitly.
- [x] 1.3 Update self-maintenance serialization/review tests for the new role fields and role mismatch findings.

## 2. Public API Surface

- [x] 2.1 Split public route discovery from advanced/internal helper inventories in `FLOWGUARD_ROUTE_API`, `ROUTE_STARTER_API`, and `ROUTE_ADVANCED_API`.
- [x] 2.2 Remove `development_process_simulator`, `model_angle_deliberation`, `model_similarity_consolidation`, `maintenance_obligation_memory`, `maintenance_scan_router`, `flowguard_closure_contract`, and `state_closure` from the direct public route starter surface unless classified as a proven public facade.
- [x] 2.3 Keep internal helper functions importable through advanced/helper inventories without making them public route starters.

## 3. Prompt, Skill, And Documentation Cleanup

- [x] 3.1 Update `.agents/skills` route shells so DevelopmentProcessFlow, ExistingModelPreflight, ContractExhaustionMesh, ArchitectureReduction, and RiskEvidenceLedger describe the new owner/internal split.
- [x] 3.2 Update `docs/agents_snippet.md`, `docs/modeling_protocol.md`, `docs/api_surface.md`, `docs/productized_helpers.md`, and topology docs to remove helper-first route wording.
- [x] 3.3 Rewrite old same-class, analogous-bug, simulator, maintenance-scan, and closure prompt text so it points to owner routes and ContractExhaustionMesh seeds instead of fallback coverage.
- [x] 3.4 Update template factory docs or CLI help for helper templates that are absorbed or internal-only.

## 4. Owner Route Integration

- [x] 4.1 Ensure DevelopmentProcessFlow consumes simulator, delegated mode, maintenance scan, and freshness evidence under the `development_process_flow` route id.
- [x] 4.2 Ensure ExistingModelPreflight consumes model-angle and similarity evidence and reports downstream public owner routes.
- [x] 4.3 Ensure ArchitectureReduction classifies old helper prompts, aliases, route ids, wrappers, and template commands as delete, absorb, internal-helper, or facade-review.
- [x] 4.4 Ensure RiskEvidenceLedger blocks broad confidence when closure helpers, internal helper evidence, or single-route matrices bypass owner-route consumption.
- [x] 4.5 Preserve ContractExhaustionMesh as the only canonical finite bad-case generator and keep composite handoff acceptance independent.

## 5. Tests And Model Evidence

- [x] 5.1 Update API surface tests for owner-only public route discovery and advanced/internal helper availability.
- [x] 5.2 Update skill-doc, public-template, and skill-trigger tests for the new public-owner route table.
- [x] 5.3 Update DevelopmentProcessFlow, ExistingModelPreflight, ContractExhaustionMesh, ArchitectureReduction, and RiskEvidenceLedger tests for absorbed helper behavior.
- [x] 5.4 Update FlowGuard self-maintenance models and route topology evidence for the role split and cleanup dispositions.
- [x] 5.5 Run focused route tests and repair failures until current evidence is passing.

## 6. Validation, Sync, And Release

- [x] 6.1 Run OpenSpec strict validation, FlowGuard project audit, and focused/full pytest validation.
- [x] 6.2 Run FlowGuard self-maintenance and structure/cleanup checks, then update adoption/topology evidence.
- [ ] 6.3 Sync source, shadow workspace, and installed skill copies; verify imports and expected version from each location.
- [ ] 6.4 Bump version, update changelog and README version row, then verify package metadata.
- [ ] 6.5 Commit scoped release changes, tag, push to GitHub, and create the GitHub release.
- [ ] 6.6 Confirm GitHub release, tag, README version, package version, and local install all agree.
