## Why

FlowGuard currently has strong freshness and validation primitives, but broad
confidence can still be both too expensive and too permissive: unrelated edits
can trigger repeated checks, while caller-supplied currentness, incomplete
model inventories, synthetic proof references, late parent freezing, or
incomplete process cleanup can still support an apparently green result. The
repository also contains current OpenSpec statements that no longer match the
fifteen-skill consumer authority or the present payload and field contracts.

This change makes currentness independently derived, affected-only, and
receipt-backed; makes one frozen validation parent the sole broad completion
owner; and restores one current specification truth before the next release.

## What Changes

- Add a read-only OpenSpec semantic-sync gate that projects delta operations
  before archive, verifies the actual post-archive current specs, and requires
  an explicit disposition for every audited historical requirement.
- Correct current specifications to the package-owned fifteen-skill consumer
  authority, remove retired public skill and fixed historical version
  authority, restore real payload proof and compact field-schema requirements,
  and record the complete 77-row historical disposition.
- **BREAKING** Make the observed model inventory complete only when every
  declared non-excluded model and runner is materialized; independently derive
  revision diffs, affected closure, and closure-bound evidence before
  activation.
- **BREAKING** Replace caller-authoritative current/match flags with loaded,
  independently verified receipt and input identities in normal runtime.
- Strengthen child receipt identity, subject, scope, obligation, fingerprint,
  and supersession verification; prohibit PlanDetail from synthesizing proof,
  terminal status, exit code, or currentness.
- Freeze the complete validation owner DAG and parent identity before any
  producer starts; invalidate only owners that consume changed components and
  reuse exact-current terminal receipts.
- Add owner/resource single-flight leases and cross-platform descendant-process
  supervision. Cleanup-unconfirmed execution remains blocked and cannot publish
  a receipt, release a residual lease, start a later owner, or auto-retry.
- Make `validation-parent:full` the only evidence subject that may support
  broad done, release, archive, or publish claims.
- Require explicit complete/scoped UI claim inputs, exact shadow consumer-suite
  parity, and implementation-sensitive callable fingerprints.
- Reduce maintained skill prompt size without increasing ceilings or restoring
  retired public routes, then split oversized implementation surfaces behind
  behavior-preserving facades and parity checks.
- Synchronize source, package, author skill projection, installed consumer
  skills, shadow workspace, Git tree, tag, and GitHub Release only after one
  frozen full validation succeeds.

## Capabilities

### New Capabilities

- `openspec-semantic-sync`: Pre-archive projection, historical requirement
  disposition, post-archive equality, and current-spec authority checks.
- `validation-execution-ownership`: Frozen owner DAG, exact parent identity,
  resource single-flight, process-tree cleanup, and parent receipt publication.

### Modified Capabilities

- `authoritative-model-system`: Complete declared/materialized observed
  inventory, live candidate rebuild, full-head CAS, and reverse-revision
  rollback.
- `model-revision-set`: Independently derived snapshot diff, affected closure,
  and native evidence coverage.
- `flowguard-evidence-receipts`: Exact child identity and store-derived
  supersession verification.
- `proof-artifact-bound-evidence`: Proof references resolve to independently
  verified producer receipts and cannot be synthesized by planners.
- `work-context`: Per-artifact source revalidation and consumer-specific input
  edges.
- `test-evidence-mesh`: Receipt-backed reuse, exact owned inventory coverage,
  and real payload execution proof.
- `model-test-alignment`: Verified receipt projection and real payload execution
  proof are required for alignment.
- `plan-detailing-compiler`: Planning preserves exact proof references but never
  produces execution proof.
- `development-process-flow`: Broad process claims consume exactly one verified
  full-validation parent.
- `long-check-observability`: Process-tree terminality and cleanup settlement
  replace PID/log/progress authority.
- `budgeted-model-groups`: Callable and helper implementation identity is part
  of the reusable graph fingerprint.
- `flowguard-validation-command-surface`: Plan-only freezes all owners before
  execution and the full command publishes only a verified parent receipt.
- `flowguard-ui-flow-structure`: Complete and scoped runnable UI claims have
  explicit, non-omissible evidence inputs.
- `flowguard-skill-suite-distribution`: Shadow and installed projections match
  the exact package-owned fifteen-skill consumer authority.
- `flowguard-suite-inventory`: Retired internal route helpers have zero public
  skill, alias, or fallback authority.
- `flowguard-skill-contract-governance`: Maintained prompt reduction preserves
  every target-declared native check and closure contract.
- `project-adoption-version-gate`: Ordinary project upgrade and installed
  currentness consume the single package-owned consumer authority without
  author-suite dependency or writes.
- `flowguard-evidence-field-structure`: Removed duplicate and historical fields
  stay rejected instead of returning through compatibility paths.

## Impact

- Core code: model authority, revision transactions, evidence receipts,
  validation ownership, lifecycle/process supervision, model regression,
  WorkContext, test reuse, PlanDetail, DevelopmentProcessFlow, UI validation,
  distribution synchronization, and budgeted fingerprints.
- Models and tests: authoritative model system, project adoption version gate,
  test evidence mesh, model-impact freshness, WorkContext, model-test-code
  alignment, DevelopmentProcessFlow, PlanDetail, long-check observability,
  distribution, UI, and structure parity.
- Author skills: the single `unit:flowguard-suite` maintenance unit and its
  clean fifteen-skill consumer projection.
- Release: requires a new immutable version, source-only Git tag, installed and
  shadow parity, and a GitHub Release after the frozen full receipt succeeds.
