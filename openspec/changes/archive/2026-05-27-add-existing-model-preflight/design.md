## Context

The current route table is good at choosing the right FlowGuard route once the
agent recognizes the class of work. It does not yet force the agent to anchor
early discussion and implementation planning in the existing model map.

This change introduces a companion skill and helper. The companion preflight is
selected alongside the downstream route when the work is in an existing modeled
system.

## Decisions

1. **Make the feature a peer companion skill, not a universal parent.**

   `flowguard-existing-model-preflight` is directly invokable and discoverable,
   but it does not replace downstream FlowGuard skills. It answers "what model
   map already exists?" before the downstream route answers "what should we do
   next?"

2. **Use light and full modes.**

   Light mode is for discussion, exploration, and early analysis. It needs a
   short grounding note with relevant models and a reuse-first recommendation.
   Full mode is required before implementation, OpenSpec proposal, major
   architecture decisions, or risky behavior changes. It needs structured hits,
   ownership snapshots, duplicate-risk review, reuse decision, and downstream
   route.

3. **Review grounding as structured evidence.**

   The package helper checks that the report names relevant models or explicitly
   says none were found, records existing ownership when model hits exist,
   explains reuse or new-boundary decisions, keeps stale evidence visible, and
   blocks parallel ownership without rationale.

4. **Keep existing FlowGuard helpers authoritative.**

   Code Structure Recommendation still derives implementation structure.
   ModelMesh still governs parent/child model partitions. StructureMesh still
   governs code splits. UI Flow Structure still owns UI behavior. The new helper
   supplies upstream context to those routes.

5. **Prompt wording constrains the result, not a rigid sequence.**

   Global guidance says existing-system reasoning must be grounded in existing
   FlowGuard models before choosing a technical route. It avoids saying every
   task must first run this skill.

## Risks / Trade-offs

- **Risk: over-triggering on trivial tasks.** Mitigation: skip trivial typo,
  formatting, pure explanation, direct command answers, and greenfield work with
  no existing model context.
- **Risk: prose-only "I checked" claims.** Mitigation: full mode uses
  `review_existing_model_preflight(...)`.
- **Risk: blocking new architecture when needed.** Mitigation: new boundaries
  are allowed when the report explains why existing models cannot carry them.
- **Risk: stale model evidence.** Mitigation: stale hits remain visible and
  route to ModelMesh or model update work instead of being treated as green.

## Implementation Shape

1. Add package objects and `review_existing_model_preflight(...)`.
2. Add CLI/template support and docs.
3. Add `.agents/skills/flowguard-existing-model-preflight`.
4. Update kernel/global prompt guidance and peer skill tables.
5. Add focused unit tests, skill-doc tests, and a local FlowGuard model for this
   route behavior.
6. Run focused checks, then background/full regression evidence, install sync,
   shadow workspace sync, version bump, changelog, and Git state verification.
