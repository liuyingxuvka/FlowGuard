# FlowGuard DNA: directory-first model exchange

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

There is only one current chain. It is read and audited in place; no export
command creates another projection or authority.

## What is supporting material

Test logs, run receipts, temporary regression folders, scaffolding, and audit
reports support the DNA but are not copied into the DNA directory by default.
They remain addressable by the fingerprints and paths recorded in the model
and binding layers. A structural check therefore cannot be mistaken for a
claim that source code was executed or that the target was rebuilt.

## How to use it

Point another workspace at the repository's normal source checkout and inspect
the same native model directory and pointer chain. The only supported
operation is an in-place read-only audit of the current directory. There is no
single-file envelope, copied-directory export, or transport command to keep in
sync.

## What this does not promise

The directory is detailed enough to guide an equivalent implementation, but
it is not a copy of every source line. A successful directory check proves the
declared model, bindings, and projection integrity while keeping `not_run`
evidence visible. It reports understanding depth and current gaps; it does not
create a second model authority or a generated target.
