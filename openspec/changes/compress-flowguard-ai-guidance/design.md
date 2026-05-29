## Context

FlowGuard already has the right conceptual direction: a thin default AI entry,
direct satellite routes, and reference protocols for deep work. The current
maintenance issue is that the same guidance appears in several hot-path files,
especially `docs/agents_snippet.md` and satellite `SKILL.md` files, so agents
must parse a large prompt surface before selecting the small route.

The change touches AI-facing prompt artifacts rather than core runtime behavior.
It still needs FlowGuard lifecycle governance because prompt and skill changes
affect agent behavior, installed local skills, shadow workspace imports, and
release-confidence evidence.

## Goals / Non-Goals

**Goals:**

- Make the first-read FlowGuard path shorter and more decisive.
- Keep one canonical compact router table and move long-form route detail to
  reference docs.
- Make satellite `SKILL.md` files behave as concise route shells with hard
  gates, trigger/skip criteria, minimum workflow, and reference handoff.
- Add tests that enforce prompt budgets and prevent duplicate route inventories
  from regrowing silently.
- Validate and synchronize the git checkout, editable install, installed skills,
  and shadow workspace before claiming completion.

**Non-Goals:**

- Do not remove FlowGuard satellite skills or package helper APIs.
- Do not weaken adoption/version gates, evidence honesty, model checks, or
  public-entrypoint compatibility.
- Do not introduce a new dependency or a replacement prompt framework.
- Do not publish to GitHub unless local validation, install sync, and git
  evidence support it.

## Decisions

1. **Use prompt budgets instead of prose-only intent.**
   Existing guidance already says "thin default path", but the files can still
   grow. Tests will enforce upper bounds for kernel, satellite, and AGENTS
   snippet hot paths.

2. **Keep direct satellite skills, but collapse their hot path.**
   Removing satellites would make route discovery worse. The better contraction
   is to keep each satellite discoverable while shortening its first-read
   content and pointing to route-specific reference docs for deep protocol
   detail.

3. **Centralize route inventory in one compact table.**
   The AGENTS snippet and kernel may both name routes, but they should use the
   same compact trigger table and avoid repeated helper inventories. Detailed
   helper API lists belong in reference docs.

4. **Treat prompt assets as behavior-affecting inputs.**
   Skill prompt changes need tests and install sync; repository diffs alone do
   not prove installed Codex behavior changed.

## Risks / Trade-offs

- **Over-compression can hide required gates** -> Keep hard gates in every
  standalone skill shell and move detail to references, not out of the repo.
- **Tests may overfit exact wording** -> Prefer line/budget and key-contract
  assertions over long phrase snapshots.
- **Installed skill sync can diverge from repo source** -> Verify content hashes
  or representative files after copying, then verify imports from git checkout
  and shadow workspace.
- **Background regression can look complete before it is done** -> Treat
  background progress as liveness only; final confidence waits for exit/status
  artifacts.
