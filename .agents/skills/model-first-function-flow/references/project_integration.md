# Project Integration

Before using this skill in another repository, verify that the real
`flowguard` package is available:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

If that fails, do not write a temporary mini-framework and claim the project is
using FlowGuard. Connect the real toolchain first.

If you have a local checkout, use an explicit source path:

```powershell
$env:FLOWGUARD_SOURCE = "<path-to-your-FlowGuard-checkout>"
python -m pip install -e $env:FLOWGUARD_SOURCE
```

Use the normal editable install command in a fresh virtual environment so `pip`
can prepare the build backend declared in `pyproject.toml`.

Then verify:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
python -m flowguard schema-version
```

Toolchain helper:

```powershell
python <path-to-model-first-function-flow-skill>\assets\toolchain_preflight.py --source <path-to-your-FlowGuard-checkout> --json
python <path-to-model-first-function-flow-skill>\assets\toolchain_preflight.py --source <path-to-your-FlowGuard-checkout> --install-editable --json
```

Use the helper when the target Python environment cannot import FlowGuard and
you want the Skill to discover the local source tree and print the supported
install or `PYTHONPATH` command. The helper is standard-library-only.
If it reports `mode: pythonpath_available`, run one of the recommended commands
before treating the target environment as connected.

Temporary fallback for pilots:

```powershell
$env:PYTHONPATH = "<path-to-your-FlowGuard-checkout>;$env:PYTHONPATH"
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

Record the chosen integration path in the adoption log. If the real toolchain
cannot be connected, record the task as blocked or partial rather than as a
passed FlowGuard check.

When the target environment can run `python -m flowguard`, prefer the
low-friction adoption CLI for start and finish entries:

```powershell
python -m flowguard adoption-start --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>"
python -m flowguard adoption-finish --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>" --command "<check command>"
```

The CLI appends `.flowguard/adoption_log.jsonl` and
`docs/flowguard_adoption_log.md`. It reduces logging friction but does not
replace executable checks.
