# FlowGuard DNA: native-directory model authority

FlowGuard's normal DNA is the versioned set of model directories and the
small amount of authority metadata that lets an AI navigate them. It is not a
mandatory giant export file.

## What belongs to the DNA

The model directories under `.flowguard/` are the long-lived model source.
Each model keeps its executable model and its native check entry point. The
current model-system snapshot, accepted revision, and activation receipt bind
those directories to one observed authority. The snapshot also records the
parent/child relations, model inputs, code-facing owners, test-facing owners,
and explicit evidence status (`pass`, `not_run`, `blocked`, or `gap`).

The authoritative chain is deliberately separate:

```text
model directories
  -> current snapshot
  -> accepted revision set
  -> activation receipt
  -> .flowguard/project.toml pointer
```

There is only one current chain. Read-only audits may project a compact view of
that chain for people or tools, but the projection is never another DNA carrier
or model authority.

## What is supporting material

Test logs, run receipts, temporary regression folders, scaffolding, and audit
reports support the DNA but are not copied into the DNA directory by default.
They remain addressable by the fingerprints and paths recorded in the model
and binding layers. A structural check therefore cannot be mistaken for a
claim that source code was executed or that the target was rebuilt.

## How to inspect it

Inspect the native directory in place. For FlowGuard's own repository, use the
read-only self-blueprint check:

```powershell
python -m flowguard flowguard-self-blueprint-check --root . --compact --json
```

For another declared target, use `target-system-blueprint-audit` with its frozen
provider evidence and native report set, or use the affected-blueprint reader
for an ordinary bounded change. These commands report fingerprints, bindings,
readiness, and typed gaps without copying or materializing the DNA.

Former DNA export, copied-directory materialization, and isolated-verification
commands are retired. Invoking an old command returns the typed reason
`native_directory_only`; it does not create a compatibility export or a second
authority. The portable-model JSON IR remains available for an explicitly
declared finite transition relation, but it is model semantics, not a package or
replacement carrier for project DNA.

## What this does not promise

The directory is detailed enough to guide bounded model-backed work, but it is
not a copy of every source line. A successful in-place structural audit proves
only the declared model, authority, and binding integrity. It does not perform
reconstruction, translation, or production execution, and it keeps `not_run`
evidence visible.
