# Project Integration

FlowGuard has one clean consumer surface and three public lifecycle operations.
The target agent reads the installed skill, while the Python package supplies
the executable check engine.

## Current consumer surface

Start at `$CODEX_HOME/skills/flowguard/SKILL.md`. Once a request names a
subject, load only `references/domains/<subject>/protocol.md` and its explicit
dependencies. The target repository does not copy the author checkout, author
receipts, or a second suite map into its own skill tree.

The installed projection and the source identity in the request must agree. A
missing, stale, foreign, or contradictory projection blocks the operation.

## Public operations

Read the accepted current map without side effects:

```powershell
python -m flowguard read --root <target-project> --request read.json --json
```

Change a declared source or model scope through the current compare-and-swap
boundary:

```powershell
python -m flowguard change --root <target-project> --request change.json --json
```

Verify an already accepted current and its declared release projection:

```powershell
python -m flowguard release --root <target-project> --request release.json --json
```

`read` starts zero producers and writes. Its request must include a selected
identity and explicit page budget. `change` runs only the required current
owners. Normal changes use protected-failure native checks and derived
structure coverage; per-element good, bad, and draft evidence is added only for
an explicit architecture reduction or candidate comparison. `release` reports
what it actually verified and does not publish GitHub artifacts by itself.

## Engine preflight

Before claiming executable evidence, run:

```powershell
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

If this fails, record the operation as blocked or partial. Do not substitute a
local mini-framework, a stale source tree, or an alternate reader. A local
checkout may be selected explicitly for the check engine; its identity belongs
in the result.

## Evidence and handoff boundary

Every result keeps unknown, blocked, not-run, skipped, stale, failed, and
scoped states visible. The operation, subject, page budget, owner, source bytes,
toolchain, and result must agree. A log, checkbox, package version, or clean
directory does not prove executable evidence.

Route or obligation changes reopen admission and plan identity. When the actual
check, input, dependency, toolchain, and environment are unchanged, the leaf
execution key can be reused within the same maintenance unit. Performance and
installation evidence belongs in one acceptance result with two sections that
share the frozen identity; no separate delivery handoff service is needed.

Git tags and GitHub publication remain separate transactions after `release`
has verified the current projection.
