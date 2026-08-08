## 1. Freeze the observable contract

- [x] 1.1 Add focused tests that count complete initial validation observations and require exactly one shared observation for a multi-child operation.
- [x] 1.2 Add mutation-between-phases tests for governed source, receipt inventory, owner context, dependency, toolchain, and environment drift.
- [x] 1.3 Add tests proving shared child verification does not merge aggregate owner, subject, obligation, or child-subset identity.
- [x] 1.4 Add tests proving a missing final freshness comparison remains `not_run` and cannot support parent, bundle, or activation currentness.

## 2. Add the invocation-local observation primitive

- [x] 2.1 Implement one immutable typed observation over the canonical repository manifest, receipt inventory, owner contexts, verified child receipts, phase, and canonical fingerprint.
- [x] 2.2 Implement initial observation construction through existing canonical discovery and native verifier owners without adding a fallback or persistent cache.
- [x] 2.3 Implement a final fresh identity observation and exact comparison that reports typed drift without rerunning unchanged child producers or native semantic verifiers.
- [x] 2.4 Expose diagnostic observation counts and bounded phase timings without making them inputs to pass/current authority.
- [x] 2.5 Project literal owner input paths by direct lookup and reserve manifest-wide matching for actual glob patterns, preserving identical resolved manifests without per-owner full-candidate scans.

## 3. Contract model-revision owner evidence

- [x] 3.1 Freeze the complete affected owner-to-child mapping once before writing any model-revision owner aggregate.
- [x] 3.2 Derive every owner aggregate from its exact subset of the one verified child closure and remove per-owner complete replanning/reverification.
- [x] 3.3 Perform one bundle-level final freshness comparison immediately before aggregate publication, reload the content-addressed outputs afterward, and reject the entire bundle on any drift or output mismatch.
- [x] 3.4 Reuse the already verified bundle during candidate construction instead of invoking the complete bundle verifier a second time inside the same build.
- [x] 3.5 Delete or privatize duplicate collection paths that have no remaining caller, after reference review proves their current protections are preserved.

## 4. Contract full model-regression composition

- [x] 4.1 Carry the initial planned owner observation and exact child decisions through runner execution into parent composition.
- [x] 4.2 Replace parent-time complete child rediscovery/reverification with one final fresh identity comparison against the consumed observation.
- [x] 4.3 Preserve independent later-consumer resolution as a new invocation with its own observation; do not persist or reuse the transient object.
- [x] 4.4 Add canonical result diagnostics that separate initial observation, executed/reused child work, final comparison, and parent composition.
- [x] 4.5 Move bounded-batch leaf receipt publication after the one final source observation and publish every executed leaf from those fresh owner contexts without per-child filesystem current rebuilds.
- [x] 4.6 Reconcile the newly published leaf receipts once and complete parent freshness from the final source observation plus exact receipt identities without a third repository scan.
- [x] 4.7 Add focused tests proving N executed leaves still cause exactly two complete repository observations and zero per-leaf source-current rebuilds on the bounded batch path.

## 5. Model, documentation, and focused validation

- [x] 5.1 Update the affected validation-evidence, authoritative-model-system, model-regression, and development-process self-model bindings and scenarios.
- [x] 5.2 Update normative main specs only through OpenSpec sync/archive and update user-facing validation documentation with the one-initial/one-final boundary.
- [x] 5.3 Run one focused test batch covering validation ownership, model-revision evidence/builder, model regression, drift rejection, and timing/count projections.
- [x] 5.4 Run the affected model checks once, inspect counterexamples, and fix any strictness or path-quality regression before renewing model authority.
- [x] 5.5 Record before/after operation counts and wall-time diagnostics from equivalent current inputs; treat timing as diagnostic and identity/count assertions as acceptance evidence.

## 6. Integrate with the release candidate

- [x] 6.1 Build one affected ModelRevisionSet only after code, tests, specs, docs, and self-models are stable.
- [x] 6.2 Verify the OpenSpec change strictly, sync/archive it with the other v0.68.7 changes, and confirm no active requirement delta remains.
- [x] 6.3 Leave full suite, SkillGuard full validation, installation parity, and release validation to the single frozen release-candidate gate rather than rerunning them during this change.
