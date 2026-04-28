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
python -m pip install -e $env:FLOWGUARD_SOURCE --no-deps --no-build-isolation
```

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

Temporary fallback for pilots:

```powershell
$env:PYTHONPATH = "<path-to-your-FlowGuard-checkout>;$env:PYTHONPATH"
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

Record the chosen integration path in the adoption log. If the real toolchain
cannot be connected, record the task as blocked or partial rather than as a
passed FlowGuard check.
