## Why

FlowGuard can currently prove that a model is executable, covered, connected, and evidence-bound, but it does not require the model's own path shape to be justified. A model can therefore enter software DNA while still containing unreachable states, duplicated transitions, unnecessary intermediate work, or several equivalent routes that were never compared.

## What Changes

- Require one current path-quality result for every new or materially changed model before that model enters current DNA.
- Keep ordinary use lightweight: run a bounded structural review for every affected model and avoid deep candidate expansion when there is one clear path.
- Trigger deep review only from an explicit request or current evidence such as multiple hard-equivalent paths, material state/branch growth, duplicated or unreachable structure, repeated work, a path-design model miss, missing necessity evidence, or a high-cost/release-critical boundary.
- Compare candidates only after hard semantic equivalence is proved across inputs, outputs, state, protected errors, side effects, order, retry, timeout, progress, permissions, parent/child interfaces, intent, authority, oracles, and evidence obligations.
- Keep cost as a multi-dimensional vector and license only bounded conclusions: `single_clear_path`, `preferred_within_candidates`, `non_dominated_within_boundary`, `minimum_within_exhausted_finite_set`, `locally_irreducible_under_declared_rewrites`, or `unresolved`. Never claim an unrestricted global optimum.
- Require a necessity witness for each retained model element and retain an exact unresolved row when a witness, equivalence proof, candidate boundary, or current evidence is missing.
- Store a compact path-quality summary and fingerprint in the current model revision; keep deep candidate bodies in referenced evidence so parent models and ordinary prompts do not repeatedly load them.
- Keep observed and normative models distinct: observed models remain faithful to current behavior even when inefficient; a proposed improvement remains a normative target until implementation and current evidence make it observed.
- Keep existing owners: ModelMaturation owns single-model path quality, ModelMesh owns cross-model topology, Architecture Reduction consumes accepted model results for code contraction, DevelopmentProcessFlow owns work order, and Model-Test Alignment/TestMesh own executable evidence. No new public skill, route, CLI command, compatibility reader, or reconstruction workflow is added.
- Use the same general capability to audit and contract FlowGuard's own models before release.

## Capabilities

### New Capabilities

- `model-path-quality-closure`: Defines lightweight and triggered-deep path review, hard-semantic equivalence, cost-vector comparison, necessity witnesses, bounded conclusions, compact evidence, and freshness.

### Modified Capabilities

- `model-maturation-iterative`: Makes the per-model path-quality result part of maturation closure.
- `authoritative-model-system`: Requires current path-quality summaries on new or materially changed observed models.
- `target-system-blueprint`: Carries exact path-quality subjects and compact parent/child summaries in a provider-neutral blueprint.
- `software-blueprint-readiness`: Blocks broad DNA readiness on missing, stale, or unresolved required path-quality rows.
- `model-revision-set`: Publishes path-quality identities atomically with the same current model revision rather than a second authority pointer.
- `hierarchical-model-mesh`: Propagates changed-child path-quality freshness and compact summaries without loading every deep detail.
- `architecture-reduction`: Consumes path-quality provenance for mapped implementation contraction without becoming a second model optimizer.
- `model-test-alignment`: Binds affected semantic obligations and necessity witnesses to current code, tests, and oracles without claiming optimality.
- `development-process-flow`: Places lightweight/deep path review in the correct pre-code and activation order while keeping deep work conditional.
- `flowguard-skill-kernel`: Exposes the compact result and trigger state in AI guidance without adding a public optimization route or reconstruction ceremony.

## Impact

- New internal path-quality data and review logic plus focused model/runner, revision, blueprint, readiness, topology, alignment, process, and skill-kernel integrations.
- New native and unit cases for structural findings, bounded rewrite comparison, exact claim language, freshness, token/payload bounds, observed-versus-normative separation, and FlowGuard self-use.
- Current model authority and self-blueprint projections must be rebuilt after the final model-owner set is frozen; existing release and installation domains remain separately verified.
