## Context

FlowGuard now has a compact skill kernel plus direct satellite skills. The
remaining bloat is mostly behind the first `SKILL.md` layer:

- `model-first-function-flow/references/modeling_protocol.md` contains long
  route trigger sections that repeat satellite responsibilities.
- The kernel reference directory contains exact copies of some satellite-owned
  reference protocols.
- ModelMesh and Model-Test Alignment reference protocols include long prompt
  templates inline, forcing agents to ingest templates even when they only need
  route rules.

This change keeps the public behavior contract unchanged: the kernel still
routes, satellites remain directly invokable, and detailed protocols remain
available on demand.

## Goals / Non-Goals

**Goals:**

- Keep first-read and second-read guidance compact enough for agents to use
  without losing hard safety gates.
- Make one canonical owner for satellite reference detail.
- Preserve all route-specific detail in reachable files.
- Add regression tests that fail when duplicate copies or long inline prompt
  templates return.
- Synchronize source, editable install, installed skills, shadow workspace, and
  local git evidence before claiming completion.

**Non-Goals:**

- Do not remove any FlowGuard satellite skill.
- Do not remove detailed protocol content from the repository.
- Do not change FlowGuard runtime semantics or helper APIs.
- Do not push to GitHub or publish a public release.

## Decisions

1. **Satellite protocols are canonical.**
   When a protocol belongs to a standalone satellite, the satellite
   `references/` copy owns the detailed content. Kernel-side duplicates become
   short handoff stubs.

2. **Templates are lazy-loaded.**
   Long "ask another agent to do this" prompt templates move into
   `references/templates/`. The primary protocol keeps the required input shape
   and links to the template.

3. **The core modeling protocol becomes a route handoff.**
   The core modeling protocol keeps the thin modeling workflow and hard gates.
   Satellite route trigger detail is folded into a compact table with target
   skill/reference paths.

4. **Tests protect the compression shape.**
   Tests should check structural invariants: no exact duplicate reference
   copies, prompt templates split out of main protocols, handoff stubs stay
   compact, and detailed content remains reachable.

## Risks / Trade-offs

- **Risk: over-compression hides safety gates.** Mitigation: keep hard gates in
  `SKILL.md` shells and keep detailed protocol files reachable.
- **Risk: tests overfit prose.** Mitigation: test ownership, size, and required
  anchors rather than long exact wording.
- **Risk: source/shadow/install drift.** Mitigation: sync whole relevant source
  sets and verify hashes/imports after edits.
- **Risk: peer-agent edits appear mid-run.** Mitigation: recheck status before
  commit and stage only files touched by this change.
