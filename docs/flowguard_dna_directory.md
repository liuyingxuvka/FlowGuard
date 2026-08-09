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

There is only one current chain. The directory export command is a projection
of that chain; it does not create another model authority.

## What is supporting material

Test logs, run receipts, temporary regression folders, scaffolding, and audit
reports support the DNA but are not copied into the DNA directory by default.
They remain addressable by the fingerprints and paths recorded in the model
and binding layers. A structural check therefore cannot be mistaken for a
claim that source code was executed or that the target was rebuilt.

## How to exchange it

Use `flowguard-self-blueprint-directory-export` when a directory projection is
needed and `portable-blueprint-directory-verify` to check it. Verification is
bounded: it checks the manifest, declared shards, paths, fingerprints, and
duplicate/non-finite JSON hazards without executing target software.

The single-file portable envelope remains an explicit transport option for a
caller who asks for one. It is not required for normal modeling, authority
selection, or exchange, and it is never promoted to the current authority.

## What this does not promise

The directory is detailed enough to guide an equivalent implementation, but
it is not a copy of every source line. A successful directory check proves
model and projection integrity only. It does not perform a reconstruction,
translation, or production execution, and it keeps `not_run` evidence visible.
