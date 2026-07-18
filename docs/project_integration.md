# Project Integration

This document explains how a target repository should use FlowGuard as an
AI-agent skill suite with executable check scripts.

FlowGuard source repository:

```text
https://github.com/liuyingxuvka/FlowGuard
```

## Agent Skill Suite Setup

For AI-agent use, FlowGuard setup means the agent can read the skill suite, not
that a Python package has been installed.

The required agent-visible surface is:

- `AGENTS.md`
- `$CODEX_HOME/skills/flowguard/SKILL.md`
- all sibling FlowGuard `SKILL.md` files under `$CODEX_HOME/skills/`
- any referenced `references/`, `assets/`, and check scripts used by the
  selected route

Start from `flowguard`. Use a direct FlowGuard sibling skill
when the route is obvious, and use the kernel when route selection is unclear.
The target repository does not vendor a second project-local FlowGuard suite,
does not copy the suite into `.agents/skills/`, and does not own
`.skillguard/flowguard-suite/suite-map.json`. The author repository owns that
maintenance map. The installed package instead ships one deterministic
clean-consumer authority, and the current Codex skills root owns the one clean
consumer projection.

Project audit and upgrade use exactly one consumer-validation path: packaged
authority to `$CODEX_HOME/skills/` plus its ownership manifest. They do not
read an author checkout, project-local suite, `.skillguard` state, alternate
manifest, or fallback reader. Missing or mismatched current authority is a
visible blocker before any project-upgrade write.

If the agent can read the skills but cannot run executable checks yet, record
that as scoped or partial evidence. Do not treat package metadata, a passing
project audit, or a directory named `flowguard` as proof that the AI-agent
skill suite is installed.

## Executable Check Preflight

Before claiming executable FlowGuard evidence in another repository, run:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

This checks the local executable check engine and prints the artifact schema
version, not the GitHub release version. For example, FlowGuard can be released
as `v0.52.2` while the trace/report schema remains `1.0`.

If this fails, do not create a temporary local mini-framework and claim the
project used FlowGuard. Connect the real check engine first, or record the task
as blocked or partial.

If the import preflight succeeds but the target project has no FlowGuard model
yet, create one. Existing production code or a prewritten model script is not a
requirement. The agent should write or adapt a model script from the current
plan, run it, inspect counterexamples, and strengthen it when the customer's
risk is not yet visible.

## Local Check Engine Source

When the check engine must be run from a local FlowGuard checkout, point the
agent or shell at that source tree explicitly:

```powershell
$env:FLOWGUARD_SOURCE = "<path-to-your-FlowGuard-checkout>"
$env:PYTHONPATH = "$env:FLOWGUARD_SOURCE;$env:PYTHONPATH"
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

The repository exposes `python -m flowguard ...` as the current command
surface for checks, templates, and project records. That surface is a
check-execution convenience; it is not the AI-agent skill install surface.

If a development environment deliberately wants editable metadata for those
current commands, it may run:

```powershell
python -m pip install -e $env:FLOWGUARD_SOURCE
```

Record that as check-engine command setup, not as FlowGuard skill setup.

## Toolchain Preflight Helper

The Skill includes a standard-library helper for active Python environments
that cannot import FlowGuard yet:

```powershell
python <path-to-flowguard-skill>\assets\toolchain_preflight.py --json
```

If the helper reports `mode: pythonpath_available`, the source tree is usable
but the active environment has not been permanently connected yet. Run one of
the recommended check-engine commands before treating executable evidence as
current.

To point the helper at a local source tree:

```powershell
python <path-to-flowguard-skill>\assets\toolchain_preflight.py --source <path-to-your-FlowGuard-checkout> --json
```

To let it prepare editable metadata for current commands:

```powershell
python <path-to-flowguard-skill>\assets\toolchain_preflight.py --source <path-to-your-FlowGuard-checkout> --install-editable --json
```

The helper does not replace skill-suite setup or import preflight. After it
succeeds, still run:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

## What Not To Do

Do not:

- copy only a few FlowGuard concepts into the target repository and call it
  FlowGuard;
- write a one-off mini framework and mark the task as fully checked;
- hide import failures behind prose;
- treat skipped check-engine setup as a passed model-first check;
- treat package metadata as proof that the global FlowGuard consumer skills are
  available to the AI agent.

If an AI wrote a model-shaped draft before `flowguard` was available, treat
that draft as an exploratory sketch only, not as FlowGuard evidence. It cannot
count as FlowGuard executable evidence until the real check engine is connected
and the checks run against it. Record that state as:

```text
skill_decision: blocked_or_partial
status: blocked
friction: flowguard check engine was not connected to this repository
next_action: make the FlowGuard skills visible and connect the check engine
```

## Project AGENTS.md And Records

After the target agent can see the skill suite, add the rule from
`docs/agents_snippet.md` to the target project's `AGENTS.md`. The low-friction
current command is:

```powershell
python -m flowguard project-adopt --root .
```

This creates or updates only the managed FlowGuard block in `AGENTS.md`, writes
`.flowguard/project.toml`, and appends adoption records under `.flowguard/` and
`docs/`. The managed block includes the FlowGuard GitHub URL so future agents
know where the skill suite and check engine come from.

That project rule should require:

- FlowGuard repository URL: `https://github.com/liuyingxuvka/FlowGuard`;
- FlowGuard skill-suite visibility under `$CODEX_HOME/skills/`;
- `flowguard` executable check preflight;
- installed check-engine version comparison against `.flowguard/project.toml`
  when version freshness matters;
- AI-created model scripts when no model exists yet;
- model-first checks before production edits;
- Model-Miss Review for non-trivial bug repairs and for tests, replay, logs, or
  manual validation that expose a new issue after FlowGuard already passed;
- adoption log entries for real use;
- explicit blocked status when the skill suite or check engine is unavailable.

Use a read-only audit when you only need to check adoption state:

```powershell
python -m flowguard project-audit --root .
```

If the installed check-engine version is newer than the project record, run the
explicit upgrade path before broad confidence claims:

```powershell
python -m flowguard project-upgrade --root .
```

This does more than update version text. For an older adopted repository,
`project-upgrade` also scans known FlowGuard artifacts, model evidence, tests,
docs, and guidance for deterministic upgrades into the current FlowGuard
shape. Use `--records-only` only when intentionally scoping out that scan, and
run `python -m flowguard artifact-upgrade --root . --apply` when you need the
upgrade scan directly. Before writing, it must first prove exact parity between
the authority shipped in the installed package, the global 15-skill consumer
projection, and the distribution ownership manifest.

Then check release notes or the changelog, rerun affected FlowGuard models and
tests, and record the evidence. If the installed check-engine version is older
than the project record, connect a current FlowGuard check engine first.

FlowGuard is latest-schema-first. Old artifacts may be detected and upgraded at
project/tool boundaries, but normal route logic should not preserve long-lived
compatibility branches for obsolete fields, aliases, or wrappers.

If the target project also uses a spec/SPAC-style planning or orchestration
skill, treat that tool's plan as optional FlowGuard handoff context. The handoff
should name planned steps, state fields, side effects, parallel ownership,
repeat or retry points, skipped checks with reasons, and completion evidence.
Missing planner support does not change FlowGuard's current authority; the
agent uses the normal standalone model-first path directly.

When `python -m flowguard` is available, the lightweight adoption CLI can reduce
manual log drift:

```powershell
python -m flowguard adoption-start --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>"
python -m flowguard adoption-finish --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>" --command "<check command>"
```

These commands append `.flowguard/adoption_log.jsonl` and
`docs/flowguard_adoption_log.md`. They are evidence helpers, not a substitute
for executable model checks.
