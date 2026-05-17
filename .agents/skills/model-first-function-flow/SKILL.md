---
name: model-first-function-flow
description: For coding, repository, process-design work, structured writing/argument, and decision/planning work, first decide whether flowguard applies. Use before implementing or changing non-trivial behavior, stateful workflows, repeated bug fixes, module-boundary changes, idempotency-sensitive logic, deduplication logic, caching, retry handling, data-flow changes, multi-model FlowGuard projects that need a model mesh, slow or layered tests that need TestMesh, or any meaningful multi-step process, argument chain, or decision path that needs validation, adjustment, observation, or loss-prevention preflight.
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

FlowGuard must stay useful without any external spec, SPAC, or planning skill
installed. If an upstream planning or orchestration skill is available and has
already decomposed the task, treat its plan as optional input: inspect the
handoff for state, side effects, retries, parallel ownership, skipped checks,
counterexamples, and completion evidence. If no upstream planner exists or the
handoff is incomplete, fall back to the normal FlowGuard path or request the
missing handoff details; do not make the external planner a prerequisite for
FlowGuard.

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
  continue, release, completion, or production-confidence claims. Also trigger
  mesh review when a single model is too large to inspect comfortably, such as
  an estimated or observed state count above the configured threshold, an
  incomplete budgeted model group, or a model that mixes several unrelated
  functional areas.
- `test_mesh_maintenance`: slow, timeout-prone, background, or release-only
  tests need a parent/child validation evidence plan. Use TestMesh to partition
  the parent test gate into child-suite ownership contracts and to review
  freshness, skipped tests, timeout status, background completion artifacts,
  and routine-vs-release confidence. TestMesh does not run tests; project
  adapters run the suites and pass structured evidence into FlowGuard.
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
- For complex optimizations, repeated bug repairs, stateful refactors, broad
  workflow changes, or model-miss-sensitive work, complete a
  **Pre-Implementation Model Hardening Gate** before production code edits or
  other high-impact actions. Write a concrete change inventory, a risk catalog,
  and a risk-to-model coverage matrix that maps each important planned change
  to possible bugs, modeled state or events, invariants or oracles, known-bad
  hazards, check evidence, and residual blindspots. A happy-path pass is not
  enough: representative bad variants must fail, or the risk must be marked
  out of scope with the production-facing check or human review that covers it.
- Handle expensive project-specific model groups with a tiered evidence policy.
  Run the smallest sufficient model boundary first, launch long checks in the
  background with the standard artifact contract when useful, and record any
  skipped or deferred heavy check with the touched boundary, reason, and
  residual risk. Do not hard-code current-project model names into generic
  skill guidance as always heavy or always skippable. If a heavy model owns the
  state, contract, or risk being changed, run it, shard it, background it with
  completion evidence, or report the remaining blocker instead of silently
  skipping it.
- After the model-hardening gate passes, implement complex work in small
  change slices. Validate each slice with the strongest practical focused
  model, replay, test, or manual check before continuing when practical.
  Preserve user and peer-agent changes; if the workspace changed after earlier
  model or test evidence, treat that evidence as stale unless the model inputs,
  production inputs, and touched files are explicitly unchanged.
- When creating or materially updating a FlowGuard model file, put a short
  **Risk Purpose Header** at the top of the model. The header should name
  FlowGuard and link to `https://github.com/liuyingxuvka/FlowGuard`, then say
  which workflow the model reviews, which concrete bugs or invalid states it
  guards against, when future agents should run or update it, and the companion
  command that runs the checks. Keep it lightweight: do not add manifest files
  or extra project scaffolding unless the task separately requires them.
- Start with the smallest boundary that can expose the current customer risk,
  but do not confuse "smallest useful" with "shortest script" or "template
  only". The model should include enough state, branches, side effects, and
  invariants to simulate the problem the customer wants to catch.
- Treat FlowGuard model scripts as living design artifacts. If no model exists,
  create one. If later work reveals new failure modes, strengthen, extend, or
  connect the model rather than treating the first version as final.
- When a project has three or more local FlowGuard models, or when a single new
  or legacy model is too large, do not trust the model layout as-is. Create or
  update a model mesh: inventory child models, runners, result files, adoption
  logs, evidence tiers, freshness rules, live/conformance adapters, cross-model
  dependencies, skipped/not-run sections, parent partition coverage, sibling
  overlap, state ownership, side-effect ownership, and large-model split
  decisions. The mesh should treat child models as evidence contracts, not
  inline every child state graph. Use `references/model_mesh_protocol.md` for
  the checklist and prompt template.
- A model mesh is required before a broad continue/release/completion claim if
  model results can be stale, if multiple models cover the same workflow from
  different angles, if one model's output is another model's input, if live
  state or conformance evidence can contradict abstract results, or if a
  post-runtime model miss shows that isolated models did not catch the bug
  class. The mesh must make known-bad hazards fail before production work uses
  the plan.
- When tests are too slow or too broad to trust as one flat gate, enter
  `test_mesh_maintenance`. Partition validation by behavior, state, module,
  command, side effect, invariant, or release boundary. Bind every partition to
  a parent, child, read-only, or shared-kernel owner. Record child-suite
  evidence with status, evidence tier, freshness, selected/skipped counts,
  visible skips, timeout, exit code, result path, background artifacts, owned
  state, and owned side effects. Use `references/test_mesh_protocol.md` for the
  checklist and prompt template.
- A TestMesh must make known-bad hazards fail before parent confidence is
  trusted: missing owner, unregistered owner, duplicate partition owner,
  duplicate state or side-effect owner, hidden skipped tests, stale evidence,
  failed or timeout suite, progress-only background run, missing exit/result
  artifact, and missing release-required suite under release scope. Routine
  scope may defer release-only suites only when the report keeps the release
  obligation visible.
- Treat a runtime, test, replay, or manual validation failure that appears after
  a FlowGuard pass as a model-miss review trigger until proven otherwise. Do not
  patch and finish directly: classify why the earlier model missed it using the
  five practical types `boundary_missing`, `state_too_coarse`,
  `input_branch_missing`, `invariant_too_weak`, or `evidence_overclaimed`; if
  the issue belongs in scope, represent the observed issue plus one same-class
  generalized bad case when practical; rerun the relevant model checks; and only
  then validate the repair with production-facing evidence. Do not add a hazard
  registry, upgrade reviewer, default model mesh, full coverage matrix, or
  evidence-level field as a default response to ordinary model misses.
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
- For layered test evidence, use the TestMesh starter when it saves setup time:
  `python -m flowguard test-mesh-template --output .`.
- For recurring Sleep/Dream/Architect/Installer/Reviewer style maintenance
  systems, use the optional maintenance workflow scaffold when it saves setup
  time: `python -m flowguard maintenance-template --output .`.
- For optional spec/SPAC-style planner cooperation, use the upstream handoff
  only as a convenience layer. A valid handoff names the task, planned steps,
  state fields, side effects, parallel ownership, repeat or retry points,
  skipped checks with reasons, and completion evidence. A missing handoff may
  block collaboration mode, but it must not block standalone FlowGuard use.
- Use `FlowGuardCheckPlan` and `run_model_first_checks()` when useful for a
  low-friction agent path. Direct `Explorer(...)` usage remains valid.
- Direct `Explorer(...)` runs emit bounded ten-step progress on `stderr` by
  default, counted by top-level `initial_state x input_sequence` work units.
  Treat this as liveness/observability only, not pass/fail evidence. Use
  `progress_steps=0` or `FLOWGUARD_PROGRESS=0` when a strict environment must
  stay silent.
- For long-running FlowGuard checks launched in the background, default to a
  project-local log root at `tmp/flowguard_background/` unless the repository
  has a stricter convention. For each long check, keep a stable command base
  name and write these artifacts: `<name>.out.txt`, `<name>.err.txt`,
  `<name>.combined.txt`, `<name>.exit.txt`, and `<name>.meta.json`.
- Before reporting a long check as complete, inspect the actual log artifacts
  and report the log root, stdout/stderr/combined paths, exit code, last update
  time, completion status, and whether the result was newly executed or reused
  from a valid proof. Do not treat a path-only report, an in-progress log, or a
  missing exit artifact as completion evidence.
- Distinguish direct Explorer progress from project-specific or legacy custom
  runners. A custom runner that bypasses `Explorer(...)` may only emit a final
  report until it implements its own progress signal. Do not describe final report sections as live progress; final summaries become completion evidence
  only after the exit and log artifacts exist.
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
2. Classify the miss with one of five practical types:
   `boundary_missing`, `state_too_coarse`, `input_branch_missing`,
   `invariant_too_weak`, or `evidence_overclaimed`. Keep unusual details as a
   short note instead of adding more formal daily categories.
3. Represent the issue in executable evidence whenever it belongs in scope:
   add or update a scenario, invariant, replay adapter, representative trace, or
   model boundary note for the observed issue, plus one same-class generalized
   bad case when practical.
4. Confirm the old weakness is now visible: the refined model should catch the
   observed issue and the same-class case, or clearly mark the generalized case
   out of scope before the fix is trusted.
5. Validate the repair through the refined FlowGuard checks plus the strongest
   practical runtime/test/replay evidence.
6. Before finalizing, close or explicitly carry forward the model-miss
   obligation in the adoption note. Record `Miss type: <one of the five>` and
   `Generalized case: <one sentence>` or the reason no generalized case was
   added. A later green runtime check by itself does not close a known model
   miss unless the miss has been reviewed.

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
   `test_mesh_maintenance`, or `process_preflight`.
3. If a spec/SPAC-style planner has already decomposed the task, inspect its
   handoff as optional context. Check for state, side effects, parallel
   ownership, repeat or retry points, skipped checks with reasons, and
   completion evidence. If the planner is absent, continue with standalone
   FlowGuard.
4. If skipping a clearly trivial task, record one sentence explaining why and
   stop the FlowGuard workflow.
5. Verify the real package is importable before modeling in another repository:
   `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
   This prints the artifact schema version, not the GitHub/package release
   version.
6. If import fails, connect the real toolchain or record the task as
   blocked/partial. do not write a temporary mini-framework and claim full
   adoption.
7. Inventory existing local FlowGuard models before trusting prior green
   evidence. If there are three or more, if multiple model boundaries can
   affect the current decision, or if one new or legacy model is too large,
   create or update a model mesh using `references/model_mesh_protocol.md`.
8. If validation itself is the slow or layered boundary, create or update a
   TestMesh using `references/test_mesh_protocol.md`. Distinguish routine and
   release scope before parent test confidence is claimed.
9. Start a brief adoption note or `in_progress` log entry.
10. Write the Risk Intent Brief. If the risk priority is unclear and would
   materially change the model, ask for human review before modeling.
11. For complex optimizations, repeated bug repairs, stateful refactors, broad
    workflow changes, or model-miss-sensitive work, write the
    Pre-Implementation Model Hardening Gate artifacts: a change inventory, a
    risk catalog, and a risk-to-model coverage matrix.
12. In the coverage matrix, map each important planned change to possible bugs,
    modeled state or events, invariants or oracles, representative known-bad
    hazards, check commands or evidence, and residual blindspots. If a risk is
    outside model scope, name the production-facing validation or human review
    that will cover it.
13. Update or extend the model until representative known-bad hazards fail
    before trusting the model for the target bug class. A happy-path pass alone
    is not enough.
14. Classify expensive project-specific model groups by boundary and risk.
    Run the smallest sufficient boundary first. If a heavy model owns the
    touched state, contract, or risk, run it, shard it, background it with
    completion evidence, or report the blocker. If it is not on the touched
    boundary, record the deferred boundary and residual risk instead of naming
    it as universally skippable.
15. Read the modeling protocol and choose a behavior, argument, or decision
    boundary that is small enough to inspect but strong enough to expose the
    customer-relevant risk.
16. If no FlowGuard model exists yet, create one from the current plan or adapt
    `assets/model_template/`. Build or update the model with explicit inputs,
    state, blocks, outputs, reads, writes, idempotency, and invariants.
17. Build the state write inventory for fields used by invariants.
18. Run `run_model_first_checks()` when useful, or run Explorer directly.
19. Inspect counterexamples and revise the model or intended architecture until
    the correct model passes.
20. For FlowGuard/LiveFlowGuard self-upgrades, multi-model mesh upgrades, or
    model-miss triage, inspect the
    full finding ledger before choosing a repair path. Classify each actionable
    finding as real-system repair, check-flow repair, model extension, or
    explicit out-of-scope boundary.
21. Preserve important counterexamples as tests or implementation notes.
22. Edit production code or perform the modeled high-impact action only after
    executable model checks pass, unless the user explicitly waives modeling.
23. For complex optimized work, implement in change slices. After each slice,
    run the relevant focused model, replay, test, or manual validation when
    practical, and preserve user or peer-agent changes. Treat earlier model or
    test evidence as stale when the workspace, model inputs, production inputs,
    or touched files changed.
24. Run scenario review, loop/stuck review, progress checks, contracts, or
    conformance replay when those risks apply.
    If this would repeat an unchanged abstract run that already passed, it may
    be enough to reuse the earlier result and focus post-edit verification on
    tests, conformance replay, or other production-facing evidence.
25. If post-edit runtime validation exposes a new issue after FlowGuard passed,
    enter Post-Runtime Model-Miss Review before claiming completion.
26. Finish the adoption note with the checks run, findings, skipped checks, and
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
- `references/test_mesh_protocol.md`: trigger, partition checklist, evidence
  checklist, prompt template, and completion standard for layered test
  validation.
- Repository-level `docs/skill_orchestrator_collaboration.md`: optional
  spec/SPAC-style planner handoff contract and collaboration hazards.
- `python -m flowguard project-template --output .`: basic public starter
  model.
- `python -m flowguard risk-intent-template --output .`: Risk Intent +
  CheckPlan starter.
- `python -m flowguard model-miss-template --output .`: post-runtime
  model-miss review starter.
- `python -m flowguard test-mesh-template --output .`: layered test evidence
  starter.
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
