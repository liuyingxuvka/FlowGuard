## Context

The previous `add-user-facing-model-diagrams` change intentionally kept the
rule optional. That avoided over-formatting small answers, but real usage showed
the guidance was too weak: models were often explained only in prose or only in
the final summary.

This change keeps diagrams explanatory and bounded, but makes them the default
for non-trivial FlowGuard work.

## Goals / Non-Goals

**Goals:**

- Show users a compact model snapshot during non-trivial FlowGuard work.
- Make route choice, states, branches, evidence, missing paths, and claim limits
  visible while work is ongoing.
- Cover all installed FlowGuard satellite skills with route-specific diagram
  prompts.
- Preserve the rule that diagrams are not validation evidence.
- Preserve the small-task escape hatch.

**Non-Goals:**

- Do not add a public Python API.
- Do not require diagrams for trivial copy edits, one-step commands, or pure
  formatting work.
- Do not replace executable FlowGuard checks with Mermaid.
- Do not publish private local `.flowguard/` models.

## Decisions

1. **Use "default for non-trivial" instead of "mandatory for all".**
   This is stronger than optional guidance while avoiding noisy diagrams in tiny
   tasks.

2. **Place model visibility near route/model formation.**
   The kernel and satellite skills should mention a during-work snapshot, not
   only a final evidence note.

3. **Use Mermaid as the default chat format.**
   Mermaid is text, diffable, renderable in Codex/GitHub, and already supported
   by FlowGuard helpers.

4. **Keep diagrams bounded.**
   Diagrams should show the relevant model path, not the complete internal state
   graph. They should be updated when the route, model, evidence, or claim
   boundary materially changes.

5. **Test prompt semantics.**
   Focused tests should assert the stronger "default during work" language, the
   small-task escape hatch, and "not validation evidence" boundary.

## Implementation Shape

1. Add this OpenSpec change and validate it.
2. Add a local ignored FlowGuard prompt-behavior model covering:
   - trivial task may skip diagrams;
   - non-trivial UI/model-miss/release work defaults to a visible model snapshot;
   - material changes update the snapshot;
   - diagrams never count as validation evidence.
3. Update global and repository routing guidance.
4. Update all FlowGuard satellite skills and the kernel.
5. Update docs, README, CHANGELOG, tests, installed skills, shadow workspace,
   local editable install, git tag, and GitHub release.
