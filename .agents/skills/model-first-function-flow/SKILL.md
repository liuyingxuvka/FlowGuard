---
name: model-first-function-flow
description: Use before implementing non-trivial features, stateful workflows, repeated bug fixes, module-boundary changes, idempotency-sensitive logic, deduplication logic, caching, retry handling, or data-flow changes. Builds an executable function-flow model with flowguard before production code changes.
---

# Model-First Function Flow

Use this skill before production code changes that may affect behavior, state,
retries, deduplication, idempotency, caching, side effects, module boundaries,
or workflow routing.

## Rules

- Do not edit production code first.
- First define or update a FlowGuard model.
- Represent each function block as:

```text
Input x State -> Set(Output x State)
```

- Define external inputs.
- Define abstract finite state.
- Define possible outputs.
- Define state reads and writes.
- Define idempotency rules.
- Define hard invariants.
- Run FlowGuard checks.
- Inspect counterexample traces.
- If the model fails, revise the model or architecture before production code.
- Only after the model passes may production code be implemented, unless the
  user explicitly waives modeling.
- Do not weaken hard invariants merely to pass checks.
- Do not replace executable modeling with prose.
- Always include repeated-input exploration when duplicate side effects are
  possible.
- After production code exists, export representative traces and replay them
  through a conformance adapter when feasible.
- For retry, refresh, queue, waiting, reprocessing, human review loops,
  uncertain AI decisions, caching, deduplication, or side effects, run scenario
  sandbox review and loop/stuck review when they apply.
- For progress-sensitive workflows, use progress checks when a cycle has an
  escape edge but no forced progress guarantee.
- For module-boundary or refinement-sensitive work, define FunctionContract
  checks for input/output compatibility, forbidden writes, ownership,
  traceability, and projection refinement.
- Trivial copy edits, formatting-only work, and read-only explanation tasks may
  skip FlowGuard, but record the reason when an adoption log is being kept.
- If the task boundary is unclear, mark it as `needs_human_review` or narrow the
  scope before deciding to skip or model.
- For real project adoption, record a project-local FlowGuard adoption log with
  status, trigger reason, elapsed time, commands, findings, counterexamples,
  skipped steps, friction points, and next actions.
- Adoption log status must be one of `in_progress`, `completed`, `blocked`,
  `skipped_with_reason`, or `failed`.
- Do not let adoption logging replace executable model checks.
- Before modeling in another repository, verify the real `flowguard` package is
  importable with `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- If `flowguard` is not importable, connect the real toolchain first with an
  editable install or a documented `PYTHONPATH`; do not write a temporary mini-framework and claim full FlowGuard adoption.
- If the real toolchain cannot be connected, record the task as
  `blocked/partial` instead of treating it as a passed FlowGuard check.

## Workflow

1. Read `references/modeling_protocol.md`.
2. Choose the smallest behavior boundary that can expose the risk.
3. Copy `assets/model_template/` into the target project if no model exists.
4. Replace the template domain with the project's abstract inputs, state,
   blocks, outputs, and invariants.
5. Run the model checks.
6. Inspect any counterexample trace.
7. Revise the model or intended architecture until the correct model passes.
8. Preserve important counterexamples as tests or implementation notes.
9. Edit production code only after the executable model passes.
10. After production code exists, export representative traces and replay them
    through a conformance adapter when feasible.
11. Fix production behavior or explicitly revise the model if replay shows
    divergence.
12. For workflow-heavy changes, run scenario sandbox review to compare human
    expectations with observed model behavior.
13. For retry, refresh, waiting, queue, or reprocessing flows, run loop/stuck
    review and document known limitations honestly.
14. For progress-sensitive cycles, run progress checks and report
    `potential_nontermination` or `missing_progress_guarantee` when appropriate.
15. For contract/refinement-sensitive changes, run contract checks and report
    explicit contract findings.
16. Start an `in_progress` adoption log entry when feasible and finish it with
    `completed`, `blocked`, `skipped_with_reason`, or `failed`.
17. Store machine-readable adoption entries in `.flowguard/adoption_log.jsonl`
    when feasible.
18. Store human-readable adoption notes in `docs/flowguard_adoption_log.md` when
    feasible.
19. Record skipped steps explicitly. A skipped conformance replay, loop check,
    or contract check is not a pass.
20. Record friction points and elapsed time so future FlowGuard improvements are
    based on real usage.

## Resource Map

- `references/modeling_protocol.md`: step-by-step modeling protocol.
- `references/invariant_examples.md`: invariant patterns for duplicate records,
  repeated scoring, cache consistency, state ownership, and non-consumable
  outputs.
- `references/adoption_protocol.md`: real project adoption logging protocol.
- `references/project_integration.md`: how to connect the real FlowGuard package
  in another repository before using the skill.
- `assets/model_template/model.py`: minimal FlowGuard model template.
- `assets/model_template/run_checks.py`: minimal check runner.
- `assets/adoption_log_template.md`: human-readable adoption log template.
- `assets/toolchain_preflight.py`: standard-library helper for detecting or
  installing a local FlowGuard source checkout in the active Python environment.

## Constraints

- Use only the Python standard library in the model.
- Do not call LLM APIs.
- Do not use probability, random sampling, or Monte Carlo.
- Do not use live production side effects.
- Keep the model finite and inspectable.
