## Context

The route already has the needed runtime primitives: process artifacts, process
actions, evidence rows, validation requirements, freshness rules, and minimum
revalidation recommendations. The gap is in the Codex-facing route trigger and
the public descriptions. They currently bias agents toward using the route near
the final completion or release claim, not during the earlier planning stage of
a staged edit.

## Goals / Non-Goals

**Goals:**

- Make the trigger simple: non-trivial staged development/modification plus
  validation means use `flowguard-development-process-flow`.
- Preserve one route. Do not introduce separate modes or a second skill.
- Keep the existing hard gates: real package, no fake mini-framework, skipped
  or stale validation is not a pass, peer writes can stale evidence.
- Keep DevelopmentProcessFlow as a sibling route that can reference sibling
  evidence ids but does not inspect or supervise sibling internals.
- Make the installed global skill match the repository source copy.

**Non-Goals:**

- Do not change the public Python API.
- Do not change DevelopmentProcessFlow review semantics.
- Do not make every trivial typo, formatting-only edit, or pure explanation use
  the route.
- Do not add a new two-tier skill mode.

## Decisions

1. **Broaden the trigger where agents choose skills.**
   The satellite `description`, satellite `openai.yaml`, Skill Kernel route
   map, modeling protocol trigger, AGENTS snippet, README, and public docs will
   all say staged development or modification with validation is sufficient.

2. **Keep one route and let scope decide effort.**
   The text will not create a named lightweight/heavyweight split. Agents should
   use the route directly, with detail proportional to task complexity.

3. **Preserve final-readiness semantics.**
   Done, archive, publish, and release confidence remain important
   DevelopmentProcessFlow use cases. The change adds earlier staged-work
   triggers without removing final claim checks.

4. **Validate the wording as a route contract.**
   Skill/docs tests will assert both the new staged-development trigger and the
   existing evidence-freshness/final-claim boundaries.

## Risks / Trade-offs

- **Risk: over-triggering on trivial work.** Mitigation: trigger text keeps the
  `non-trivial` and `requires validation` conditions and explicitly allows
  trivial copy, formatting, and pure explanation to skip.
- **Risk: agents treat DevelopmentProcessFlow as a parent supervisor.**
  Mitigation: keep sibling-route language and non-goals intact.
- **Risk: installed skill drifts from repository source.** Mitigation: sync the
  global copy from the repository and verify matching file hashes.
- **Risk: publishing before adjacent issues are understood.** Mitigation: keep
  this pass local-only; do not bump release version, tag, push, or create a
  GitHub Release until a later publication pass.
