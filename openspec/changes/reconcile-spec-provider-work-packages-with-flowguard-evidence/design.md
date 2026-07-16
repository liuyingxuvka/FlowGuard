## Context

The current repository has two active completed OpenSpec changes whose verification contracts independently run overlapping focused tests and the same full FlowGuard model inventory. OpenSpec computes its freshness source hashes before it runs the contract checks. FlowGuard already has DevelopmentProcessFlow freshness rules, PlanDetail source/step rows, TestMesh child evidence, `ProofArtifactRef`, and `TestResultReuseTicket`, but there is no provider-neutral object that connects specification tasks, FlowGuard obligations, checks, sessions, and receipts.

The bridge must remain in the `development_process` plane. OpenSpec and Spec Kit retain their own specification/task/strict-validation/archive authority; product-runtime commitments may be referenced only as typed targets. The repository is shared with a read-only peer agent, so all writes must preserve current files and later peer writes must invalidate only affected evidence.

Current SkillGuard also resolves all seventeen managed skills as blocked because their new V2 trio coexists with former V1 migration surfaces without an explicit lifecycle declaration. The available evidence proves contract depth, not execution depth, so formal V1 retirement cannot be claimed in this change.

## Goals / Non-Goals

**Goals:**

- Add a provider-neutral, canonical Spec Work Package model with stable provider/change/task/obligation/check identities and bidirectional reconciliation.
- Discover OpenSpec and Spec Kit only inside the declared project root or explicit configured roots.
- Separate canonical verification inputs from derived results and record immutable begin/post snapshots for one session.
- Execute or safely reuse a check through an immutable terminal receipt, with exact input, command, tool, environment, coverage, and result identities.
- Deduplicate one execution across multiple consumers without duplicating evidence and require explicit `cross_change_safe` authorization for cross-change reuse.
- Integrate the new rows through existing DevelopmentProcessFlow, PlanDetailing, ExistingModelPreflight, TestMesh, proof-artifact, API, template, skill, install, and self-maintenance owners.
- Use the bridge in the current OpenSpec changes so their identical full-model check can share one current receipt.
- Restore honest SkillGuard runtime authority by declaring V2-migration until official calibration/retirement evidence exists.

**Non-Goals:**

- Do not fork or patch the globally installed OpenSpec or Spec Kit packages.
- Do not create a second task state, strict verifier, archive command, product behavior owner, or SkillGuard domain executor.
- Do not scan the whole computer or silently modify provider task files.
- Do not expose this internal development-process structure through product UI content or alter the UI visibility/product-language rules.
- Do not claim `v2-only` or execution depth without official content-addressed calibration and retirement receipts.

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

### 6. Receipts are immutable and reuse is fail-closed

A receipt binds work-package/check identity, check-definition hash, command/cwd, input fingerprint, tool/schema/version, environment boundary, coverage ids, terminal status, exit code, output hashes, and begin/post snapshot ids. Only a terminal successful receipt with complete coverage can be reused. Running, progress-only, skipped, failed, timeout, ambiguous, or stale evidence never becomes a cache hit.

Cross-change reuse requires the check definition to declare `cross_change_safe=true`. The reuse key omits consumer change ids only in that case; the receipt still records every consumer through fan-out references. Default reuse stays within one work package.

Provider-orchestrator reuse and FlowGuard check reuse are separate layers. A lightweight wrapper that begins, hydrates, or closes current-session state declares `orchestrator_reuse_policy=never`, so provider resume executes the wrapper again. The wrapper may then consume an exact immutable FlowGuard receipt without rerunning the expensive underlying command. Reusing the outer wrapper itself is unsafe because a new frozen provider workspace does not contain the prior session state.

For OpenSpec 1.6's current verification runtime, the normal route is smaller: OpenSpec directly owns pure command receipts, frozen snapshots, dependencies, receipt consumers, and resume accounting. The FlowGuard adapter preserves those provider-native identities and fields, while this repository's OpenSpec contracts no longer nest `spec-session-begin`, `spec-check-run`, or `spec-session-close` as provider command rows. The FlowGuard session CLI remains the native route for standalone/other-provider integration and any explicit wrapper remains fail-closed with `orchestrator_reuse_policy=never`.

### 7. The CLI is a thin native FlowGuard surface

Add canonical JSON commands for provider audit and cached check execution. The cached-check command wraps the target command; it does not interpret domain output as success beyond exit status and declared terminal evidence. The public Python API exposes the same model/review/runner without adding another owner.

### 8. SkillGuard remains V2-migration until retirement is provable

All seventeen V2 contract sources declare `v1_runtime_authority.status=migration-evidence`, name the exact former V1 surfaces, and state that V2 is the only runtime authority while V1 is migration evidence only. Generated V2 artifacts are rebuilt with official compilers. Formal retirement remains a later atomic action after content-addressed positive/shallow calibration and official eligibility/completion receipts.

### 9. Unrelated product changes keep their own closure owners

The product-language/UI change and the execution-plane partition change remain independent OpenSpec work packages. This provider-bridge change may supply reusable receipt infrastructure, but it does not run, archive, version, or tag those product changes. Folding their closure into this package would broaden scope, duplicate their native archive owners, and recreate the process overreach this work is intended to remove.

## Risks / Trade-offs

- **[Broad input inventory reduces cache hits]** → Prefer safety first; later owner-declared input subsets may narrow keys only with tests proving complete dependency coverage.
- **[A shared receipt could leak across unrelated changes]** → Default to package-local reuse and require explicit cross-change safety plus identical command/input/tool/environment/coverage identities.
- **[Provider file formats evolve]** → Bind provider and adapter versions, fail with `provider_schema_unsupported`, and keep adapters read-only.
- **[Concurrent agents race for one check]** → Use an atomic receipt lock; a live lock reports running/blocked, while an abandoned lock is recovered only with explicit stale-lock evidence.
- **[Migration evidence becomes permanent]** → Keep the retirement trigger and missing execution-depth evidence visible; never call migration `v2-only`.
- **[Wrapping checks hides useful output]** → Persist stdout/stderr hashes and bounded diagnostic text in the immutable receipt and print executed/reused status to the caller.
- **[Provider resume reuses a session side effect]** → Mark state-hydrating wrappers non-reusable at the provider layer and leave exact command reuse to FlowGuard's inner receipt owner.

## Migration Plan

1. Add the model, tests, adapters, receipt runner, CLI/API, and focused documentation without changing current provider authority.
2. Add explicit V2-migration lifecycle declarations and rebuild all seventeen generated contract trios; verify runtime-authority/project audit.
3. Wrap the shared full-model checks in the two current OpenSpec contracts with one identical explicitly cross-change-safe execution definition; narrow watch inputs away from derived results.
4. Run the new bridge/model/tests, SkillGuard gates, provider audits, and current OpenSpec verifications. Confirm the second identical full-model consumer reports `reused-current` rather than executing again.
5. If any bridge change fails, remove only the new wrapper use and receipts; the original provider commands remain available as the declared underlying commands.

## Open Questions

- None blocking. Exact per-check narrow input inventories are intentionally deferred until the conservative repository-governed manifest has current usage evidence.
