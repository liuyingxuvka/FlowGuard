# AGENTS.md Snippet: Model-First Function Flow

Copy this section into another repository's `AGENTS.md`.

```markdown
## Model-first function flow

For coding, repository, process-design work, structured writing/argument, and decision/planning work, first make a lightweight FlowGuard applicability decision: `use_flowguard`, `skip_with_reason`, or `needs_human_review`. For non-trivial tasks involving behavior, workflows, state, module boundaries, retries, deduplication, idempotency, caching, repeated inputs, production conformance, repeated bugs, multiple local FlowGuard models, meaningful process validation/adjustment/observation with side effects, argument chains with prerequisite claims, or decision paths with assumptions and commitments, use the model-first-function-flow skill before editing production code, performing the high-impact action, relying on the argument, or locking in the decision. Build or update a flowguard model, run checks, inspect counterexamples, and only then implement production code, act on the process, use the argument, or commit to the decision. If no FlowGuard model exists yet, create one from the current plan or adapt the included model template; the model should be strong enough to capture the customer's relevant risks and should evolve as new risks appear.

Rules:

- Start each coding, repository, or process-design task by deciding whether FlowGuard applies.
- Use `use_flowguard` when the task may affect behavior, state, workflow, retries, deduplication, idempotency, caching, side effects, module boundaries, queue/reprocessing behavior, production conformance, external process dependencies, rollback concerns, costly/irreversible process actions, argument prerequisites, evidence/proof dependencies, decision assumptions, or commitments.
- When FlowGuard applies, classify the main lens as `behavior_flow`, `argument_flow`, or `decision_flow`. This lens guides the state fields and invariants; it does not replace the existing project, Risk Intent, model-miss, or maintenance templates.
- Use `skip_with_reason` only for clearly trivial copy edits, formatting-only changes, read-only explanation, or work with no behavior/state impact.
- Use `needs_human_review` or narrow the task when the behavior boundary is unclear.
- If a spec/SPAC-style planning or orchestration skill has already decomposed
  the task, treat its plan as optional handoff context. Check that the handoff
  names planned steps, state fields, side effects, parallel ownership, repeat
  or retry points, skipped checks with reasons, and completion evidence. If the
  planner is absent, continue with standalone FlowGuard; no external planning
  skill is a FlowGuard prerequisite.
- Before creating model files, verify that the real flowguard package is importable with `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`. This prints the artifact schema version, not the GitHub/package release version.
- If flowguard is not importable, connect the real toolchain first, such as by editable install from the local FlowGuard source tree, or record the task as `blocked`. Do not hand-write a temporary mini-framework and claim full flowguard adoption.
- When available, use the Skill helper `assets/toolchain_preflight.py --json` to discover the editable install or `PYTHONPATH` command for the active Python environment.
- Do not edit production code or perform the modeled high-impact action first.
- If no FlowGuard model script exists yet, create one. Existing production code
  is not required; the model script is the executable design artifact the AI
  creates before action.
- When creating or materially updating a FlowGuard model file, put a short
  **Risk Purpose Header** at the top of the model. The header should name
  FlowGuard and link to `https://github.com/liuyingxuvka/FlowGuard`, then say
  which workflow the model reviews, which concrete bugs or invalid states it
  guards against, when future agents should run or update it, and the companion
  command that runs the checks. Keep it lightweight: do not add manifest files
  or extra project scaffolding unless the task separately requires them.
- Do not force every adoption into the shortest possible script. Start with the
  smallest inspectable boundary that can expose the current risk, then add
  state, branches, retries, side effects, or invariants when the customer's
  failure mode would otherwise be invisible.
- Treat models as living artifacts. When future tasks expose new failure modes,
  strengthen, extend, or connect the model instead of assuming the first version
  is final.
- If the project has three or more local FlowGuard models, create or update a
  local model mesh before broad continue, release, completion, or
  production-confidence claims. The mesh is a model-of-models: inventory child
  models, evidence tiers, freshness rules, live/conformance adapters,
  cross-model dependencies, skipped/not-run sections, and blindspots. Do not
  inline every child state graph unless a specific contradiction needs a narrow
  adapter.
- The model mesh must make known-bad hazards fail: abstract-only permission,
  hidden skipped live/replay checks, stale result reuse, unregistered model
  evidence, cross-model contradictions, hidden blockers, missing conformance,
  unrepresented model misses, sealed/private body reads, stale installed
  skill/source copies, oversized mesh expansion, and absence of a mesh when the
  three-model threshold is met.
- Treat runtime, test, replay, or manual validation failures after a FlowGuard
  pass as model-miss review triggers until proven otherwise. Do not patch and
  finish directly: classify why the earlier model missed the issue, represent
  the issue in FlowGuard as a scenario, invariant, replay, representative trace,
  or explicit out-of-scope boundary, rerun the relevant checks, and then
  validate the repair with production-facing evidence.
- For FlowGuard or LiveFlowGuard framework upgrades, live failure triage, or
  broad capability claims, build a full finding ledger first: invariant/model
  checks, model-quality audit, scenario or live-audit evidence, progress,
  contracts, conformance, skipped/not-run sections, and adoption evidence.
  Use that ledger to choose whether to fix the real system, adjust the check
  flow, extend the model, or mark a boundary out of scope. Do not default to a
  point-rule patch for the first visible failure.
- Treat the FlowGuard model as a falsifiable simulator of the real workflow, not as ground truth. Compare representative traces with real code paths, logs, tests, known user workflows, or conformance replay before trusting the model result.
- Calibrate model fidelity to the current risk. If a trace is impossible, suspicious, or misses known behavior, refine the model, scenario oracle, or replay adapter and rerun the checks.
- Represent each function block as `Input x State -> Set(Output x State)`.
- Define finite external inputs and immutable abstract state.
- Define possible outputs, state reads, state writes, idempotency rules, and hard invariants.
- For non-code process models, name real-world state and side effects explicitly: approvals, confirmations, reservations, payments, published artifacts, user commitments, vendor dependencies, deadlines, cancellation windows, and rollback options.
- For `behavior_flow`, model phases, completed steps, persisted records, side effects, retries, terminal status, and rollback state; check prerequisite order, duplicate side effects, failure-to-success mistakes, illegal terminal mutations, and stuck states.
- For `argument_flow`, model reader and argument state: introduced context, defined terms, declared assumptions, cited evidence, proved claims, referenced figures, and allowed conclusions; check definition-before-use, support-before-claim, no overbroad conclusions, and no circular dependencies.
- For `decision_flow`, model goals, constraints, assumptions, evidence, options considered, tradeoffs recorded, commitments made, irreversible steps, and changed conditions; check that choices wait for goals/constraints, commitments wait for required checks, changed conditions trigger re-evaluation, and rejected options need new evidence before returning.
- Before trusting an invariant over a state field, make a state write inventory: search for every production writer of fields such as `recommendation_status`, `output_status`, `analysis_json`, cache values, queue status, retry counters, and side-effect records. Record modeled writers and skipped writers with reasons.
- Run flowguard with repeated-input exploration when duplicate side effects are possible.
- Run scenario review, conformance replay, loop/stuck review, progress/fairness checks, and contract checks when those risks apply.
- Default to a small conformance replay when production logic has multiple state write points, database side effects, runtime/cleanup/finalizer paths, or production-confidence claims. If replay is skipped, record why; skipped is not pass.
- Keep FlowGuard pass evidence provisional until runtime validation and any
  model-miss review obligation are closed. A later green runtime check by itself
  does not close a known post-FlowGuard model miss unless the miss has been
  classified and represented or explicitly marked out of scope.
- Treat UI state-flow, product architecture, orchestration, and module-boundary changes as model-first unless they are clearly trivial.
- Treat booking, purchase, publication handoff, operational runbook, data migration, support escalation, and multi-agent coordination flows as model-first when they have meaningful state, side effects, external dependencies, rollback concerns, or irreversible cost.
- Trivial copy edits, formatting-only work, read-only explanation tasks, and fully reversible process steps with no meaningful state or side effects may skip flowguard with an explicit reason.
- If the task boundary is unclear, mark it as `needs_human_review` or narrow the scope before deciding to skip or model.
- Treat zero-result and non-consumable branches as reportable failures unless they are explicitly modeled as terminal.
- Preserve expected-vs-observed status categories; do not hide `needs_human_review`, known limitations, or counterexamples.
- When FlowGuard is used, finish with a short adoption note in the project log. Do not treat the task as complete until the note exists.
- Keep the note plain and useful: why FlowGuard was used or skipped, what workflow or risk was modeled, what checks ran, what FlowGuard found, what was skipped, and what should happen next.
- If there was a counterexample, preserve the important label or one-sentence trace summary. If a check was skipped, say why.
- The note can live in `.flowguard/adoption_log.jsonl`, `docs/flowguard_adoption_log.md`, or the existing project log. The `python -m flowguard adoption-start ...` and `python -m flowguard adoption-finish ...` commands can help create it, but CLI output is not a substitute for the short human-readable note when the model found something important.
- Do not treat skipped flowguard steps as passed checks.
- Do not call LLM APIs, databases, network services, clocks, random sources, Monte Carlo samplers, or external packages from the model.
- Do not weaken hard invariants merely to pass checks.
- Do not replace executable modeling with prose.
- Treat non-code process models as risk-discovery preflights, not proof that real-world facts, prices, availability, policies, or vendor behavior are safe.
```
