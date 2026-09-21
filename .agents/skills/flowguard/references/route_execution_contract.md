# FlowGuard lifecycle execution contract

FlowGuard has one public skill and exactly three public operations: `read`,
`change`, and `release`. This document is the shared execution contract for
those operations. It does not add a route, checker, model authority, or
receipt store. The current public boundary is declared by the root skill,
`references/route_index.md`, and the current consumer release manifest.

## 1. Subject and operation selection

Read `references/route_index.md` before selecting a subject. Select exactly
one domain subject from that index and exactly one lifecycle operation from
`read`, `change`, or `release`. A zero-match subject is `no_match`; conflicting
facts are `conflict`. Keyword similarity, declaration order, a caller's
assertion, or a request to run everything cannot resolve the selection.

Domain folders under `references/domains/` are on-demand reference material
inside the single public skill. They are not discoverable skills, aliases, or
forwarding entrypoints. After a subject is selected, read its `SKILL.md` and
the first protocol named by its local material routing. Load deeper material
only when the selected protocol names a concrete trigger.

The public operation boundary is fixed:

| Operation | Meaning | Side effects |
| --- | --- | --- |
| `read` | Read the accepted current model, selected domain material, and currentness evidence. | No execution, mutation, acceptance, installation, or publication. |
| `change` | Freeze the declared request and affected owners, execute the required native checks, and accept one current result through the compare-and-swap boundary. | Only the declared change and its owned evidence may be written. |
| `release` | Verify the declared release scope, reuse exact valid evidence, fill missing release obligations, and verify the actual projection. | Only the declared release projection may be activated. |

Every other historical command, profile, or mode is rejected as an unknown
operation. There is no compatibility alias, fallback route, alternate reader,
or alternate automatic success path.

## 2. Shared context and ownership

After selection, pass one immutable `RouteContext` envelope to the selected
domain owner. It contains only the current task boundary and the fields needed
for that operation:

- task facts and coverage demand, including preserved unknown, contradictory,
  and scoped facts;
- the real project root, accepted observed-model snapshot, accepted
  revision/head, exact current owner denominator, bindings, and affected ids;
- the claim boundary and selected subject, plus the active OpenSpec change and
  task status when the work is governed;
- current source, contract, check, toolchain, and environment fingerprints;
- the private evidence root and exact receipt references required by the
  selected owner.

The context is shared metadata, not shared semantic ownership. A domain owner
may consume an exact sibling receipt or typed handoff, but it must not copy
the sibling's semantics, invent a child receipt, or turn a related-plane row
into an instruction. Ordinary work reads only the affected model/evidence
neighborhood. Whole-target materialization requires an explicit whole-system,
integration, export, self-qualification, or release fact.

## 3. Producer, reuse, and terminal rules

Every operation classifies its declared work before starting a process:

`execute | reuse_current | blocked | not_run`.

- A `read` operation does not reserve a lease, create a run directory, write a
  receipt, activate a pointer, install a projection, or launch a model/test or
  heavy producer.
- Before `execute`, freeze operation, subject, unit/member, task and coverage
  identities, source/model/contract/check/toolchain/environment identities,
  claim boundary, owner inputs, dependencies, and evidence root. An unmapped
  or ambiguous component stops before any producer and is not converted to
  run-all.
- `reuse_current` is legal only for an exact current terminal receipt in the
  same declared unit and operation boundary with identical subject, owner,
  request, inputs, dependencies, producer, toolchain, environment, policy,
  covered obligations, and required child receipts. Reuse verifies and
  composes only: producer count remains zero and no new run directory, lease,
  or receipt is created.
- A parent or aggregate receipt cannot be relabeled as an independently
  executed leaf receipt. Each owner preserves its native evidence authority.
- A routine functional cycle permits one bounded producer observation and then
  closes. Formal qualification or release projection is admitted only when
  explicitly requested, with its own frozen inputs and one owner.
- After timeout, cancellation, or interruption, confirm the entire descendant
  process tree is absent before accepting evidence or starting another owner.
  Progress, a PID, log text, an old receipt, or a checkbox is not a terminal.

Universal stop conditions return a typed reason and stop at the current owner.
Do not retry by changing output paths, creating a new epoch, loading a
fallback route, or starting a broader operation:

- source, model, contract, toolchain, or environment drift after freeze;
- missing, stale, foreign, malformed, duplicate, ambiguous, in-flight, or
  cleanup-unconfirmed evidence;
- missing owner, unknown component, unresolved reverse binding, or a scope that
  exceeds the selected subject or claim boundary;
- skipped, not-run, or blocked required members under a declared-complete
  claim;
- no current parent for a `--reuse-only` request;
- a real reparse-point gate that cannot be probed because of `WinError 1314` or
  an equivalent capability failure;
- active OpenSpec scope drift or an unavailable required external owner.

Working evidence may remain under the governed private work root while an
invocation is in progress or under review. It is non-authoritative and
release-excluded until the declared projection verifies it. Cleanup is a
separate explicit, gated action.

## 4. OpenSpec and external boundaries

When a task has OpenSpec scope, read its active task artifacts directly. This
contract does not embed historical change IDs or become a second task
authority. On a symlink-capable runner, a governed final gate may reserve at
most one producer and then one same-parent `--reuse-only` check. If the
capability probe returns `WinError 1314`, stop before either run.

External CI, provider, UI, installation, release, and remote operations remain
typed `blocked`/`not_run` unless separately admitted. A current receipt and
the task's own completion evidence are still required; this document never
closes an OpenSpec task by itself.

## 5. Domain reference map

The following subjects are internal reference domains selected through the
single public skill. They do not create additional public operations or public
skill entries.

| Subject | Reference directory | Typical trigger |
| --- | --- | --- |
| `existing-model` | `references/domains/existing-model-preflight/` | Existing model ownership or currentness lookup. |
| `behavior-commitment` | `references/domains/behavior-commitment-ledger/` | External promise/source coverage and one owner. |
| `architecture-reduction` | `references/domains/architecture-reduction/` | Behavior-preserving implementation reduction or retirement proof. |
| `code-structure` | `references/domains/code-structure-recommendation/` | Model-driven pre-code ownership. |
| `contract-exhaustion` | `references/domains/contract-exhaustion-mesh/` | Declared finite cases, combinations, oracles, and shards. |
| `development-process` | `references/domains/development-process-flow/` | Staging, freshness, synchronization, installation, or release. |
| `field-lifecycle` | `references/domains/field-lifecycle-mesh/` | Field, schema, prompt, payload, or persisted-attribute change. |
| `model-mesh` | `references/domains/model-mesh/` | Cross-model topology, parent/child evidence, or stale relation. |
| `model-miss` | `references/domains/model-miss-review/` | Concrete runtime or test miss after model confidence. |
| `model-test` | `references/domains/model-test-alignment/` | Model obligations, code contracts, and tests need comparison. |
| `topology-hazard` | `references/domains/model-topology-hazard-review/` | Anchored future-use hazard before broad confidence. |
| `structure-mesh` | `references/domains/structure-mesh/` | Existing public surface needs parity-aware partitioning. |
| `test-mesh` | `references/domains/test-mesh/` | Large, stale, layered, or release-only validation. |
| `ui-flow` | `references/domains/ui-flow-structure/` | UI states, journeys, controls, and operability. |

If no domain subject is clear, keep the subject as `model-first` and use the
core references for ordinary behavior/state modeling or cross-subject work.

## 6. Completion vocabulary

The selected domain owner owns its decision. A typed handoff names the next
owner and exact affected ids; it does not execute that owner eagerly.
`not_triggered` means a named conditional reference or downstream domain was
not required by current facts. `not_run` means it was required by a broader
claim but intentionally not executed, such as external CI/provider/release
work in a local task. `blocked` means a required gate prevented execution.
None of these states may be silently converted to pass by a parent aggregate
or by re-reading an old receipt.

The final report keeps domain evidence, operation, model currentness, receipt
reuse, external scope, and release/install identity separate. A route contract
or static documentation test proves only documentation alignment; it does not
create a model/test pass or close an OpenSpec task.
