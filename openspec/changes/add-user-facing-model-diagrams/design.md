## Context

FlowGuard skills currently emphasize executable modeling, route choice, and
validation evidence. That protects correctness, but a user may still not see
what the model did or why a modeling step mattered, especially for UI journeys,
model meshes, and staged development flow. The desired change is intentionally
lightweight: improve skill prompts so agents can explain model value with a
diagram when useful, without adding a mandatory reporting format.

## Goals / Non-Goals

**Goals:**

- Add a small, reusable user-facing diagram guidance note to the skill kernel.
- Add route-specific diagram guidance to the three most abstract or visual
  satellite skills: UI Flow Structure, ModelMesh, and DevelopmentProcessFlow.
- Encourage Mermaid as the default in chat/docs because it is text, diffable,
  and already supported by FlowGuard helper APIs.
- Keep diagrams expressive when used: major states, branches, gates, evidence,
  claim boundaries, and important missing paths.
- Preserve the user's lightweight direction: no new hard gate that forces every
  FlowGuard answer to include a diagram.

**Non-Goals:**

- No new public Python API.
- No automatic Mermaid generation for every report.
- No mandatory diagram in small, obvious, or purely mechanical tasks.
- No broad rewrite of every satellite skill in this release.

## Decisions

1. **Use prompt guidance instead of runtime code.** The current problem is
   explanation quality, not missing executable validation. Prompt changes keep
   the fix small and avoid overbuilding.

2. **Put the shared rule in the kernel.** `model-first-function-flow` is the
   first router most agents touch, so a compact "use diagrams when helpful"
   note belongs there.

3. **Patch only three satellite skills now.** UI Flow Structure, ModelMesh, and
   DevelopmentProcessFlow are where users most often need to understand
   branches, boundaries, evidence, and claim limits. Other skills can inherit
   the kernel rule until real usage proves they need route-specific text.

4. **Prefer richer diagrams, not stricter rules.** The rule stays optional, but
   when a diagram is used it should be useful enough to show FlowGuard's
   modeling strength rather than a shallow four-box chain.

5. **Version as a patch release.** This changes skill behavior guidance and
   public docs only; runtime schema and Python APIs remain stable.

## Risks / Trade-offs

- [Risk] Agents may overuse diagrams after seeing the prompt.  
  [Mitigation] The wording explicitly says not to force diagrams for tiny or
  obvious tasks.
- [Risk] Diagrams may become too verbose.  
  [Mitigation] The wording asks for user-facing diagrams that show major states
  and evidence, not complete internal state machines.
- [Risk] Only three satellite skills get route-specific text.  
  [Mitigation] The kernel rule covers other routes; future additions can be
  based on observed user confusion.

## Migration Plan

1. Add OpenSpec requirements and tasks.
2. Build a small local FlowGuard model that checks the desired prompt behavior:
   optional diagrams, rich diagrams when used, no mandatory diagram for trivial
   work, and targeted route coverage.
3. Update the kernel and three satellite skills.
4. Update public docs, changelog, and version metadata.
5. Sync installed skills and the shadow workspace.
6. Run focused skill validation, OpenSpec validation, FlowGuard checks,
   regression tests, privacy scans, and release checks before publishing.
