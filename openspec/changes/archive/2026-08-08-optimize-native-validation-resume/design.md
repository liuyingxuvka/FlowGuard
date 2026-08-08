## Context

See `proposal.md` for motivation. The failed release candidate showed that the DevelopmentProcessFlow native member selected 31 test files, 19 of which were already owned elsewhere, and reached a fixed 300-second timeout without completing. The parent validation correctly preserved the 14 successful sibling member receipts, but native receipt currentness had to cover every declared command rather than one command subset before selective reuse could be trusted.

The repository also intentionally retires `scripts/sync_shadow_workspace.py` in favor of the skill installer's atomic author projection synchronization. Remaining tests of the retired module would reintroduce a second owner or force a compatibility shim, both of which contradict the direct-current maintenance policy.

## Goals / Non-Goals

**Goals:**

- Give every DevelopmentProcessFlow native obligation one focused, inspectable binding.
- Make native receipt currentness complete enough that exact reuse is evidence-preserving.
- Compose successful unchanged native member evidence after parent or sibling failure.
- Remove the last test dependency on the retired shadow-workspace synchronization route.
- Keep the final parent validation singular and frozen.

**Non-Goals:**

- Do not introduce a persistent cache, receipt alias, alternate store, background retry, or scheduled validation owner.
- Do not make read-only currentness inspection execute missing work.
- Do not change the FlowGuard consumer skill inventory, target-system modeling semantics, or public model schema.
- Do not use elapsed time alone as proof of equivalence or correctness.

## Decisions

### 1. Split the broad member by obligation, not by arbitrary file count

The DevelopmentProcessFlow contract keeps lifecycle core, strategy equivalence, atomic author projection synchronization, bounded validation observation, plan detailing, and agent workflow rehearsal as separately named native bindings. Each binding declares exact tests and exact owned sources.

This is preferred over merely increasing the 300-second timeout because a larger timeout preserves duplicate execution and hides responsibility. It is also preferred over moving every test into one new umbrella owner because that would recreate the same coupling under a different name.

### 2. Recompute the complete native input artifact set

Receipt creation resolves every declared native command's path selectors and adds the receipt producer sources. Currentness verification recomputes the same complete artifact set and requires exact set equality before comparing identities.

This is preferred over binding only the first command or only contract files because either approach can reuse a receipt after another declared check or the producer semantics changed.

### 3. Keep resume an explicit execution command

`--resume` may execute missing or stale members. For each selected member it searches current receipts, independently reconstructs the verification context, accepts only full terminal pass, and otherwise executes the current owner. The result reports `executed_members` and `reused_members`.

A read-only receipt audit remains separate and never invokes resume. There is no automatic background retry and no fallback to older receipts when current verification fails.

### 4. Parent full validation requests resumable native composition

The full-validation child plan invokes the native runner with `--resume`. The parent still freezes source, toolchain, owner plan, and output roots; it does not treat a child receipt as proof for distribution, install, Git, tag, or GitHub Release identities.

### 5. Retire obsolete shadow-workspace tests directly

Tests whose subject is the deleted whole-workspace synchronizer are removed. Current author projection behavior remains covered by the installer-owned atomic author-sync test class, including clean projection, staging, verification, and parity behavior.

This is preferred over keeping an import-only compatibility module because a compatibility layer would preserve a second synchronization authority that the architecture cleanup explicitly retired.

## Risks / Trade-offs

- **[Incomplete command parsing misses an input]** → Contract compilation requires exact path selectors, receipt tests mutate a later-command input, and reuse must fail after the mutation.
- **[Over-splitting creates ceremony]** → Split only distinct obligations that already have separate owners or materially different inputs; do not create one binding per test function.
- **[A reused receipt hides environment drift]** → Environment, producer version, command, proof, result, contract, manifest, suite inventory, and input identities remain part of current verification.
- **[Removing old tests reduces coverage]** → Confirm each still-required author projection behavior is present under the current atomic author-sync test owner; delete only tests whose subject is the retired route.
- **[A later source change stales the focused proof]** → Run focused checks during repair, then one final frozen full validation after OpenSpec, model authority, contracts, and synchronization inputs are stable.

## Migration Plan

1. Compile the split DevelopmentProcessFlow contract and reject unmapped obligations or implementation inputs.
2. Focus-test complete receipt input binding, exact-current resume, full-parent composition, atomic author-sync, and retirement of the old test import.
3. Synchronize the delta requirements into the main specifications and archive this change after verification.
4. Refresh the current FlowGuard self-model authority against the frozen source.
5. Synchronize author and installed consumer projections.
6. Run one frozen final full validation; use its immutable result for release readiness.

Rollback does not revive the retired synchronization script or weaken receipt currentness. If the new path fails before release, leave the release blocked and repair forward under the current schema and owner contracts.
