# Engineering Hardening

FlowGuard ships thin adoption surfaces around the existing Python API. The goal
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

## Command Line And Python Entry Points

The command line is intentionally small. Day to day it is:

```powershell
python -m flowguard read
python -m flowguard change
python -m flowguard release
python -m flowguard template --list
python -m flowguard map <scan|discover|digest|deps|check|lint|impact|models|confirm>
```

`python -m flowguard map models` runs the executable models bound in
`.flowguard/map.json`; every call executes them (results are never cached). The older review
helpers are Python APIs, not separate commands:

- `review_scenarios()` for expected-vs-observed scenario review;
- `check_loops()` for stuck-loop and non-terminating component review;
- `replay_trace()` and `default_conformance_rules()` for conformance replay;
- `build_benchmark_scorecard()` and `build_benchmark_coverage_audit()` for
  the executable problem corpus;
- `flowguard.SCHEMA_VERSION` for the artifact schema version.

None of these should hide expected-vs-observed statuses, `needs_human_review`,
or known limitations.

The wheel carries the maintained `examples` packages that the models and tests
import. A consumer check must execute at least one real model or check; a
successful `--help` or package import is only an entry point smoke check and
does not prove that the runtime dependencies are installed.

## Templates

The package exposes public-safe scaffolds for common agent situations:

- `risk_intent_template_files()`: a Risk Intent + `FlowGuardCheckPlan`
  starter with model-level confidence boundaries;
- `model_miss_review_template_files()`: a bug-repair/model-miss review starter
  for non-trivial bug repairs or cases where real validation finds a gap after
  a FlowGuard pass;
- `model_test_alignment_template_files()`: a direct model-obligation to
  ordinary test-evidence alignment starter;
- `maintenance_workflow_template_files()`: a recurring maintenance workflow
  starter.

The helpers return content instead of writing files so callers can decide where
and how to create project files. The CLI can print or write the same templates
(`python -m flowguard template --list` shows every name):

```powershell
python -m flowguard template risk-intent --write .
python -m flowguard template model-miss-review --write .
python -m flowguard template model-test-alignment --write .
python -m flowguard template maintenance-workflow --write .
```

Without `--write` the files are printed; `--force` overwrites existing files.
