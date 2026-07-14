## Context

The current repository has two active completed OpenSpec changes whose verification contracts independently run overlapping focused tests and the same full FlowGuard model inventory. OpenSpec computes its freshness source hashes before it runs the contract checks. FlowGuard already has DevelopmentProcessFlow freshness rules, PlanDetail source/step rows, TestMesh child evidence, `ProofArtifactRef`, and `TestResultReuseTicket`, but there is no provider-neutral object that connects specification tasks, FlowGuard obligations, checks, sessions, and receipts.

The bridge must remain in the `development_process` plane. OpenSpec and Spec Kit retain their own specification/task/strict-validation/archive authority; product-runtime commitments may be referenced only as typed targets. The repository is shared with a read-only peer agent, so all writes must preserve current files and later peer writes must invalidate only affected evidence.

All seventeen managed skills now need one current runtime authority. Former work contracts, manifests, run records, compatibility readers, and migration declarations are invalid runtime surfaces rather than a second lifecycle to preserve.

## Goals / Non-Goals

**Goals:**

- Add a provider-neutral, canonical Spec Work Package model with stable provider/change/task/obligation/check identities and bidirectional reconciliation.
- Discover OpenSpec and Spec Kit only inside the declared project root or explicit configured roots.
- Separate canonical verification inputs from derived results and record immutable begin/post snapshots for one session.
- Execute or safely reuse a check through an immutable terminal receipt, with exact input, command, tool, environment, coverage, and result identities.
- Deduplicate one execution across multiple consumers without duplicating evidence and require explicit `cross_change_safe` authorization for cross-change reuse.
- Integrate the new rows through existing DevelopmentProcessFlow, PlanDetailing, ExistingModelPreflight, TestMesh, proof-artifact, API, template, skill, install, and post-change routing owners. SelfMaintenance keeps its own route/skill/install/sync closure and does not duplicate provider task state, session state, receipt identities, or verification-contract hashes.
- Use the bridge in the current OpenSpec changes so their identical full-model check can share one current receipt.
- Restore one SkillGuard runtime authority by replacing former surfaces directly with the current contract trio and rejecting residuals.

**Non-Goals:**

- Do not fork or patch the globally installed OpenSpec or Spec Kit packages.
- Do not create a second task state, strict verifier, archive command, product behavior owner, or SkillGuard domain executor.
- Do not scan the whole computer or silently modify provider task files.
- Do not expose this internal development-process structure through product UI content or alter the UI visibility/product-language rules.
- Do not preserve a former runtime as migration evidence or claim execution depth without current owner receipts.

## Decisions

### 1. DevelopmentProcessFlow remains the lifecycle owner

`SpecWorkPackage` is a typed development-process input. PlanDetailing may project provider tasks into ordered plan rows; ExistingModelPreflight may use the package as context after plane-first commitment lookup; TestMesh validates child receipts; DevelopmentProcessFlow owns session order, invalidation, and close/archive readiness. No bridge row copies a product-runtime promise.

Alternative rejected: a new universal spec controller. It would duplicate OpenSpec/Spec Kit task authority and FlowGuard's existing process simulator.

### 2. Provider adapters are bounded and read-only

The OpenSpec adapter reads active change directories, task checkboxes, current verification reports when present, and stable provider metadata. The Spec Kit adapter activates only when a `.specify` project marker exists and reads feature `spec.md`, `plan.md`, `tasks.md`, and checklists. Both return canonical language-neutral rows and never write provider state.

Alternative rejected: unrestricted computer monitoring. It creates privacy, ambiguity, and unrelated-project freshness risks.

### 3. Reconciliation is bidirectional, not a literal merged checklist

Each in-scope task maps to one or more FlowGuard obligation/check ids or a typed scoped-out reason. Each in-scope obligation/check maps back to a provider task or an infrastructure owner. Multiple consumers may reference one receipt without becoming duplicate owners. Unmapped rows and conflicting primary owners block broad completion.

Alternative rejected: one combined checkbox list. Task and obligation relationships are many-to-many and have different owners.

### 4. Canonical inputs and derived outputs are disjoint

The filesystem classifier includes source, specifications, models, tests, prompts, canonical contracts, config, and declared environment/tool identities as inputs. It excludes receipts, reports, JUnit, logs, caches, bytecode, temporary installs, `.flowguard/evidence`, SkillGuard run/report/evidence directories, and ordinary `result.json` files. A derived artifact may point back to its input provenance but cannot become an input of the same session.

### 5. Every verification session has begin and post snapshots

The session begins with an immutable governed-input manifest and ends with a newly computed manifest. Missing post snapshot, changed canonical input, tool/schema/version drift, or a peer write blocks session close and archive. The check that first observes a mutation records the changed paths. Derived-output changes do not stale the session.

Once a session has written its immutable close record, a repeated close request only returns that same record. It does not rescan inputs, mint a new timestamp, rewrite evidence, or execute checks; later currentness belongs to the separate read-only post-report review.

### 6. Receipts are immutable and reuse is fail-closed

A receipt binds its physical owner identity, check-definition hash, command/cwd, input fingerprint, tool/schema/version, environment boundary, owner validation obligations, terminal status, exit code, output hashes, and begin/post snapshot ids. A consumer-local portable ref separately binds the consumer work package, check id, and exact projected `coverage_ids`. Only a terminal successful owner receipt with a current exact consumer projection can be reused. Running, progress-only, skipped, failed, timeout, ambiguous, or stale evidence never becomes a cache hit.

Cross-change reuse requires the check definition to declare `cross_change_safe=true`. The physical reuse key omits consumer change ids and consumer-only coverage only in that case; each consumer remains independently identified by its portable ref and provider projection receipt. Changing consumer coverage stales only that projection and never reruns the still-current physical owner. Default reuse stays within one work package.

### 7. The CLI is a thin native FlowGuard surface

Add canonical JSON commands for provider audit and cached check execution. The cached-check command wraps the target command; it does not interpret domain output as success beyond exit status and declared terminal evidence. The public Python API exposes the same model/review/runner without adding another owner.

### 8. SkillGuard uses one current contract trio

All seventeen managed skills contain only `.skillguard/contract-source.json`, `.skillguard/compiled-contract.json`, and `.skillguard/check-manifest.json` as runtime authority. Former work contracts, underscore manifests, run records, lifecycle declarations, and compatibility readers are rejected. Generated artifacts are rebuilt with the official compiler, and current owner receipts—not migration state—prove execution depth.

## Risks / Trade-offs

- **[Broad input inventory reduces cache hits]** → Prefer safety first; later owner-declared input subsets may narrow keys only with tests proving complete dependency coverage.
- **[A shared receipt could leak across unrelated changes]** → Default to package-local reuse and require explicit cross-change safety plus identical physical command/input/tool/environment identity; bind each consumer's exact coverage separately in its current projection.
- **[Provider file formats evolve]** → Bind provider and adapter versions, fail with `provider_schema_unsupported`, and keep adapters read-only.
- **[Concurrent agents race for one check]** → Use an atomic receipt lock; a live lock reports running/blocked, while an abandoned lock is recovered only with explicit stale-lock evidence.
- **[Former runtime residue reappears]** → Fail the current-authority audit and installation parity check; never route through the residue.
- **[Wrapping checks hides useful output]** → Persist stdout/stderr hashes and bounded diagnostic text in the immutable receipt and print executed/reused status to the caller.

## Migration Plan

1. Add the model, tests, adapters, receipt runner, CLI/API, and focused documentation without changing current provider authority.
2. Delete former runtime surfaces, rebuild all seventeen current contract trios, and verify runtime-authority/project audit.
3. Wrap the shared full-model checks in the two current OpenSpec contracts with one identical explicitly cross-change-safe execution definition; narrow watch inputs away from derived results.
4. Run the new bridge/model/tests, SkillGuard gates, provider audits, and current OpenSpec verifications. Confirm the second identical full-model consumer reports `reused-current` rather than executing again.
5. If any bridge change fails, report the missing owner receipt and repair the current owner path; do not fall back to provider-side copies of the command.

## Open Questions

- None blocking. Exact per-check narrow input inventories are intentionally deferred until the conservative repository-governed manifest has current usage evidence.

## Current protocol correction: one execution owner and a read-only provider consumer

The earlier “wrap provider commands” wording is superseded by the following
single-owner protocol:

1. Physical commands, input selectors, dependencies, execution mode,
   validation scope, and toolchain identity live only in
   `.flowguard/spec_provider_work_packages/bindings.json` under
   `canonical_checks`. An infrastructure binding names
   `flowguard.spec_check_cache` as the owner.
2. A frozen FlowGuard session executes each child owner at most once, writes an
   immutable observation receipt, aggregates the exact declared children, and
   publishes persistent portable envelopes and stable refs below the explicit
   `FLOWGUARD_SPEC_EVIDENCE_ROOT`.
3. The OpenSpec version-3 verification contract contains only `kind: receipt`
   rows. Its `covers` declarations are the provider obligation source projected
   onto the canonical owner; it contains no FlowGuard command, selector,
   dependency, toolchain, begin, close, or receipt-runner lifecycle call.
4. The native OpenSpec verifier independently validates the stable ref,
   envelope, four sidecars, scoped source manifest, semantic receipt identity,
   exact children, and current task/contract state, then writes the provider
   report without executing a FlowGuard owner.

The portable wire uses snake_case only and exact canonical SHA-256 strings.
`semantic_check_id`, declaration `execution_id`, and input-bound
`execution_key` remain distinct. The stable semantic receipt identity excludes
timestamps, run ids, and ref paths, while binding source policy, source files,
toolchain/result/termination fingerprints, coverage, validation obligations,
the exact four sidecar hashes, and recursively parsed child semantic identities.

## Current close split

`spec-session-close` closes only the frozen FlowGuard execution boundary and
cannot claim archive readiness. After OpenSpec has written a current version-3
report, `spec-provider-close-review` performs a read-only reconciliation of
the report rows against current owner receipts. A successful review may return
`archive_ready=true`; this means the evidence is ready for the provider's own
archive decision. It neither executes an archive nor constitutes OpenSpec
archive approval.

Missing or stale report rows, source/toolchain drift, non-terminal results,
missing/swapped children, mixed snapshots, provider re-execution, or provider
calls into FlowGuard owner lifecycle commands fail closed. Derived reports,
refs, envelopes, receipts, and logs remain output-only and cannot refresh their
own governed-source freshness.
