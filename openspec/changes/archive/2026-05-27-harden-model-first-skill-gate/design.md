## Context

The current `model-first-function-flow` Skill already requires Risk Intent
Briefs, model updates before production changes, counterexample inspection,
model-miss review, background log artifacts, adoption notes, and optional
planner handoffs. It still leaves a gap for complex optimization work: agents
can produce a broad plan, update or run a model, and then edit code without
first proving that the model can catch the specific regressions the plan may
introduce.

The requested change converts repeated user prompting into a stable skill gate.
It is a process-level Skill and AGENTS-snippet update, supported by focused
tests and a small FlowGuard rollout model.

## Goals / Non-Goals

**Goals:**

- Make complex optimization work start from a concrete change inventory and
  risk catalog.
- Require a risk-to-model coverage matrix before code edits for non-trivial
  FlowGuard-backed changes.
- Require known-bad hazards or scenarios to fail before the model is trusted for
  the target bug class.
- Preserve FlowGuard's fit-for-risk principle: run the smallest sufficient
  model first, and handle expensive model groups through explicit tiering,
  background execution, evidence collection, and residual-risk notes.
- Keep installed Skill, repository Skill, AGENTS snippet, OpenSpec artifacts,
  changelog, package version, and release tag aligned.

**Non-Goals:**

- Do not add runtime dependencies.
- Do not add a new public Python API unless tests show the documentation-only
  contract is not enforceable.
- Do not hard-code current-project model names such as Meta or Capability into
  the generic Skill.
- Do not require every trivial edit to run the hardening gate.

## Decisions

1. Add the gate to `Daily Rules` and the numbered `Workflow`.

   Rationale: `Daily Rules` are where agents look for operating constraints,
   while `Workflow` controls execution order. Putting the gate in only one
   location would leave either the principle or the sequence ambiguous.

   Alternative considered: put the whole gate in a separate reference file.
   Rejected for the first release because the gate must be visible during
   ordinary skill use and is short enough to live in `SKILL.md`.

2. Use a compact matrix contract instead of a verbose template file.

   Rationale: The key is forcing traceability from planned change to possible
   bug to model evidence. A compact table is easier for agents to follow than a
   long form and is cheap enough for every complex optimization.

3. Treat heavy model groups generically.

   Rationale: Current-project model names and state counts are local facts.
   The reusable Skill should say how to classify and handle heavy checks, not
   assume any specific model is always heavy or always skippable.

4. Pin the behavior with text-focused tests and a rollout model.

   Rationale: The change modifies an agent workflow contract rather than core
   runtime behavior. Existing tests already validate important Skill language;
   extending that style gives a lightweight regression barrier. A local model
   adds scenario-level coverage for known-bad variants.

## Risks / Trade-offs

- Gate becomes too ceremonial for small work -> Trigger it only for complex
  optimizations, repeated bugs, stateful refactors, broad changes, or model
  miss-sensitive work; trivial work still skips with reason.
- Agents overclaim from green model output -> Require known-bad hazards,
  residual blindspots, and production-facing checks after edits.
- Expensive model groups block all progress -> Use tiered model cost policy and
  background logs, but require final evidence or an explicit skipped boundary.
- Skill and AGENTS snippet drift -> Update both in the same task and add tests
  for both surfaces.
- Shadow workspace or installed Skill drifts from git source -> Include release
  sync checks for the installed Skill and local shadow workspace before
  publishing.

## Migration Plan

1. Add OpenSpec artifacts for the new capability.
2. Add a local FlowGuard rollout model for the gate.
3. Update the Skill and AGENTS snippet.
4. Add focused tests for the Skill, snippet, and rollout model.
5. Run focused validation, then full test validation in background if it is
   long-running.
6. Sync the installed Skill and shadow workspace from the release source.
7. Bump the patch version, update changelog, commit, tag, push, and create a
   GitHub Release.
