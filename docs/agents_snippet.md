# AGENTS.md Snippet: Model-First Function Flow

Copy this section into another repository's `AGENTS.md`.

```markdown
## Model-first function flow

For coding and repository work, first make a lightweight FlowGuard applicability decision: `use_flowguard`, `skip_with_reason`, or `needs_human_review`. For non-trivial tasks involving behavior, workflows, state, module boundaries, retries, deduplication, idempotency, caching, repeated inputs, production conformance, or repeated bugs, use the model-first-function-flow skill before editing production code. Build or update a flowguard model, run checks, inspect counterexamples, and only then implement production code.

Rules:

- Start each coding or repository task by deciding whether FlowGuard applies.
- Use `use_flowguard` when the task may affect behavior, state, workflow, retries, deduplication, idempotency, caching, side effects, module boundaries, queue/reprocessing behavior, or production conformance.
- Use `skip_with_reason` only for clearly trivial copy edits, formatting-only changes, read-only explanation, or work with no behavior/state impact.
- Use `needs_human_review` or narrow the task when the behavior boundary is unclear.
- Before creating model files, verify that the real flowguard package is importable with `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`. This prints the artifact schema version, not the GitHub/package release version.
- If flowguard is not importable, connect the real toolchain first, such as by editable install from the local FlowGuard source tree, or record the task as `blocked`. Do not hand-write a temporary mini-framework and claim full flowguard adoption.
- When available, use the Skill helper `assets/toolchain_preflight.py --json` to discover the editable install or `PYTHONPATH` command for the active Python environment.
- Do not edit production code first.
- Treat the FlowGuard model as a falsifiable simulator of the real workflow, not as ground truth. Compare representative traces with real code paths, logs, tests, known user workflows, or conformance replay before trusting the model result.
- Calibrate model fidelity to the current risk. If a trace is impossible, suspicious, or misses known behavior, refine the model, scenario oracle, or replay adapter and rerun the checks.
- Represent each function block as `Input x State -> Set(Output x State)`.
- Define finite external inputs and immutable abstract state.
- Define possible outputs, state reads, state writes, idempotency rules, and hard invariants.
- Before trusting an invariant over a state field, make a state write inventory: search for every production writer of fields such as `recommendation_status`, `output_status`, `analysis_json`, cache values, queue status, retry counters, and side-effect records. Record modeled writers and skipped writers with reasons.
- Run flowguard with repeated-input exploration when duplicate side effects are possible.
- Run scenario review, conformance replay, loop/stuck review, progress/fairness checks, and contract checks when those risks apply.
- Default to a small conformance replay when production logic has multiple state write points, database side effects, runtime/cleanup/finalizer paths, or production-confidence claims. If replay is skipped, record why; skipped is not pass.
- Treat UI state-flow, product architecture, orchestration, and module-boundary changes as model-first unless they are clearly trivial.
- Trivial copy edits, formatting-only work, and read-only explanation tasks may skip flowguard with an explicit reason.
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
```
