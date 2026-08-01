## Context

See `proposal.md` for motivation. The current observed model-system snapshot contains the relevant owners, and the current package already provides strict task-local Model Maturation v2, open-angle deliberation, DevelopmentProcessFlow, Risk Evidence Ledger, Closure Contract, and model-derived code structure recommendations. The gap is cross-owner identity and admission wiring:

- Model Angle can currently overread a caller-authored `resolved` Boolean.
- Model Maturation has a strong independent-universe contract but no typed intake compiler that assembles pre-code task, preflight, angle, and specialist contributions.
- DevelopmentProcessFlow owns lifecycle and freshness but has no separate implementation-admission value.
- Risk and Closure know route evidence generically but do not enforce one exact maturation identity.
- The agent prompts do not consistently expose sufficiency and authorization as separate results.

This is a current-schema direct replacement inside one registered SkillGuard maintenance unit. Source, editable package, clean consumer projection, installed skills, Git commit, tag, and GitHub Release remain separate authorities.

## Goals / Non-Goals

**Goals:**

- Make task-local model sufficiency machine-checkable before or after implementation evidence.
- Keep execution permission independent from model confidence.
- Preserve the smallest triggered route set and existing public route topology.
- Make broad risk and closure claims consume an exact, current maturation result.
- Preserve each satellite's native semantics while standardizing its contribution boundary.
- Update FlowGuard's executable models before production code and activate the multi-model change as one accepted revision set.

**Non-Goals:**

- No global user, role, persona, or permission model for target applications.
- No public `understanding`, `readiness`, or `authorization` skill or CLI command.
- No mandatory full-suite gate for trivial, read-only, recommendation-only, or unrelated specialist work.
- No compatibility reader, schema alias, dual writer, or fallback authority.
- No attempt to make prompts or user authorization prove factual correctness.

## Decisions

### Decision: Model Maturation remains the sole sufficiency owner

The existing `ModelMaturationPlan` and `ModelMaturationReport` remain the authoritative task-local sufficiency contract. A new current-schema intake layer compiles into that plan instead of creating another parent model.

The intake contains:

- task id, purpose, model/risk ids, base and candidate fingerprints;
- independent task coverage sources and required probe ids;
- typed `ModelMaturationCoverageContribution` rows from current native owners;
- iteration lineage and any exact gap-resolution receipts.

Each contribution contains owner route, contribution id, task id, currentness, coverage source/evidence ids, coverage ids, required probe ids, signals, and an optional current `ProofArtifactRef`. The compiler checks owner/task/currentness, unions and deduplicates coverage and probes, preserves every non-pass contribution as a signal, and computes the existing coverage fingerprint. The candidate cannot remove source-owned items.

Alternative considered: add a public Understanding Readiness model. Rejected because it duplicates Model Maturation, adds a second authority, and makes lightweight routing heavier.

### Decision: Model-angle resolution uses existing ProofArtifactRef

`ModelAngleDeliberation` gains an optional owner proof plus exact subject fingerprint bindings. A required broad-claim angle is resolved only when:

- `resolved` is true;
- the proof is current terminal pass;
- `producer_route` equals the angle's declared owner route;
- the proof covers the angle id/obligation;
- required subject fingerprints match.

Scope-out and defer remain visible scoped outcomes; they do not need fake passing proof and contribute scoped/open coverage to maturation.

Alternative considered: create a new angle-specific evidence type. Rejected because `ProofArtifactRef` already owns current route proof, covered obligations, scope, fingerprints, and status.

### Decision: DevelopmentProcessFlow owns a separate admission value

Add an internal admission review beside the existing lifecycle review:

- `ImplementationAuthorization` records the current request evidence digest, exact allowed action/artifact/path ids, accepted open-gap fingerprints, required validation ids, task/source/model/coverage fingerprints, and invalidation conditions.
- `ImplementationAdmissionPlan` binds the current task, requested action, exact maturation report, optional authorization, target scope, and non-waivable blockers.
- `ImplementationAdmissionReport` returns `understanding_status`, `authorization_status`, `admission`, allowed scope, open gaps, required validations, blockers, and a compact summary.

Authorization states are `not_requested`, `not_authorized`, `authorized_normal`, `authorized_with_open_gaps`, and `stale`. Admission states are `no_code_requested`, `ready`, `ready_scoped`, and `blocked`.

Normal implementation request plus exact closed maturation yields `ready`. Open maturation requires authorization that accepts the exact current open-gap fingerprints and exact bounded scope, yielding only `ready_scoped`. Read-only/no-code, unknown target, safety/approval, scope mismatch, stale identity, live ownership conflict, and missing toolchain are non-waivable.

Alternative considered: a hard global gate. Rejected because it would turn FlowGuard's fit-for-risk routing into one heavyweight mode and would conflate recommendation work with production mutation.

### Decision: Downstream consumers verify one compact maturation identity

Add a compact `ModelMaturationEvidenceRef` derived from a report. It includes evidence id, task id, plan/model id, decision/confidence, candidate and coverage fingerprints, input fingerprint, open gap fingerprints, current status, and terminal status. The exact candidate and coverage values are carried through the report rather than reconstructed from prose.

- Risk Evidence Ledger adds gate kind `model_maturation`. Its typed adapter creates a gate from the evidence ref; missing/stale/scoped/blocked/open/mismatched values emit specific codes.
- Closure Plan accepts maturation evidence refs and a `require_model_maturation` flag. Broad claim scopes require at least one matching current closed result. Closure also checks the risk evidence report metadata/ref identifies the same maturation evidence id.
- Closure does not rerun or reinterpret maturation signals; it checks material, status, and identity only.

Alternative considered: encode maturation as an ordinary generic gate only. Rejected because caller-entered generic confidence cannot prove task/candidate/coverage identity.

### Decision: Code structure distinguishes recommendation-only from implementation-ready

The existing recommendation gains optional admitted task/model/coverage/scope identity and a requested readiness flag. A valid structural recommendation can remain recommendation-only. When implementation readiness is requested, review requires a current `ready` or `ready_scoped` admission with identical scope and identities; target modules and paths must be inside that admission.

### Decision: Satellite routes emit one generic contribution shape

The kernel, ExistingModelPreflight, PlanDetail, BCL, FieldLifecycleMesh, UI Flow Structure, and TestMesh prompts/protocols use the generic contribution contract. ModelMesh and Model-Test Alignment keep their existing maturation handoffs. The central compiler does not import or reinterpret every native report class in the first release; owner-specific projection helpers may construct the generic contribution at their native boundary.

This keeps the runtime dependency graph acyclic and avoids duplicating specialist schemas inside `model_maturation.py`.

### Decision: Model-first implementation and one revision-set activation

Before Python changes, update the current executable models for model angle, DevelopmentProcessFlow, existing-model/preflight handoff, and FlowGuard closure. Known-bad variants cover bare angle resolution, permission-as-confidence, scope expansion, stale authorization, and missing/mismatched maturation consumption.

After focused model checks and implementation tests pass, run the repository model regression owner once on the frozen model/source inventory, build a current `ModelRevisionSet`, and activate it atomically. No partial model pointer update is allowed.

### Decision: Skill source changes precede clean consumer installation

Edit only `.agents/skills/**` source prompts and references. After native API behavior and tests are stable, update the SkillGuard contract source/component selectors, regenerate the compiled contract and check manifest through SkillGuard, run affected-only checks, then one frozen full unit validation. Build and activate the clean consumer projection transactionally; do not hand-edit installed copies.

### Decision: Patch release is 0.68.3

The requested release increments only the third semantic version component from `0.68.2` to `0.68.3`. Version changes occur only after implementation is stable and before the single final release gate so package, docs, adoption, source/install projection, Git tree, tag, and GitHub Release can be compared exactly.

## Risks / Trade-offs

- **Risk: contribution intake becomes another semantic owner** → Keep contributions opaque except for common identity/currentness/coverage/signal fields; specialist routes decide their own semantics.
- **Risk: old callers omit new broad-claim evidence** → Current schema fails visibly for broad claims; narrow recommendation/read-only use remains explicit and does not synthesize compatibility evidence.
- **Risk: authorization grows into a user/role database** → Bind it only to one current task request and fingerprints; store no target-domain role taxonomy or runtime user data.
- **Risk: prompt size grows** → Put the two-result rule in hot-path prompts and detailed field rules in conditional protocols; rerun prompt-budget tests.
- **Risk: other AI changes land during work** → Re-read dirty state at each phase boundary, preserve peer writes, stage only owned paths, and stale only affected evidence.
- **Risk: background validation progress is mistaken for pass** → Run independent checks concurrently only with named owners; consume only terminal exit/result/receipt artifacts; never use unattended resume or scheduled tasks.
- **Risk: model snapshot remains stale after source changes** → Freeze one final model regression, build and activate one exact revision set before release.
- **Risk: installation and Git release diverge** → Compare source, package, consumer installation, commit tree, tag tree, and Release separately after publication.

## Migration Plan

1. Add and validate OpenSpec delta artifacts.
2. Update executable FlowGuard models and run focused model regressions with known-bad variants.
3. Implement the intake, proof binding, admission, risk/closure identity checks, code-structure readiness, templates, CLI/API projection, and focused tests.
4. Update source skill prompts/protocols and prompt-budget/parity tests.
5. Update SkillGuard contract source as required; regenerate compiled contract/check manifest, run affected checks, then one frozen full validation.
6. Build and atomically activate the model-system revision set.
7. Synchronize main OpenSpec specs and archive the completed change.
8. Bump to 0.68.3, refresh project/adoption/version surfaces, build and activate the clean local consumer installation, and verify installed parity.
9. Commit only owned and reconciled peer changes, push the frozen main branch, create tag `v0.68.3`, publish the GitHub Release, and perform post-push identity checks.

Rollback before publication restores the last committed source and installed consumer transaction only if every changed effect is restorable. After an immutable tag or Release exists, any correction uses a new patch version instead of moving the published tag.
