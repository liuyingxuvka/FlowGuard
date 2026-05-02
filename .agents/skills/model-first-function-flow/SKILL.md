---
name: model-first-function-flow
description: For coding, repository, and process-design work, first decide whether flowguard applies. Use before implementing or changing non-trivial features, stateful workflows, repeated bug fixes, module-boundary changes, idempotency-sensitive logic, deduplication logic, caching, retry handling, data-flow changes, or any meaningful multi-step process that needs validation, adjustment, observation, or loss-prevention preflight.
---

# Model-First Function Flow

For coding, repository, and process-design work, first make a lightweight
applicability decision: `use_flowguard`, `skip_with_reason`, or
`needs_human_review`.

Use this skill before production code changes that may affect behavior, state,
retries, deduplication, idempotency, caching, side effects, module boundaries,
or data flow. Trivial, formatting-only, and read-only work may skip with a
reason instead of paying the cost of a model.

Also use this skill for non-code workflows when the user is designing,
checking, adjusting, or observing a process and the process has meaningful
state, ordering constraints, external dependencies, irreversible or costly
actions, privacy/reputation risk, payment/reservation/publication side effects,
or rollback concerns. FlowGuard can model these as process blindspot checks even
when no software is being edited. Examples include booking or purchase flows,
publishing/release handoffs, operational runbooks, data migration plans,
support/escalation procedures, and multi-agent coordination processes.

Do not turn this into a universal ceremony. If the task is trivial, fully
reversible, has no meaningful state or side effects, and does not need process
validation, skip with a short reason. Treat non-code models as risk-discovery
preflights, not as proof that real-world facts, prices, availability, policies,
or vendor behavior are safe.

## Modes

- `read_only_audit`: inspect an existing project without changing production
  code. Run import preflight, existing FlowGuard models/replays when present,
  adoption evidence review, and stale fallback checks. Do not create a new model
  merely because the task is read-only.
- `model_first_change`: production behavior may change. Build or update the
  smallest useful model before editing production code.
- `model_maintenance`: existing `.flowguard` models, replay adapters, or
  adoption evidence appear stale. Update those artifacts before making claims
  from them.
- `process_preflight`: a non-code or mixed workflow needs validation,
  adjustment, observation, or loss-prevention review before action. Build the
  smallest useful model of the process states, decisions, side effects,
  confirmations, rollback paths, and hard invariants.

## Daily Rules

- Before creating model files, write a short **Risk Intent Brief**. Name the
  failure modes being prevented, protected harms, state and side effects that
  must be visible, adversarial inputs or retries to simulate, hard invariants,
  and residual blindspots. Ask the user only when materially different risk
  priorities exist and the protected harm cannot be inferred safely.
- Start with the smallest useful FlowGuard model. The minimal path remains
  `State + FunctionBlock + Invariant + Explorer`.
- Keep the API surface boundary clear. Core APIs are for direct modeling and
  exploration; helper APIs reduce boilerplate; reporting APIs explain gaps;
  evidence and benchmark APIs validate FlowGuard itself.
- Do not require ordinary project work to run FlowGuard's internal evidence
  suites. Use `docs/framework_upgrade_checks.md` only for FlowGuard framework
  upgrades, benchmark claims, or broad capability claims.
- Treat the model as a falsifiable simulator, not ground truth. Compare
  important traces with real code paths, logs, tests, known workflows, or
  conformance evidence when available.
- Calibrate model fidelity to the current risk. Include control-flow branches,
  state writes, retry/cache/deduplication behavior, terminal paths, exceptions,
  and side effects that could affect the bug class under review.
- Before trusting an invariant over a state field, create a state write
  inventory. Search for every production writer of fields such as
  `recommendation_status`, `output_status`, `analysis_json`, cache values,
  queue status, retry counters, and side-effect records. Record modeled writers
  and skipped writers with reasons.
- Represent each function block as:

```text
Input x State -> Set(Output x State)
```

- Define external inputs, finite abstract state, possible outputs, state reads,
  state writes, idempotency rules, and hard invariants.
- For non-code process models, name the real-world state and side effects
  explicitly: approvals, confirmations, reservations, payments, published
  artifacts, customer/user commitments, vendor dependencies, deadlines,
  cancellation windows, and rollback options.
- Use property factories or domain packs when they fit, but do not make them a
  required modeling layer.
- For recurring Sleep/Dream/Architect/Installer/Reviewer style maintenance
  systems, use the optional maintenance workflow scaffold when it saves setup
  time: `python -m flowguard maintenance-template --output .`.
- Use `FlowGuardCheckPlan` and `run_model_first_checks()` when useful for a
  low-friction agent path. Direct `Explorer(...)` usage remains valid.
- If the exact same abstract model, scenarios, oracle, invariants, risk
  boundary, and task revision already passed and none of those inputs changed,
  it is acceptable to reuse that result instead of rerunning the same
  simulation only for ceremony. Mention the reuse briefly. Rerunning is still
  fine when previous evidence is unavailable, stale, requested by the user, or
  useful as a cheap context refresh.
- Always include repeated-input exploration when duplicate side effects are
  possible.
- Inspect counterexample traces. If a trace is impossible, suspicious, or
  misses known behavior, revise the model, scenario oracle, or replay adapter
  before reporting confidence.
- Do not weaken hard invariants merely to pass checks.
- Do not replace executable modeling with prose.
- Use model quality audit and summary reports as optional reporting aids. Audit
  warnings are confidence boundaries, not hard failures.
- Skipped or not-run checks must remain visible. Skipped is not pass.

## Conformance Replay

After the model passes, conformance replay should be the default next check when
any of these are true:

- the invariant depends on a state field with multiple production write points;
- production code has database writes or other durable side effects;
- runtime, cleanup, repair, or finalizer paths can update the same state;
- the result will be reported as production confidence rather than model-level
  confidence;
- adapter projection is required to compare real state with abstract state.

If replay is skipped in one of these cases, record why and report model-level
confidence only. A skipped replay is not a pass.

## Adoption Logging

Whenever this Skill is used for real project work, finish with a short adoption
note. Do not treat the task as complete until the note exists.

The note can be JSONL, Markdown, or the existing project log:

- `.flowguard/adoption_log.jsonl`
- `docs/flowguard_adoption_log.md`

Keep it short, but make it useful to a future reviewer. Write these four things
in plain language:

1. Why FlowGuard was used or skipped.
2. What workflow or risk was modeled.
3. What checks or commands ran, and whether they passed or failed.
4. What FlowGuard found, what was skipped, and what should happen next.

If there was a counterexample, preserve the important label or one-sentence
trace summary. If a check was skipped, say why. A skipped check is not a pass.

The CLI is a quick way to create the log entry:

```powershell
python -m flowguard adoption-start --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>"
python -m flowguard adoption-finish --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>" --command "<check command>"
```

The CLI does not replace the short human-readable note when the model found
something important. Do not let adoption logging replace executable checks.

## Workflow

1. Decide applicability: `use_flowguard`, `skip_with_reason`, or
   `needs_human_review`.
2. Choose mode: `read_only_audit`, `model_first_change`, `model_maintenance`,
   or `process_preflight`.
3. If skipping a clearly trivial task, record one sentence explaining why and
   stop the FlowGuard workflow.
4. Verify the real package is importable before modeling in another repository:
   `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
   This prints the artifact schema version, not the GitHub/package release
   version.
5. If import fails, connect the real toolchain or record the task as
   blocked/partial. do not write a temporary mini-framework and claim full
   adoption.
6. Start a brief adoption note or `in_progress` log entry.
7. Write the Risk Intent Brief. If the risk priority is unclear and would
   materially change the model, ask for human review before modeling.
8. Read the modeling protocol and choose the smallest behavior or process
   boundary that can expose the risk.
9. Build or update the model with explicit inputs, state, blocks, outputs,
   reads, writes, idempotency, and invariants.
10. Build the state write inventory for fields used by invariants.
11. Run `run_model_first_checks()` when useful, or run Explorer directly.
12. Inspect counterexamples and revise the model or intended architecture until
    the correct model passes.
13. Preserve important counterexamples as tests or implementation notes.
14. Edit production code or perform the modeled high-impact action only after
    executable model checks pass, unless the user explicitly waives modeling.
15. Run scenario review, loop/stuck review, progress checks, contracts, or
    conformance replay when those risks apply.
    If this would repeat an unchanged abstract run that already passed, it may
    be enough to reuse the earlier result and focus post-edit verification on
    tests, conformance replay, or other production-facing evidence.
16. Finish the adoption note with the checks run, findings, skipped checks, and
    next action.

## Resource Map

- `references/modeling_protocol.md`: step-by-step modeling protocol.
- `references/invariant_examples.md`: invariant patterns.
- Repository-level `docs/api_surface.md`: public API layer map.
- Repository-level `docs/state_write_inventory.md`: lightweight state writer
  checklist for invariant fields.
- Repository-level `docs/productized_helpers.md`: optional helper-layer
  reference.
- Repository-level `docs/check_plan.md`: optional RiskProfile,
  FlowGuardCheckPlan, runner, and packs.
- Repository-level `docs/conformance_testing.md`: replay triggers and adapter
  guidance.
- `python -m flowguard maintenance-template --output .`: optional scaffold for
  multi-role maintenance flows.
- Repository-level `docs/framework_upgrade_checks.md`: FlowGuard-only upgrade
  and benchmark reference.
- `references/adoption_protocol.md`: real project adoption logging protocol.
- `references/project_integration.md`: how to connect the real package before
  using the skill in another repository.
- `assets/model_template/model.py`: minimal model template.
- `assets/model_template/run_checks.py`: minimal check runner.
- `assets/toolchain_preflight.py`: standard-library helper for detecting or
  installing the local FlowGuard toolchain in the active Python environment.

## Constraints

- Use only the Python standard library in the model.
- Do not call LLM APIs.
- Do not use probability, random sampling, or Monte Carlo.
- Do not use live production side effects.
- Keep the model finite and inspectable.
