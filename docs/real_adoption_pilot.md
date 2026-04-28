# Real Adoption Pilot

FlowGuard is intended to be used before production code changes, not only as an
example repository. A real adoption pilot should be small, explicit, and
reviewable.

## Trigger

Use FlowGuard when a task involves:

- non-trivial behavior;
- workflow changes;
- state transitions;
- retries;
- caching;
- deduplication;
- idempotency;
- side effects;
- module boundaries;
- repeated bugs.

Trivial copy edits, formatting-only changes, and read-only explanations may
skip FlowGuard, but the skip should be recorded when an adoption log is kept.

## Toolchain Preflight

Before using FlowGuard in another repository, verify that the real package is
importable:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

If the import fails, connect the real package with an editable install or
temporary `PYTHONPATH`. Do not replace FlowGuard with a hand-written mini
framework and mark the task as fully checked.

## Adoption Log

`flowguard.adoption` provides structured log objects:

- `.flowguard/adoption_log.jsonl` for machine-readable entries;
- `docs/flowguard_adoption_log.md` for a human-readable running log.

An adoption entry should record:

- why FlowGuard was triggered;
- model files;
- commands run;
- findings;
- counterexamples;
- skipped steps;
- friction points;
- next actions;
- status.

Use one of these statuses:

- `in_progress`;
- `completed`;
- `blocked`;
- `skipped_with_reason`;
- `failed`.

Only `completed` means the model-first work finished successfully. A skipped
conformance replay, loop check, or contract check is not a pass unless that
step truly does not apply and the reason is recorded.

## Minimal Logging Example

```python
from flowguard.adoption import (
    AdoptionCommandResult,
    append_jsonl,
    append_markdown_log,
    make_adoption_log_entry,
)

entry = make_adoption_log_entry(
    task_id="architecture-change-001",
    project="target-project",
    task_summary="Review retry and deduplication workflow",
    trigger_reason="Task changes retry handling and side effects",
    status="completed",
    model_files=("flowguard_model/model.py", "flowguard_model/scenarios.py"),
    commands=(
        AdoptionCommandResult(
            "python flowguard_model/run_checks.py",
            True,
            summary="scenario review passed",
        ),
    ),
    findings=("repeated input uses idempotency key",),
    counterexamples=(),
    friction_points=(),
    skipped_steps=(),
    next_actions=("implement production change after model passes",),
)

append_jsonl(".flowguard/adoption_log.jsonl", entry)
append_markdown_log("docs/flowguard_adoption_log.md", entry)
```

## What Successful Adoption Means

A successful adoption entry does not mean the production system is completely
correct. It means:

- the intended behavior was modeled;
- relevant deterministic checks were run;
- counterexamples were inspected;
- skipped steps were explicit;
- the result is reviewable by a future agent or maintainer.

