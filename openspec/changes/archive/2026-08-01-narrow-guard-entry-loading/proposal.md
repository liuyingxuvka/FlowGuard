## Why

FlowGuard already supports route-first, progressively deep modeling, but its guaranteed first-read bundle can omit required references from the budget, several direct routes lack discriminating admission evidence, and Existing Model Preflight can reject a current owner when a ledger stores the owner as a path while the observed snapshot exposes its logical id. These defects make a nominally compact entry either larger than reported or incorrectly blocked.

## What Changes

- Make the kernel entry load only the compact route index before ownership is selected; load the modeling protocol and deeper references only after the kernel route is selected or a named gap triggers them.
- Derive guaranteed prompt components from declared skill/reference loading instead of trusting a hand-maintained path list, report conditional components separately, require practical budget headroom, and keep the byte proxy explicitly separate from provider token or billing data.
- Extend the existing `RouteProfile` authority with positive conditions, forbidden conditions, first action, conditional reference edges, and deepening triggers for all fifteen public routes without introducing another router.
- Add discriminating positive, near-neighbor, forbidden, and conflict cases for the five public routes not covered by the existing AI trigger model.
- Reconcile Behavior Commitment Ledger owner paths, observed logical ids, model paths, and exact fingerprints before deciding that an owner projection is missing.
- Shrink the kernel skill, route index, managed project prompt projection, and default OpenAI prompt while preserving every hard gate in a single current reference owner.
- Add the missing current-format model-revision build handoff: derive one typed candidate and accepted `ModelRevisionSet` from the current observed head plus one exact-current terminal-pass full model-regression parent receipt, persist content-addressed artifacts, and leave activation to the existing atomic command.
- Refresh existing FlowGuard model evidence, target-owned SkillGuard contracts, focused validation, package version `0.68.2`, and changelog entries. Installation and release actions remain outside this change's implementation run.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `flowguard-ai-entry-simplification`: Guaranteed first-read material is derived and budgeted as a narrow route shell with conditionally triggered deep references and explicit headroom.
- `flowguard-route-topology-governance`: Every public route has machine-checkable admission, exclusion, first-action, reference-loading, and deepening metadata with conflict-safe route selection evidence, and the current authority lifecycle exposes one typed build-to-activate handoff with no alternate authority path.
- `existing-model-preflight`: Current owner reconciliation accepts equivalent exact path/logical-id/fingerprint identities and blocks mismatched or ambiguous identities.

## Impact

Affected surfaces include `flowguard.prompt_budget`, `flowguard.self_maintenance`, the FlowGuard AI trigger model, Existing Model Preflight, the kernel skill and route reference, project adoption prompt generation, OpenAI prompt metadata, the model-authority API/CLI, model-owned checks, SkillGuard contract generation, tests, and package release metadata. No compatibility reader, alias route, second router, installation, Git publication, tag, or GitHub release is introduced by this implementation change.
