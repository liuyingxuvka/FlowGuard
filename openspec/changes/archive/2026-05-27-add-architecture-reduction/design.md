## Context

FlowGuard currently has three related but separate pieces:

- core executable modeling over finite `Input x State -> Set(Output x State)` transitions;
- Code Structure Recommendation, which maps modeled FunctionBlocks, state, side effects, config, and entrypoints into target modules;
- StructureMesh, which governs large code-structure refactors with facade compatibility, dependency, config, and behavior parity evidence.

The missing piece is a review route that starts from an existing codebase and model map, asks whether the implemented flow is more complex than the behavior requires, proves or bounds candidate reductions, and hands a target contraction plan to Code Structure Recommendation and StructureMesh. The route must be useful to Codex agents as a visible subskill, but it must not directly rewrite production code without the existing refactor gates.

## Goals / Non-Goals

**Goals:**
- Provide a first-class architecture reduction review for model-backed code contraction.
- Distinguish model-only simplification from code architecture simplification.
- Classify candidates such as handler/module merges, pass-through adapter collapse, branch removal, state-field removal, and public facade retention.
- Attach proof status to every candidate so agents can tell safe reductions from property-only or missing-evidence suggestions.
- Produce a target structure handoff that can feed Code Structure Recommendation and StructureMesh.
- Add routing guidance so related FlowGuard skills invoke architecture reduction when complexity-growth signals appear.

**Non-Goals:**
- Automatically editing production code.
- Replacing StructureMesh parity checks for large refactors.
- Replacing conformance replay or tests for production behavior confidence.
- Implementing a full Python semantic equivalence prover.
- Treating classic DFA minimization as the only reduction method.

## Decisions

1. Add a helper API rather than changing core model semantics.
   - Rationale: architecture reduction is a review and planning layer. It should consume model/code ownership evidence without changing `FunctionBlock`, `Workflow`, or `Explorer`.
   - Alternative considered: add minimization into the explorer. Rejected because the goal is code contraction with entrypoint, state, side-effect, and facade mapping, not only graph-size reduction.

2. Use explicit observable contracts.
   - Rationale: "same behavior" is only meaningful after declaring public entrypoints, outputs, state fields, side effects, config, errors, and validation obligations that must be preserved.
   - Alternative considered: infer observable behavior from all model fields. Rejected because many model fields are internal proof scaffolding and should not block safe code simplification.

3. Represent reductions as candidates with proof status.
   - Rationale: agents need reviewable recommendations such as `safe_by_equivalence`, `safe_by_public_facade`, `property_only_safe`, `needs_conformance_replay`, `risky_keep`, and `blocked_by_missing_evidence`.
   - Alternative considered: return one pass/fail decision. Rejected because architecture contraction is usually a mixed report with safe, blocked, and intentionally-kept areas.

4. Keep implementation conservative and structural first.
   - Rationale: the initial API can catch high-value cases using ownership maps and declared equivalence groups: duplicate owners, pass-through adapters with no state/side effect/config ownership, removable branches with no observable difference, and state fields not in the observable contract.
   - Alternative considered: implement SAT/BDD or AST-wide dataflow immediately. Rejected for this change because the first useful capability should land without new dependencies or broad source analysis risk.

5. Route actual code changes through existing gates.
   - Rationale: architecture reduction decides what may be simpler; StructureMesh and DevelopmentProcessFlow decide whether a code refactor was safely executed and validated.

## Risks / Trade-offs

- [Risk] The helper may overclaim behavior equivalence from incomplete mappings. -> Mitigation: require observable contract, source model id, source structure id, and validation boundary fields; mark missing evidence as blockers.
- [Risk] Agents may delete public facades that are needed for compatibility. -> Mitigation: candidates can require facade retention, and any public-entrypoint change must go through StructureMesh.
- [Risk] Property-only reductions may be mistaken for full behavior preservation. -> Mitigation: proof status and report decision distinguish `architecture_reduction_ready`, `conformance_required`, `property_only_review`, and blocked states.
- [Risk] Other FlowGuard skills may call the route too often and slow down routine work. -> Mitigation: use explicit complexity-growth triggers rather than a universal mandatory gate.
- [Risk] Parallel agents may edit neighboring skill docs. -> Mitigation: keep touched files scoped and sync only known edited paths into the git repository.
