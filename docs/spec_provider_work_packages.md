# Specification Provider Work Packages

FlowGuard does not replace OpenSpec, Spec Kit, or another specification tool.
The provider continues to own requirements, task completion, native
verification, and archive state. FlowGuard reads one project-root-bounded work
package and governs the development-process relationships that previously fell
between provider tasks and FlowGuard evidence.

```mermaid
flowchart LR
    P["Provider-native tasks and verification contract"] --> W["SpecWorkPackage"]
    W --> R["Bidirectional task / obligation / check reconciliation"]
    R --> D["DevelopmentProcessFlow dependency order and freshness"]
    D --> T["TestMesh child checks and consumer fan-out"]
    T --> E["Immutable EvidenceReceipt"]
    E --> P
```

The bridge preserves distinct identities for the provider, work package,
change, task, provider obligation, provider check, stable FlowGuard validation
obligation, verification session, immutable receipt, and receipt consumer. A
task checkbox is never evidence, and a provider task never becomes a
product-runtime behavior owner.

## Reconciliation

Every in-scope provider task must map to an obligation/check or have a typed
provider/infrastructure owner with a reason. Every required obligation and
check must map back to a task or infrastructure owner. Obligation-to-check
links without an owner do not satisfy this gate.

The built-in adapters are read-only and reject paths outside the selected
project root. OpenSpec reads active change artifacts. Spec Kit reads
`.specify/` plus `specs/<feature>/` and reports `artifact_only` when its CLI is
unavailable. Neither adapter scans the computer.

## Verification sessions and receipts

`spec-session-begin` captures a content-hashed canonical-source manifest.
Reports, logs, caches, receipts, bytecode, run records, and verification output
are derived state and cannot enter the same input fingerprint.

`spec-check-run` normalizes the real command, working directory, timeout,
expected exit, tools, environment, stable validation coverage, and complete
input manifest. It runs a check only when its dependencies passed. A failed
dependency yields `not-run` and does not start the heavy process. Every run
captures a post manifest; a source change during execution blocks the receipt.

Only terminal success with exit code, complete coverage, exact result files,
unchanged inputs, and an independently verifiable immutable receipt is
reusable. Cross-change reuse is disabled unless explicitly declared safe and
the neutral execution identity is identical. Several provider checks may
consume one receipt; they reference it instead of copying it.

There are two reuse layers. Ordinary provider checks may use
`orchestrator_reuse_policy=exact`. A wrapper that begins a FlowGuard session,
projects a cached check into the current session, or closes the session uses
`orchestrator_reuse_policy=never`: the provider reruns that lightweight
wrapper on resume, and the wrapper decides whether the expensive inner check
can reuse an exact immutable FlowGuard receipt. Reusing the outer wrapper
would lose current-session state in a new frozen provider workspace.

OpenSpec 1.6 and later already own frozen snapshots, command-owner receipts,
receipt consumers, dependency receipts, and resume accounting for their native
verification contract. Current OpenSpec contracts therefore declare pure
commands directly with `semantic_check_id`, `execution_id`, precise
`input_selectors`, `depends_on_receipts`, `validation_scope`,
`snapshot_policy`, and `toolchain_identity`; they do not nest the three
stateful FlowGuard session commands as ordinary OpenSpec checks. FlowGuard's
read-only adapter preserves those native fields. On resume, only unchanged
independent owners may be reused; changed owners rerun in the new frozen
snapshot. A stateful wrapper remains `never`-reuse and is not converted into a
portable receipt consumer.

`spec-session-close` captures the same-session post manifest and blocks when
inputs changed, mappings are incomplete, required checks are missing/non-pass,
or provider tasks remain incomplete. The provider's own final verification and
archive gate still run afterward.

## Commands

```text
python -m flowguard spec-work-package-audit --root . --provider openspec --change <change> --json
python -m flowguard spec-session-begin --root . --provider openspec --work-package <change> --json
python -m flowguard spec-check-run --root . --provider openspec --work-package <change> --check-id <id> --semantic-id <stable-id> --validation-obligation <id> --timeout-seconds 600 -- python -m pytest -q
python -m flowguard spec-session-close --root . --provider openspec --work-package <change> --json
```

Canonical JSON uses language-neutral machine identities and reports
`executed`, `reused-current`, `stale`, `not-run`, or `blocked`. Localized
human explanations belong in a presentation layer, not in receipt identity or
input fingerprints.

## Product UI boundary

This bridge is development-process tooling. Its provider ids, task ids,
receipt hashes, cache keys, session state, and audit fields are not product UI
content. Product UI admission, typography, navigation, and design-language
rules remain owned by UI Flow Structure.
