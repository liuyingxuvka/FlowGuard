## Why

The final FlowGuard validation path still treated one DevelopmentProcessFlow native owner as a broad 31-file test batch, duplicated tests owned by other skills, and lost more than five minutes to a fixed timeout before the release gate could continue. Native receipts also needed to bind every declared command input so a repeated validation can safely reuse exact-current work instead of either rerunning everything or trusting incomplete evidence.

## What Changes

- Split DevelopmentProcessFlow native validation into small, named responsibilities with exact test and source ownership instead of one overlapping batch.
- Bind each native skill receipt to every declared native command, exact path selector, producer source, contract, manifest, suite inventory, toolchain, and environment input.
- Add an explicit native `--resume` execution path that reuses only independently verified, terminal-pass, full-scope, exact-current member receipts and executes every missing or stale member.
- Make the parent full-validation owner call the native runner through that exact resume path and report executed and reused member counts.
- Retire obsolete shadow-workspace tests that still target the removed synchronization script; keep author projection synchronization under the current installer-owned atomic author-sync tests.
- Preserve visible failure for unknown, damaged, conflicting, stale, timed-out, or non-terminal evidence; add no fallback, alias, compatibility reader, unattended retry, or alternate receipt authority.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `flowguard-validation-command-surface`: Define exact-current native-member resume behavior, complete receipt input binding, and executed/reused accounting for full validation.
- `development-process-flow`: Require bounded native-owner responsibility, non-overlapping affected checks, and reuse of exact-current terminal evidence before release.
- `flowguard-skill-suite-distribution`: Keep author projection synchronization on the current atomic installer owner and retire the removed shadow-workspace synchronization test path.

## Impact

- Affects native-skill receipt creation and verification, the native-check command, full-validation composition, DevelopmentProcessFlow SkillGuard contracts, focused tests, and author/consumer synchronization documentation.
- Does not change FlowGuard's target-system modeling semantics, public model schema, consumer skill count, package API, or release asset policy.
- Existing receipts whose recorded input set or producer identity is incomplete become visibly stale and must be executed once under the current owner before they can be reused.
