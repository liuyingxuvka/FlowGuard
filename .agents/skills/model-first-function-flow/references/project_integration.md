# Project Integration

This document explains how a target repository should connect to the real
`flowguard` toolchain before using the `model-first-function-flow` skill.

FlowGuard source repository:

```text
https://github.com/liuyingxuvka/FlowGuard
```

## Preflight

Before modeling in another repository, run:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

This prints the artifact schema version, not the GitHub/package release
version. For example, FlowGuard can be released as `v0.2.1` while the
trace/report schema remains `1.0`.

If this fails, do not create a temporary local mini-framework and claim the
project used FlowGuard. Connect the real toolchain first, or record the task as
blocked or partial.

If the import preflight succeeds but the target project has no FlowGuard model
yet, create one. Existing production code or a prewritten model script is not a
requirement. The agent should write or adapt a model script from the current
plan, run it, inspect counterexamples, and strengthen it when the customer's
risk is not yet visible.

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
python -c "import importlib.metadata as m; print(m.version('flowguard'))"
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

If an AI wrote a model-shaped draft before `flowguard` was available, treat that
draft as an exploratory sketch only, not as FlowGuard evidence. It cannot count
as FlowGuard adoption until the real toolchain is connected and the checks run
against the real package. Record that state as:

```text
skill_decision: blocked_or_partial
status: blocked
friction: flowguard package was not connected to this repository
next_action: install flowguard editable or add an explicit integration path
```

## Project AGENTS.md

After connecting the package, add the rule from `docs/agents_snippet.md` to the
target project's `AGENTS.md`. The low-friction command is:

```powershell
python -m flowguard project-adopt --root .
```

This creates or updates only the managed FlowGuard block in `AGENTS.md`, writes
`.flowguard/project.toml`, and appends adoption records under `.flowguard/` and
`docs/`. The managed block includes the FlowGuard GitHub URL so future agents
know where the real toolchain comes from.

That project rule should require:

- FlowGuard repository URL: `https://github.com/liuyingxuvka/FlowGuard`;
- `flowguard` import preflight;
- installed package version comparison against `.flowguard/project.toml`;
- AI-created model scripts when no model exists yet;
- model-first checks before production edits;
- post-runtime model-miss review when tests, replay, logs, or manual validation
  expose a new issue after FlowGuard already passed;
- adoption log entries for real use;
- explicit blocked status when the real toolchain is unavailable.

Use a read-only audit when you only need to check adoption state:

```powershell
python -m flowguard project-audit --root .
```

If the installed FlowGuard package version is newer than the project record,
run the explicit upgrade path before broad confidence claims:

```powershell
python -m flowguard project-upgrade --root .
```

Then check release notes or the changelog, rerun affected FlowGuard models and
tests, and record the evidence. If the installed package version is older than
the project record, upgrade the local FlowGuard toolchain first.

If the target project also uses a spec/SPAC-style planning or orchestration
skill, treat that tool's plan as optional FlowGuard handoff context. The handoff
should name planned steps, state fields, side effects, parallel ownership,
repeat or retry points, skipped checks with reasons, and completion evidence.
Missing planner support should not block FlowGuard; the agent should fall back
to the normal standalone model-first path.

When `python -m flowguard` is available, the lightweight adoption CLI can reduce
manual log drift:

```powershell
python -m flowguard adoption-start --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>"
python -m flowguard adoption-finish --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>" --command "<check command>"
```

These commands append `.flowguard/adoption_log.jsonl` and
`docs/flowguard_adoption_log.md`. They are evidence helpers, not a substitute
for executable model checks.
