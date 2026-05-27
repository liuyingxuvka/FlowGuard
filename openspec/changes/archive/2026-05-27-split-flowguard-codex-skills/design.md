## Context

The current `model-first-function-flow` Skill is already a kernel with detailed
route procedures stored in `references/*.md`. Several routes are now stable
enough to be useful as directly invokable Codex skills:

- model-test alignment;
- development process / validation freshness;
- post-runtime model-miss review;
- model-derived code structure recommendation;
- ModelMesh;
- TestMesh;
- StructureMesh.

The package helper APIs and CLI templates already exist for most of these
routes. This change is about Codex skill discoverability, installed skill
sync, prompt routing, and release hygiene rather than new checker semantics.

## Goals / Non-Goals

**Goals:**

- Keep `model-first-function-flow` as the canonical FlowGuard Skill Kernel.
- Add seven standalone FlowGuard satellite skills under `.agents/skills/`.
- Make every satellite skill self-contained enough for direct Codex invocation.
- Keep each satellite bounded to one route and route ambiguous cases back to
  the kernel.
- Update AGENTS/global prompt guidance to describe the new topology.
- Add tests that verify the 1 + 7 skill topology and key trigger language.
- Sync repository skills to installed Codex skills before release.
- Release the change as a new public version.

**Non-Goals:**

- No new public checker API is required.
- No package helper API becomes a Codex skill by itself.
- No behavior change to core FlowGuard modeling semantics.
- No separate standalone skills for `conformance_adoption`,
  `long_check_observability`, or `framework_upgrade` in this release.

## Decisions

### Kernel plus satellite skills

The kernel remains the only skill that owns global applicability decisions,
hard gates, flow lens selection, and ambiguous route selection. Seven satellite
skills own route-specific execution when the user's request clearly matches
their trigger.

Alternative considered: keep every route internal to the kernel. That would
avoid duplication but keeps Codex discovery too coarse as the route set grows.

### FlowGuard-prefixed skill names

The standalone skills use `flowguard-<route>` names. This keeps them grouped in
Codex skill lists and avoids collisions with generic "mesh" or "alignment"
skills.

Alternative considered: use shorter names such as `model-test-alignment`.
Those are easier to read but less clearly bound to FlowGuard.

### Minimal self-contained satellite skills

Each satellite `SKILL.md` includes its trigger, hard gates, workflow, owned
helper APIs/templates, non-goals, and validation standard. Where a detailed
protocol already exists, the satellite can keep a concise body and load its
own copied reference file as needed.

Alternative considered: have satellites point back into the kernel's references
only. That would reduce duplication but makes installed satellite skills less
self-contained.

### Shared support remains internal

`conformance_adoption`, `long_check_observability`, and `framework_upgrade`
remain kernel routes for now because they are cross-cutting release/support
protocols or high-risk internal framework gates rather than first-batch
direct user skills.

## Risks / Trade-offs

- **Routing drift** -> Tests verify satellite names, triggers, references, and
  kernel route links. The AGENTS snippet documents that ambiguous routing
  returns to the kernel.
- **Duplicated protocol text** -> Keep satellite bodies concise and copy only
  the route-specific reference needed for standalone use.
- **Installed skill mismatch** -> Release validation checks both repository
  skills and installed Codex skills after syncing.
- **Over-triggering standalone skills** -> Each satellite declares non-goals
  and routes unclear or cross-cutting work back to the kernel.
