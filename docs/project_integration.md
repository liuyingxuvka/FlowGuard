# Project Integration

This document explains how a target repository should connect to the real
`flowguard` toolchain before using the `model-first-function-flow` skill.

## Preflight

Before modeling in another repository, run:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

If this fails, do not create a temporary local mini-framework and claim the
project used FlowGuard. Connect the real toolchain first, or record the task as
blocked or partial.

## Local Source Install

If you have a local checkout of this repository, set an explicit source path:

```powershell
$env:FLOWGUARD_SOURCE = "<path-to-your-FlowGuard-checkout>"
python -m pip install -e $env:FLOWGUARD_SOURCE
```

The normal editable install command is intentional. It works in a fresh virtual
environment because `pip` can prepare the standard build backend declared in
`pyproject.toml`.

Then verify:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
python -m flowguard schema-version
```

## Toolchain Preflight Helper

The Skill includes a standard-library helper for active Python environments
that cannot import FlowGuard yet:

```powershell
python <path-to-model-first-function-flow-skill>\assets\toolchain_preflight.py --json
```

If the helper reports `mode: pythonpath_available`, the source tree is usable
but the active environment has not been permanently connected yet. Run one of
the recommended commands before treating the adoption as complete.

To point the helper at a local source tree:

```powershell
python <path-to-model-first-function-flow-skill>\assets\toolchain_preflight.py --source <path-to-your-FlowGuard-checkout> --json
```

To let it install the source tree in editable mode:

```powershell
python <path-to-model-first-function-flow-skill>\assets\toolchain_preflight.py --source <path-to-your-FlowGuard-checkout> --install-editable --json
```

The helper does not replace the import preflight. After it succeeds, still run:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

## Temporary PYTHONPATH Fallback

If editable install is not appropriate, use a temporary `PYTHONPATH` while
running checks:

```powershell
$env:PYTHONPATH = "<path-to-your-FlowGuard-checkout>;$env:PYTHONPATH"
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

This is acceptable for a quick pilot, but the adoption log should record that
the toolchain was connected through `PYTHONPATH`.

## What Not To Do

Do not:

- copy only a few FlowGuard concepts into the target repository and call it
  FlowGuard;
- write a one-off mini framework and mark the task as fully checked;
- hide import failures behind prose;
- treat a skipped install as a passed model-first check.

If a temporary model was created because `flowguard` was not available, record
that as:

```text
skill_decision: blocked_or_partial
status: blocked
friction: flowguard package was not connected to this repository
next_action: install flowguard editable or add an explicit integration path
```

## Project AGENTS.md

After connecting the package, add the rule from `docs/agents_snippet.md` to the
target project's `AGENTS.md`.

That project rule should require:

- `flowguard` import preflight;
- model-first checks before production edits;
- adoption log entries for real use;
- explicit blocked status when the real toolchain is unavailable.

When `python -m flowguard` is available, the lightweight adoption CLI can reduce
manual log drift:

```powershell
python -m flowguard adoption-start --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>"
python -m flowguard adoption-finish --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>" --command "<check command>"
```

These commands append `.flowguard/adoption_log.jsonl` and
`docs/flowguard_adoption_log.md`. They are evidence helpers, not a substitute
for executable model checks.
