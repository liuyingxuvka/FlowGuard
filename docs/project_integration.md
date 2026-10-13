# Project Integration

FlowGuard has one clean consumer surface and three public lifecycle operations.
The target agent reads the installed skill, while the Python package supplies
the executable check engine.

## Current consumer surface

Start at `$CODEX_HOME/skills/flowguard/SKILL.md`. Once a task names a
subject, load only `references/domains/<subject>/protocol.md` and its explicit
dependencies. The skill is installed by copying `.agents/skills/flowguard/`:

```powershell
python scripts/install_skill.py --target $CODEX_HOME/skills
python scripts/install_skill.py --target $CODEX_HOME/skills --check
```

The target repository does not copy the author checkout or a second copy of the
skill into its own tree. Its own project knowledge lives in
`.flowguard/map.json` (create a first draft with `python -m flowguard map scan`,
then fill in and `map confirm` the component descriptions) and in the models
and tests that map binds to each component.

## Public operations

Understand the software without side effects:

```powershell
python -m flowguard read --root <target-project>
```

After editing, check the map and list what to run:

```powershell
python -m flowguard change --root <target-project>
```

Before a release, run the strict gate:

```powershell
python -m flowguard release --root <target-project>
```

`read` starts zero producers and writes nothing. `change` compares the changed
files (from git, or passed explicitly) with the map and lists only the affected
components, models, and tests; running those models and tests is the proof.
Normal changes rerun the affected models and tests;
per-element good, bad, and draft evidence is added only for an explicit
architecture reduction or candidate comparison. `release` runs the strict map check, the architecture
review errors, and every model, reports what it actually ran, and does not
publish GitHub artifacts by itself. Starter model files come from
`python -m flowguard template <name>` (`--list` shows the names).

## Engine preflight

Before claiming executable evidence, run:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

If this fails, record the operation as blocked or partial. Do not substitute a
local mini-framework, a stale source tree, or an alternate reader. A local
checkout may be selected explicitly for the check engine; say which one in the
result.

## Evidence and handoff boundary

Every result keeps unknown, blocked, not-run, skipped, stale, failed, and
scoped states visible. A log, checkbox, package version, or clean directory
does not prove that a model or test ran. A component reported as stale by
`python -m flowguard map check` has changed since its description was confirmed;
re-read it and confirm it again before relying on that description.

Git tags and GitHub publication remain separate transactions after `release`
has passed.
