## Context

FlowGuard has grown by closing real gaps: model/test alignment, TestMesh,
StructureMesh, ModelMesh, UI Flow Structure, Architecture Reduction,
DevelopmentProcessFlow, Risk Evidence Ledger, layered proof, and code-boundary
conformance all protect against known failure modes. The problem is not that
these capabilities are wrong. The problem is that the default AI-facing entry
now presents the advanced map before the simple route.

The current source repository has concurrent peer-agent work in core Python
files and a separate OpenSpec change. This change should avoid those files and
focus on guidance, tests, and synchronization surfaces.

## Goals / Non-Goals

**Goals:**

- Make the first FlowGuard path obvious to AI agents and human readers.
- Preserve every mature satellite skill and helper API as an escalation path.
- Keep advanced evidence routes discoverable without forcing their vocabulary
  into the first decision.
- Update tests so future additions cannot silently bloat the default entry.
- Preserve concurrent peer-agent changes by only staging and committing this
  change's files.
- Run practical validation, with long checks in background when useful, and
  only count final exit artifacts as proof.

**Non-Goals:**

- Do not remove public checker APIs or satellite skills.
- Do not rewrite the core Python modules currently edited by other agents.
- Do not weaken hard gates such as real package import, skipped-is-not-pass,
  stale evidence visibility, or no fake mini-framework.
- Do not publish remote GitHub releases unless explicitly requested later.

## Decisions

1. **Thin default path first.**
   The kernel, AGENTS snippet, README, and API docs should put the simple
   FlowGuard path before the route map. Advanced routes remain available but
   are introduced as escalation triggers.

2. **Escalation taxonomy instead of flat route pressure.**
   Group routes into a small set of buckets: core modeling, implementation
   structure, UI, tests/evidence, model hierarchy, process/release, and miss
   repair. This reduces choice fatigue while keeping names searchable.

3. **Public/internal separation stays explicit.**
   Public docs should emphasize that ordinary users do not need the problem
   corpus, benchmark suite, deep maintenance models, or release ledger routes
   before the minimum path works.

4. **Tests protect guidance shape.**
   Existing tests already assert many route names. Add tests for the thin path
   and current satellite count so future changes cannot regress to stale
   "seven satellites" wording or bury the minimal workflow.

5. **Version and sync are local-release quality, not remote publish.**
   Bump the local package version and changelog, refresh editable install and
   installed skills, sync the non-git shadow workspace as a whole source set,
   and create a scoped local commit/tag for this change. Leave peer-agent
   uncommitted work untouched.

## Risks / Trade-offs

- **Risk: over-compressing guidance hides safety gates.** Mitigation: keep hard
  gates visible, but separate them from the full advanced route inventory.
- **Risk: docs and tests drift from installed skills.** Mitigation: validate
  source and installed skills and verify shadow imports after sync.
- **Risk: concurrent peer-agent changes affect full regression.** Mitigation:
  avoid editing their files, report dirty-worktree boundaries, and stage only
  this change's files.
- **Risk: local tag with unrelated dirty work is confusing.** Mitigation:
  create a scoped commit only if this change's validation passes; leave
  unrelated modified files unstaged and visible in final status.
