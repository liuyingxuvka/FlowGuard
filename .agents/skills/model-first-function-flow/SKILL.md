---
name: model-first-function-flow
description: For coding, repository, process-design work, structured writing/argument, and decision/planning work, first decide whether flowguard applies. Use before implementing or changing non-trivial behavior, stateful workflows, repeated bug fixes, module-boundary changes, idempotency-sensitive logic, deduplication logic, caching, retry handling, data-flow changes, multi-model FlowGuard projects that need a model mesh, or any meaningful multi-step process, argument chain, or decision path that needs validation, adjustment, observation, or loss-prevention preflight.
---

# Model-First Function Flow

For coding, repository, process-design work, structured writing/argument, and
decision/planning work, first make a lightweight applicability decision:
`use_flowguard`, `skip_with_reason`, or `needs_human_review`.

Use this skill before production code changes that may affect behavior, state,
retries, deduplication, idempotency, caching, side effects, module boundaries,
or data flow. Trivial, formatting-only, and read-only work may skip with a
reason instead of paying the cost of a model.

Also use this skill for non-code workflows when the user is designing,
checking, adjusting, or observing a process, argument, or decision path and it
has meaningful state, ordering constraints, external dependencies, irreversible
or costly actions, privacy/reputation risk, evidence or proof dependencies,
commitment changes, payment/reservation/publication side effects, or rollback
concerns. FlowGuard can model these as blindspot checks even when no software is
being edited. Examples include booking or purchase flows, publishing/release
handoffs, operational runbooks, data migration plans, support/escalation
procedures, multi-agent coordination processes, structured papers/reports, and
plan or architecture decision flows.

Do not turn this into a universal ceremony. If the task is trivial, fully
reversible, has no meaningful state or side effects, and does not need process
validation, skip with a short reason. Treat non-code models as risk-discovery
preflights, not as proof that real-world facts, prices, availability, policies,
or vendor behavior are safe.

Think in three broad flow types. The flow type is a modeling lens, not a
separate template family. Use the existing project, Risk Intent, model-miss, or
maintenance templates when they fit; otherwise create a fit-for-risk model from
`State + FunctionBlock + Invariant`.

- `behavior_flow`: software, automation, operations, releases, UI state, or
  human workflow actions. Model current phase, completed steps, persisted
  records, emitted side effects, retries, terminal status, and rollback state.
  Useful invariants: prerequisites happen before actions; retries do not create
  duplicate side effects; failures do not become success; terminal states do not
  keep mutating; non-terminal states are not stuck.
- `argument_flow`: writing, papers, reports, design docs, README claims,
  proposals, proofs, or explanations where later claims depend on earlier
  context. Model reader and argument state explicitly: introduced context,
  defined terms, declared assumptions, cited evidence, proved claims,
  referenced figures, and allowed conclusions. Useful invariants: terms are not
  used before definition; claims are not used before support; conclusions do not
  exceed available assumptions or evidence; claim dependencies are not circular.
- `decision_flow`: planning, technical choice, release/open-source choice,
  roadmap, resource tradeoff, or architecture decision work. Model goals,
  constraints, assumptions, evidence, options considered, tradeoffs recorded,
  commitments made, irreversible steps, and changed conditions. Useful
  invariants: options are not selected before goals and constraints are known;
  irreversible commitments wait for required checks; changed conditions trigger
  re-evaluation; rejected options are not silently reintroduced without new
  evidence.

## Modes

- `read_only_audit`: inspect an existing project without changing production
  code. Run import preflight, existing FlowGuard models/replays when present,
  adoption evidence review, and stale fallback checks. Do not create a new model
  merely because the task is read-only.
- `model_first_change`: production behavior may change. Build or update the
  fit-for-risk model before editing production code. If no FlowGuard model
  exists yet, create one from the current plan or adapt the model template.
- `model_maintenance`: existing `.flowguard` models, replay adapters, or
  adoption evidence appear stale. Update those artifacts before making claims
  from them. If the project has three or more local FlowGuard models, also
  inventory them and create or update a local model mesh before making broad
  continue, release, completion, or production-confidence claims.
- `process_preflight`: a non-code or mixed workflow, argument chain, or decision
  path needs validation, adjustment, observation, or loss-prevention review
  before action. Build or update a fit-for-risk model of process states,
  reader/argument states, decisions, side effects, confirmations, rollback
  paths, commitments, and hard invariants.

## Daily Rules

- Before creating model files, write a short **Risk Intent Brief**. Name the
  failure modes being prevented, protected harms, state and side effects that
  must be visible, adversarial inputs or retries to simulate, hard invariants,
  and residual blindspots. Ask the user only when materially different risk
  priorities exist and the protected harm cannot be inferred safely.
- Start with the smallest boundary that can expose the current customer risk,
  but do not confuse "smallest useful" with "shortest script" or "template
  only". The model should include enough state, branches, side effects, and
  invariants to simulate the problem the customer wants to catch.
- Treat FlowGuard model scripts as living design artifacts. If no model exists,
  create one. If later work reveals new failure modes, strengthen, extend, or
  connect the model rather than treating the first version as final.
- When a project has three or more local FlowGuard models, do not trust them as
  isolated green islands. Create or update a model mesh: inventory child
  models, runners, result files, adoption logs, evidence tiers, freshness rules,
  live/conformance adapters, cross-model dependencies, and skipped/not-run
  sections. The mesh should treat child models as evidence contracts, not inline
  every child state graph. Use `references/model_mesh_protocol.md` for the
  checklist and prompt template.
- A model mesh is required before a broad continue/release/completion claim if
  model results can be stale, if multiple models cover the same workflow from
  different angles, if one model's output is another model's input, if live
  state or conformance evidence can contradict abstract results, or if a
  post-runtime model miss shows that isolated models did not catch the bug
  class. The mesh must make known-bad hazards fail before production work uses
  the plan.
- Treat a runtime, test, replay, or manual validation failure that appears after
  a FlowGuard pass as a model-miss review trigger until proven otherwise. Do not
  patch and finish directly: classify why the earlier model missed it, represent
  the issue in the model as a scenario, invariant, replay, or explicit
  out-of-scope boundary, rerun the relevant model checks, and only then validate
  the repair with production-facing evidence.
- For FlowGuard or LiveFlowGuard framework upgrades, live failure triage, or
  broad capability claims, use coverage-first repair: first build a full
  finding ledger across invariant/model checks, model-quality audit, scenario
  or live-audit evidence, progress, contracts, conformance, skipped/not-run
  sections, and adoption evidence. Only after that ledger is visible decide
  whether to fix the real system, adjust the check flow, extend the model, or
  mark a boundary out of scope. Do not patch only the immediate failure with a
  point rule unless the ledger shows that is the right repair.
- The minimal technical path remains `State + FunctionBlock + Invariant +
  Explorer`.
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
  cancellation windows, and rollback options. For argument and decision models,
  name the reader knowledge, established claims, evidence, goals, constraints,
  assumptions, commitments, and re-evaluation triggers explicitly.
- Use property factories or domain packs when they fit, but do not make them a
  required modeling layer.
- Use the public starter template CLI when it saves setup time:
  `python -m flowguard project-template --output .`,
  `python -m flowguard risk-intent-template --output .`, or
  `python -m flowguard model-miss-template --output .`.
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

## Post-Runtime Model-Miss Review

FlowGuard passing is provisional until the modeled change or process is checked
against real tests, replay, logs, manual validation, or another appropriate
production-facing signal. When FlowGuard is used, keep an open obligation until
runtime validation and any model-miss review are closed.

If a later runtime/test/replay/manual validation step exposes a new issue after
FlowGuard passed:

1. Reopen the FlowGuard work instead of treating the prior pass as final.
2. Classify the miss: boundary too narrow, state abstraction too coarse,
   missing input branch, weak invariant, missing production writer, skipped
   replay, wrong oracle, or explicitly outside the modeled risk.
3. Represent the issue in executable evidence whenever it belongs in scope:
   add or update a scenario, invariant, replay adapter, representative trace, or
   model boundary note.
4. Confirm the old weakness is now visible: the refined model should catch the
   problem or clearly mark it out of scope before the fix is trusted.
5. Validate the repair through the refined FlowGuard checks plus the strongest
   practical runtime/test/replay evidence.
6. Before finalizing, close or explicitly carry forward the model-miss
   obligation in the adoption note. A later green runtime check by itself does
   not close a known model miss unless the miss has been reviewed.

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
   `needs_human_review`. When using FlowGuard, also classify the main lens as
   `behavior_flow`, `argument_flow`, or `decision_flow`.
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
6. Inventory existing local FlowGuard models before trusting prior green
   evidence. If there are three or more, or if multiple model boundaries can
   affect the current decision, create or update a model mesh using
   `references/model_mesh_protocol.md`.
7. Start a brief adoption note or `in_progress` log entry.
8. Write the Risk Intent Brief. If the risk priority is unclear and would
   materially change the model, ask for human review before modeling.
9. Read the modeling protocol and choose a behavior, argument, or decision
   boundary that is small enough to inspect but strong enough to expose the
   customer-relevant risk.
10. If no FlowGuard model exists yet, create one from the current plan or adapt
   `assets/model_template/`. Build or update the model with explicit inputs,
   state, blocks, outputs, reads, writes, idempotency, and invariants.
11. Build the state write inventory for fields used by invariants.
12. Run `run_model_first_checks()` when useful, or run Explorer directly.
13. Inspect counterexamples and revise the model or intended architecture until
    the correct model passes.
14. For FlowGuard/LiveFlowGuard self-upgrades, multi-model mesh upgrades, or
    model-miss triage, inspect the
    full finding ledger before choosing a repair path. Classify each actionable
    finding as real-system repair, check-flow repair, model extension, or
    explicit out-of-scope boundary.
15. Preserve important counterexamples as tests or implementation notes.
16. Edit production code or perform the modeled high-impact action only after
    executable model checks pass, unless the user explicitly waives modeling.
17. Run scenario review, loop/stuck review, progress checks, contracts, or
    conformance replay when those risks apply.
    If this would repeat an unchanged abstract run that already passed, it may
    be enough to reuse the earlier result and focus post-edit verification on
    tests, conformance replay, or other production-facing evidence.
18. If post-edit runtime validation exposes a new issue after FlowGuard passed,
    enter Post-Runtime Model-Miss Review before claiming completion.
19. Finish the adoption note with the checks run, findings, skipped checks, and
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
- `references/model_mesh_protocol.md`: trigger, inventory, evidence tiers,
  required hazards, prompt template, and completion standard for projects with
  three or more local FlowGuard models.
- `python -m flowguard project-template --output .`: basic public starter
  model.
- `python -m flowguard risk-intent-template --output .`: Risk Intent +
  CheckPlan starter.
- `python -m flowguard model-miss-template --output .`: post-runtime
  model-miss review starter.
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
