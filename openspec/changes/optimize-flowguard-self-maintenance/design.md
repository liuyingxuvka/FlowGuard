## Context

FlowGuard already has specialist routes for existing-model preflight, field lifecycle, architecture reduction, code structure recommendation, model/test alignment, test mesh, structure mesh, model mesh, development process flow, risk evidence, closure contracts, UI flow, model miss review, agent workflow rehearsal, and the newer model-angle deliberation route. The main problem is not missing capability. The problem is that AI-facing discovery still makes too much of this capability look flat, optional, or disconnected.

Current inspection showed:

- `FLOWGUARD_ROUTE_API` exposes fewer route groups than the installed route set.
- The public surface is large enough that AI consumers can see many helper names before they see the recommended route chain.
- Repeated evidence fields such as metadata, summary, rationale, findings, severity, and proof freshness appear across many dataclasses.
- Several route modules contain long review functions whose internal responsibilities are harder to isolate, test, and maintain.
- Existing validation and install-sync tasks are already tracked in nearby OpenSpec changes, so this change must preserve peer work and treat sync as evidence, not as an informal cleanup step.

## Goals / Non-Goals

**Goals:**

- Make FlowGuard self-maintenance route-first: AI starts from route intent, minimal inputs, owner route, proof boundary, and next actions.
- Add a parent self-maintenance mesh that coordinates route graph completeness, field layering, structure split governance, validation evidence, install/shadow sync, and closure claims.
- Fold repeated field/proof concepts into shared profiles and evidence references without deleting behavior-bearing evidence.
- Preserve public API compatibility while making route discovery compact and complete.
- Keep large internal refactors facade-first and parity-checked through StructureMesh and DevelopmentProcessFlow.
- Update tests, docs, installed skill guidance, and adoption logs in the same evidence chain.

**Non-Goals:**

- No breaking removal of existing public entrypoints in this change.
- No rewrite of FlowGuard's core modeling kernel.
- No claim that background tests passed until their exit status and artifacts are collected.
- No rollback of peer-agent changes or unrelated OpenSpec work.

## Decisions

### 1. Route Graph Before Deletion

FlowGuard will add a route graph completeness layer before pruning or hiding fields. This keeps existing capability available while making the AI path lighter.

Alternative considered: delete or move fields first. That risks removing evidence fields that still carry safety contracts and makes route ownership unclear.

### 2. Thin Profiles Over Thin Evidence

Common AI tasks will use lightweight profiles that expose only required input fields and route-owned handoffs. Full evidence structures remain available when the owning route runs.

Alternative considered: replace large dataclasses with smaller dataclasses. That would be a breaking data-model change and would force migration before the usage path is clear.

### 3. Shared Evidence References

Repeated proof/freshness/scope concepts will be represented through shared evidence-reference helpers and route profiles. Routes can still keep domain-specific fields when they carry behavior, compatibility, or audit meaning.

Alternative considered: collapse all repeated fields into `metadata`. That would make evidence less inspectable and would weaken model-test alignment.

### 4. Facade-First Structure Work

Oversized route modules may gain internal child helpers, but public imports and route entrypoints must remain stable until StructureMesh parity evidence supports a contraction.

Alternative considered: split files aggressively and update imports everywhere. That would create peer-agent conflict risk and make validation harder.

### 5. Self-Maintenance Mesh As Parent Evidence

The new parent model will not replace specialist route checks. It will collect child closure reports and block broad confidence when route graph, fields, structure, tests, install sync, or closure evidence is stale.

Alternative considered: add a prose checklist only. That would not give FlowGuard executable self-maintenance behavior.

## Risks / Trade-offs

- Route graph becomes another surface to maintain -> Mitigate with API surface tests, installed skill tests, and OpenSpec specs that require route groups to name handoffs and evidence owners.
- Lightweight profiles could hide required evidence -> Mitigate by making profiles entry-only and requiring route-owned expansion before broad claims.
- Shared evidence references could become vague -> Mitigate by preserving owner route, artifact kind, freshness, scope, and unsafe claim boundary.
- Large regression tests may be slow -> Mitigate with TestMesh-style child evidence and explicit timeout/skipped/stale status.
- Local git sync may be unavailable in the shadow workspace -> Mitigate by finding the real repository, reporting unavailable git state when absent, and never pretending a non-git directory was committed.
