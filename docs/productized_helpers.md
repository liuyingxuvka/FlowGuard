# Productized Helper Layer

FlowGuard's core remains small:

```text
State + FunctionBlock + Invariant + Explorer
FunctionBlock: Input x State -> Set(Output x State)
Explorer: deterministic finite exploration
```

The helper layer exists to make that path easier for AI coding agents. It should
not become a mandatory checklist or a second formal system.

For the full public API layer map, see `docs/api_surface.md`. The exported
`API_SURFACE` grouping is descriptive only; it does not turn helpers, reports,
or internal evidence tools into required steps.

## Standard Property Factories

Use these when they match a common bug class:

- `no_duplicate_by(...)`: selected items are unique by key.
- `at_most_once_by(...)`: attempts, events, or side effects happen at most once per key.
- `all_items_have_source(...)`: downstream items trace to upstream source items.
- `no_contradictory_values(...)`: one key cannot accumulate mutually exclusive values.
- `cache_matches_source(...)`: cache entries agree with source-of-truth values.
- `only_named_block_writes(...)`: one state field is written only by its owner block.
- `require_label_order(...)`: one trace label appears before another.
- `forbid_label_after(...)`: a later forbidden label does not appear after an anchor label.

Each factory returns an ordinary `Invariant`. Failure messages include the
specific duplicate keys, missing source keys, contradictory values, mismatches,
unauthorized writes, or label positions, plus structured metadata for reports.
Factories also attach lightweight `property_classes` metadata, such as
`deduplication`, `at_most_once`, or `cache_consistency`. `audit_model(...)`
uses these tags before falling back to name/description heuristics, so custom
names do not have to include words like "duplicate" or "cache" to be recognized.

Custom invariants may add the same optional metadata directly:

```python
Invariant(
    "job_records_are_valid",
    "records have the expected domain shape",
    check_records,
    metadata={"property_classes": ("deduplication",)},
)
```

The metadata is helper information only. It is optional, unknown values are not
hard failures, and older `Invariant(name, description, predicate)` usage remains
valid.

## Counterexample Minimization

Use `minimize_failing_sequence(...)` after a violation when the failing input
sequence is longer than needed. The algorithm is deterministic and only tries
to delete inputs or contiguous chunks. It does not use random shrinking,
Hypothesis, SMT, LTL, probability, or an LLM API.

The returned `MinimizedCounterexample` keeps both:

- `original_sequence`
- `minimized_sequence`

If no shorter sequence preserves the failure, the status is
`no_reduction_found`.

## Model Quality Audit

Use `audit_model(...)` to expose obvious coverage gaps:

- missing repeated-input exploration for retry/dedup/idempotency risks;
- missing invariants;
- missing scenarios;
- missing cache consistency checks for cache risks;
- missing duplicate/idempotency checks for side-effect risks;
- missing progress checks for retry/queue/loop/waiting risks;
- conformance replay not run;
- skipped checks.

Severity rules:

- `error`: the model structure is unusable, such as a workflow with no blocks.
- `warning`: the model can run, but coverage or confidence has a gap.
- `suggestion`: useful improvement, but not a current check failure.

Warnings are not automatic failures. They define the boundary of what the model
has and has not checked. Skipped is not pass.

`audit_model(...)` can also consume a `RiskProfile`. RiskProfile risk classes
make the audit more targeted, for example warning about missing repeated-input
coverage for retry/deduplication risks or missing conformance evidence for a
`production_conformance` confidence goal. Unknown risk classes are recorded as
warnings rather than rejected.

## Adoption Evidence Audit

Use `audit_flowguard_adoption(root)` for read-only checks of existing
FlowGuard adoption evidence. It scans `.flowguard` Python files for stale
fallback markers such as `flowguard_package_available = False`, fallback
explorer comments, or local replacement `Explorer`/`Workflow` classes.

If the real package is importable but a current model still appears to use a
fallback, the report emits `stale_fallback_model` as a warning. Historical
fallback mentions in old logs are kept visible as suggestions. These findings
do not make the model fail by themselves; they prevent overclaiming current
FlowGuard adoption from stale evidence.

For low-friction logging, the CLI can append start and finish entries:

```powershell
python -m flowguard adoption-start --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>"
python -m flowguard adoption-finish --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>" --command "<check command>"
```

The start command records `in_progress`; the finish command appends the final
entry. This is a reporting helper only. It does not replace model checks,
scenario review, conformance replay, or test execution.

## Scenario Matrix Builder

`ScenarioMatrixBuilder` scaffolds a small deterministic scenario set:

- single input: `[A]`, `[B]`
- repeated same input: `[A, A]`, `[B, B]`
- pairwise order: `[A, B]`, `[B, A]`
- ABA: `[A, B, A]`, `[B, A, B]`

Generated scenarios default to `needs_human_review`. They cover useful input
shapes, such as repeats and order swaps, but they are not business oracles. Add
explicit domain expectations before treating them as pass/fail evidence.

## Unified Summary Report

`FlowGuardSummaryReport` combines optional sections such as model check, audit,
scenario review, progress, contract, conformance, and not-run/skipped checks.

Status rules:

- Any invariant violation, dead branch, exception, contract failure, progress
  failure, scenario mismatch, or conformance failure should make the relevant
  section `failed`.
- If Explorer passes but audit has warnings, overall status is
  `pass_with_gaps`.
- A `not_run` or `skipped_with_reason` conformance section is a confidence gap,
  not a hard failure and not a pass.

Use the summary in PR notes or agent replies to avoid overstating "FlowGuard
passed" when only the model checker ran.

## Mermaid Source Export

Mermaid export is an explicit reporting helper for situations where a diagram
will make a trace, counterexample, or reachable state graph easier to inspect.
It returns text source that can be copied into Markdown, GitHub, docs tooling,
or another renderer. It does not produce PNG-only output and does not change
default `format_text()` reports.

Available helpers:

- `trace_to_mermaid_text(trace)`: one representative model trace.
- `graph_to_mermaid_text(edges, states=..., initial_states=...)`: a generic
  state graph from `GraphEdge`-like objects.
- `loop_report_to_mermaid_text(report)`: the reachable graph from a
  `LoopCheckReport`.
- `mermaid_code_block(source)`: wrap source in a Markdown Mermaid fence.

Use this when the user asks for a diagram, when a counterexample needs visual
explanation, or when a loop/stuck-state review is easier to discuss as a graph.
For routine checks, prefer the normal text or JSON reports.

Run `python examples/mermaid_export_example.py` for a minimal end-to-end
example that prints a Markdown Mermaid code block.

## Runner and Domain Packs

`RiskProfile`, `FlowGuardCheckPlan`, and `run_model_first_checks(...)` provide
a low-friction path for AI agents:

1. Start with the smallest useful model.
2. Declare the intended risk boundary in `RiskProfile`.
3. Use property factories or domain packs when they fit.
4. Run `run_model_first_checks(...)`.
5. Inspect minimized counterexamples when present.
6. Treat `pass_with_gaps` as useful but limited confidence.

The runner is orchestration, not a new core checker. It calls existing helpers
and keeps direct `Explorer` use valid.

Domain packs are small recipes:

- `DeduplicationPack`
- `CachePack`
- `RetryPack`
- `SideEffectPack`

They produce optional invariants and scenario scaffolds from selectors and key
functions supplied by the user or agent. They do not infer production code, add
hidden requirements, or replace explicit domain modeling.

## Maintenance Workflow Template

Use the optional maintenance workflow template for recurring multi-role agent
systems such as Sleep/Dream/Architect/Installer/Reviewer flows:

```powershell
python -m flowguard maintenance-template --output .
```

The scaffold writes:

- `.flowguard/maintenance_workflow/model.py`
- `.flowguard/maintenance_workflow/run_checks.py`
- `docs/flowguard_maintenance_workflow.md`

The template models common maintenance failure modes:

- duplicate actions on repeated maintenance runs;
- a task marked completed without an architect/reviewer report;
- publishing before install/runtime synchronization;
- adoption evidence replacing executable checks.

It is a scaffold. Rename the roles and state fields to match the project, and
delete or extend checks that do not fit. It is not a required layer for ordinary
FlowGuard models.
