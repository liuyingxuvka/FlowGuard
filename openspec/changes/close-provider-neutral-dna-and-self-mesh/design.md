## Context

The current FlowGuard target-system blueprint already contains software and non-code-workflow profiles and a provider registry. The self blueprint and reduction audit also have useful evidence structures, but their public projections allow a statically complete artifact to be mistaken for a semantically qualified current DNA. Downstream Guard skills therefore need a narrow extension of the existing structures, not a parallel framework.

## Goals / Non-Goals

**Goals:**

- Reuse the existing target-system provider registry and layer-plan types.
- Add explicit provider/profile admission checks and a provider-neutral qualification projection.
- Preserve the distinction between static readiness, semantic currentness, code binding, and test binding.
- Make reduction reports truthful without deleting or contracting any unresolved path.
- Keep the ordinary path single and lightweight; reconstruction remains a separate caller-owned operation.

**Non-Goals:**

- No domain-specific ResearchGuard, PhysicsGuard, or WorldGuard semantics in FlowGuard.
- No automatic reconstruction, language translation, fallback, alias, compatibility reader, or second model authority.
- No deletion or contraction of existing code in this change.

## Decisions

1. **Extend the existing registry instead of creating a new one.** The current `TargetSystemProviderRegistry` and layer plans are already the canonical owner. A small provider-neutral declaration/qualification surface will be added beside them so all callers share one admission path.

2. **Use explicit qualification status, not a boolean readiness flag.** The result will carry separate status fields and reasons for static blueprint, semantic mesh, code bindings, and test bindings. A qualified claim is the conjunction of current positive statuses; unknown, candidate, stale, or missing remains visible.

3. **Require exact identity edges.** Parent/child models, code owners, and tests are qualified only when their declared fingerprints and owner identities match the current snapshot. Counts are diagnostic only and never authorize a claim.

4. **Project reduction truth as three independent facts.** Existing cleanup fields remain compatible, while new projections make inventory completeness, proof completeness, and applied-and-verified simplification independently inspectable.

5. **Keep reconstruction outside the kernel.** FlowGuard exports the model and qualification evidence. A caller that explicitly requests reconstruction owns that separate workflow and its tests.

## Risks / Trade-offs

- [Risk] Existing callers may assume a single readiness boolean. → Keep existing fields, add explicit status fields, and update only the qualification projection and tests.
- [Risk] Some historical snapshots will become visibly unqualified. → Preserve their static reports and explain the exact stale/missing reason instead of fabricating current evidence.
- [Risk] Downstream skills may be tempted to register domain logic in FlowGuard. → Validate only provider-neutral metadata and document that domain semantics remain in the provider.

## Migration Plan

1. Add the provider-neutral declaration and qualification result to the existing blueprint modules.
2. Add focused tests and run the current FlowGuard project audit.
3. Update the FlowGuard skill/model adoption records and install projection only after the source checks pass.
4. Downstream Guard repositories consume the new projection in their own OpenSpec changes; no compatibility reader is added.

## Open Questions

None. The existing registry and evidence identities are the canonical owners for this change.
