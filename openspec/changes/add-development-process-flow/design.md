## Context

FlowGuard now has several sibling route surfaces:

- core modeling for product behavior workflows;
- Model-Test Alignment for direct model/code/test obligation evidence;
- ModelMesh for parent/child model boundaries;
- TestMesh for parent/child validation evidence;
- StructureMesh for parent/child code-structure boundaries.

None of those routes owns the lifecycle question: after a sequence of
development steps, which artifact versions does each validation record still
cover, and which follow-up changes made earlier evidence stale? The new route
models the development lifecycle itself as an explicit finite workflow.

## Goals / Non-Goals

**Goals:**

- Add `development_process_flow` as a parallel Skill Kernel route, not a
  supervisor route.
- Represent requirements, designs, models, code, tests, docs, release packages,
  and sibling route reports as versioned process artifacts.
- Represent development work, validation runs, peer-agent writes, claims, and
  release/archive actions as ordered process actions.
- Keep evidence status, covered artifact versions, producer route, result
  artifacts, hidden skips, background completion, and stale reasons visible.
- Detect stale validation evidence after artifact changes, verifier changes,
  peer writes, and upstream lifecycle changes.
- Derive a minimum revalidation recommendation for unsupported completion,
  release, or archive claims.
- Preserve routine-vs-release scope so release-required validation remains
  visible even when routine continuation is allowed.

**Non-Goals:**

- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment, or
  Conformance Adoption.
- Do not inspect sibling route internals. Sibling route evidence is referenced
  only as an external evidence id with metadata.
- Do not run tests, shells, model checks, or background jobs.
- Do not infer real file diffs automatically in the first implementation.
  Project adapters or agents supply structured process actions and evidence.
- Do not require every tiny edit to use this route.

## Decisions

1. **DevelopmentProcessFlow is a sibling route.**
   The route consumes plain lifecycle rows and reports lifecycle findings. It
   may reference `producer_route="test_mesh_maintenance"` or similar metadata,
   but it does not open TestMesh reports or validate their child hierarchy.

2. **Artifact versions are the freshness source of truth.**
   `ProcessArtifact.current_version` and each `ProcessEvidence.covered_versions`
   describe what evidence still covers. A later write to the artifact, or to an
   upstream artifact that the freshness rule propagates through, makes prior
   evidence stale.

3. **Verifier artifacts are first-class.**
   Tests, model files, checklists, adapters, and review prompts are artifacts.
   If a verifier changes after producing evidence, the prior evidence becomes
   stale even if the production code did not change.

4. **Claims are process actions.**
   Done, release, archive, and publish readiness are represented as actions
   with required evidence ids or validation requirement ids. The review blocks
   unsupported claims instead of treating the final process step as proof.

5. **Background progress is not completion evidence.**
   Evidence with progress output but no final exit/result artifact is current
   liveness only. It cannot satisfy a validation requirement.

6. **Minimum revalidation is derived from missing/stale requirements.**
   The helper returns a deterministic recommendation listing requirement ids,
   evidence ids, commands, scopes, and artifact ids that need fresh evidence.

7. **Known-bad hazards must fail.**
   Unit tests and the starter template must include broken variants for stale
   code evidence, stale verifier evidence, stale model-test alignment evidence,
   upstream requirement changes, hidden skips, progress-only background checks,
   failed evidence, unknown peer writes, missing V-style validation pairs, and
   release overclaims.

## Risks / Trade-offs

- **Risk: agents treat the route as a meta-orchestrator.** -> Mitigation: Skill
  and docs explicitly say sibling route evidence is referenced, not inspected or
  supervised.
- **Risk: version rows become busywork.** -> Mitigation: templates start with a
  compact V-style lifecycle and focused artifact ids; projects can add adapter
  automation later.
- **Risk: false stale propagation from broad upstream rules.** -> Mitigation:
  freshness rules are explicit and visible; ambiguous rules produce findings
  instead of silent invalidation.
- **Risk: routine work is blocked by release-only evidence.** -> Mitigation:
  routine and release scopes mirror TestMesh/StructureMesh: routine can defer
  release-required validation visibly, release cannot.
- **Risk: overlap with Model-Test Alignment.** -> Mitigation: Model-Test
  Alignment checks whether obligations and evidence match; DevelopmentProcessFlow
  checks whether that alignment evidence still covers current artifact versions.
