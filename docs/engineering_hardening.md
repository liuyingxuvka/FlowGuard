# Engineering Hardening

Phase 15 adds thin adoption surfaces around the existing Python API. The goal
is to make proven checks easier to run without changing the mathematical core.

## Stable Artifacts

`flowguard.schema` wraps traces and reports in a deterministic envelope:

- `schema_version`;
- `artifact_type`;
- `created_by`;
- `model_name`;
- `scenario_name`;
- `trace_id`;
- `payload`.

Use `trace_artifact()` and `report_artifact()` when a trace or report needs to
be saved or compared as a stable machine-readable artifact.

## Command Wrappers

`python -m flowguard` provides thin wrappers around existing Python APIs:

```powershell
python -m flowguard benchmark
python -m flowguard coverage
python -m flowguard hardening
python -m flowguard loop-review
python -m flowguard scenario-review
python -m flowguard conformance
python -m flowguard schema-version
```

The CLI is intentionally small. It should not hide expected-vs-observed
statuses, `needs_human_review`, or known limitations.

## Templates

`flowguard.templates.project_template_files()` returns starter files for a
basic model-first workflow:

- `model.py`;
- `run_checks.py`.

The package also exposes public-safe scaffolds for common agent situations:

- `risk_intent_template_files()`: a Risk Intent + `FlowGuardCheckPlan`
  starter with model-level confidence boundaries;
- `model_miss_review_template_files()`: a post-runtime model-miss review
  starter for cases where real validation finds a gap after a FlowGuard pass;
- `maintenance_workflow_template_files()`: a recurring maintenance workflow
  starter.

The helpers return content instead of writing files so callers can decide where
and how to create project files. The CLI can print or write the same templates:

```powershell
python -m flowguard project-template --output .
python -m flowguard risk-intent-template --output .
python -m flowguard model-miss-template --output .
python -m flowguard maintenance-template --output .
```

## Pytest Adapter

`flowguard.pytest_adapter` exposes assertion helpers without importing pytest:

- `assert_report_ok(report)`;
- `assert_no_executable_corpus_regression(report)`.

These helpers let projects integrate flowguard checks into pytest while keeping
the core package free of external dependencies.

## Adoption Logging

Phase 16 adds `flowguard.adoption` as a lightweight record layer for real
project pilots:

- `AdoptionCommandResult`;
- `AdoptionLogEntry`;
- `AdoptionTimer`;
- `append_jsonl()`;
- `append_markdown_log()`.

Use `.flowguard/adoption_log.jsonl` for machine-readable entries and
`docs/flowguard_adoption_log.md` for a human-readable project log. The log
should record status, trigger reason, elapsed time, files touched, checks run,
findings, counterexamples, skipped steps, friction, and next actions.

Logging does not replace executable checks. It exists so repeated real use can
show where flowguard is useful, where it is slow, and where the workflow needs
better templates or math.

Adoption status should be one of `in_progress`, `completed`, `blocked`,
`skipped_with_reason`, or `failed`. Only `completed` means the adoption evidence
is final and successful.
