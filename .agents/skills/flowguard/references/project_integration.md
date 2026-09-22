# Project Integration

This reference defines the one current FlowGuard consumer surface. It keeps
the installed skill and the executable check engine separate while exposing
the same three public lifecycle operations everywhere.

## Current consumer surface

The target agent reads the clean projection at
`$CODEX_HOME/skills/flowguard/SKILL.md`. After an explicit subject is selected,
load only the matching
`references/domains/<subject>/protocol.md` and its named dependencies. The
target does not vendor an author checkout, copy author controls into
`.agents/skills/`, or read a second suite map.

The package and the loaded skill must identify the same current source. A
missing, stale, foreign, or mismatched projection is a blocker. Do not guess a
subject or continue through an alternate reader.

## Read

Use `read` for current inspection only:

```powershell
python -m flowguard read --root <target-project> --request read.json --json
```

The request names the target and the selected subject/page budget. `read` may
load the accepted model and selected protocol, but it creates zero producers,
zero writes, zero current-pointer changes, and zero installation or release
side effects. A missing page budget or selected identity is a typed rejection.

## Change

Use `change` for a declared source or model change:

```powershell
python -m flowguard change --root <target-project> --request change.json --json
```

The request freezes the affected owner closure and the exact native checks.
Run only the required current owners and accept through the current
compare-and-swap boundary. Ordinary changes use the real protected-failure
native checks and program-derived structure coverage. Good, bad, and draft
evidence per element is required only when the request explicitly declares an
architecture reduction or candidate comparison.

## Release

Use `release` only to verify an already accepted current and its declared
release projection:

```powershell
python -m flowguard release --root <target-project> --request release.json --json
```

The release result reports the exact source, model, installation, privacy, and
platform identities it checked. Git tags and GitHub publication remain separate
transactions. A release check never turns missing or stale evidence into pass.

## Toolchain preflight

Before claiming executable evidence, confirm the real check engine:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

If the import fails, record the operation as blocked or partial. Do not create
a local mini-framework or a compatibility setup. A local checkout may be
selected explicitly for the check engine, but that source identity must remain
visible in the result.

## Evidence boundary

Keep `unknown`, `blocked`, `not-run`, `skipped`, stale, failed, and scoped
states visible. A read summary, checkbox, directory listing, or package
version is not executable evidence. Record adoption observations in the
declared project log when the target uses one; the log does not refresh source
authority or prove a check.

The operation, selected subject, page budget, owner identities, source bytes,
toolchain, result, blockers, and claim boundary must agree. Changing a route
name or obligation requires fresh admission and plan identity. If the actual
check, inputs, dependencies, toolchain, and environment are unchanged, the
leaf execution key remains reusable within the same maintenance unit.
