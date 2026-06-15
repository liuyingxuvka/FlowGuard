# Explorer Progress Heartbeat Rollout Plan

This document is the working checklist for adding minimal progress visibility to
long-running FlowGuard Explorer runs.

## Optimization Checklist

| Order | Optimization item | Implementation boundary | Done when |
| --- | --- | --- | --- |
| 1 | Add default ten-step progress to the core `Explorer` path. | `flowguard/explorer.py` only. Count top-level work as `initial_state x input_sequence`. | Existing `Explorer(...).explore()` calls emit start and progress lines without requiring caller changes. |
| 2 | Keep the run serial. | Do not add worker pools, subprocess runners, or parallel merge logic. | The exploration order and report content remain deterministic. |
| 3 | Emit progress to `stderr`, not `stdout`. | Use the standard error stream for human/agent progress. | Existing scripts that read final reports from `stdout` keep working. |
| 4 | Add the smallest compatibility controls. | Add `progress_steps=10` by default, `progress_steps=0` to disable, and `FLOWGUARD_PROGRESS=0` as a process-level opt-out. | Old callers remain valid, and strict CI can silence progress. |
| 5 | Let `run_model_first_checks()` inherit core behavior. | Do not add duplicate progress logic to `flowguard/runner.py`. | Runner calls show Explorer progress through the same core path. |
| 6 | Update templates and docs by reference, not by copying logic. | Keep generated templates on `run_model_first_checks(...)` so they inherit core Explorer progress through the formal runner. | New templates rely on the core feature instead of writing their own progress loop. |
| 7 | Add focused regression tests before broad release checks. | Unit-test progress buckets, stream routing, opt-out, and report stability. | The behavior is covered without depending on long-running models. |
| 8 | Publish as a source-only patch release. | Version, changelog, local install, shadow workspace sync, tag, and GitHub Release. | README-visible version, `pyproject.toml`, git tag, and GitHub Release align. |

## Bug-Risk Checklist

| Risk | Bug shape to catch before coding | Guard in the FlowGuard model | Production-facing test |
| --- | --- | --- | --- |
| R1 | The plan adds progress outside core Explorer, so old models do not benefit. | Require `core_explorer_changed` and reject `template_only_progress`. | Existing no-argument `Explorer(...).explore()` emits progress. |
| R2 | Progress pollutes `stdout` and breaks JSON/report pipelines. | Require `progress_stream == stderr`. | Capture `stdout` and `stderr`; progress appears only in `stderr`. |
| R3 | Progress emits on every sequence for large models, causing noisy slow logs. | Require bounded ten-step output and reject `per_sequence_output`. | A 100-sequence run emits at most start plus ten progress lines. |
| R4 | Small models emit no useful progress. | Require small totals to emit at least one progress line and final `100%`. | A tiny run still reaches `100%`. |
| R5 | Threshold rounding skips or duplicates progress buckets. | Require monotonic unique progress buckets ending at `100%`. | Tests cover non-divisible totals. |
| R6 | The feature changes pass/fail semantics or trace collection. | Require `report_semantics_unchanged`. | Existing invariant report tests still pass and report fields stay stable. |
| R7 | Users cannot disable progress in strict environments. | Require API and environment opt-out. | `progress_steps=0` and `FLOWGUARD_PROGRESS=0` produce no progress. |
| R8 | Runner gains a second inconsistent progress implementation. | Require `runner_inherits_core` and reject duplicate runner progress. | `run_model_first_checks()` still delegates to Explorer without custom progress code. |
| R9 | Templates copy progress code and drift from the core implementation. | Require templates to inherit progress through `run_model_first_checks(...)` without custom progress loops. | Template tests still execute and contain no custom progress loop. |
| R10 | Release claims completion without local install/shadow workspace sync. | Require release sync checks before publication. | Install check and any shadow workspace focused checks pass before GitHub release. |

## Scope Boundaries

- No parallel Explorer execution in this release.
- No timeout budget, watchdog, subprocess runner, partial report status, JSONL
  event protocol, dashboard, or progress UI in this release.
- The progress output is observability only. It must not be used as pass/fail
  evidence, and skipped or incomplete checks remain separate concerns.
