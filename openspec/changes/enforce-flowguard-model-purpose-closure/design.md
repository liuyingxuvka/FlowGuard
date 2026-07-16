## Context

FlowGuard already owns Risk Intent, minimum-valuable-model checks, formal known-bad proof, model regression execution, seventeen installed skill routes, project adoption, and SkillGuard-supervised native checks. The gap is not a missing modeling framework. The gap is that these authorities are not joined into one mandatory, identity-bound record for each concrete model instance. A model can therefore be connected to the regression runner while its stated purpose, finite failure set, good case, bad cases, native oracle, candidate identity, and evidence identity remain disconnected.

The repository is already under a large in-place upgrade. This change must preserve all existing edits, reuse the current model-regression manifest and skill suite, use direct current replacement, and avoid compatibility readers, aliases, optional modes, or parallel authorities.

## Goals / Non-Goals

**Goals:**

- Require the AI to declare one or more concrete failures for the current task before creating or materially changing a concrete model instance.
- Bind that declaration to the exact candidate model, known-good case, one native known-bad case per declared failure, native oracle, claim boundary, and current evidence.
- Upgrade all current registered instances directly and reject missing, duplicate, stale, prose-only, or disconnected declarations.
- Put the same short non-optional loop in all seventeen FlowGuard skill entrypoints while keeping each route's native semantics and checks.
- Keep SkillGuard generic: it freezes and reconciles FlowGuard's declared checks and receipts but does not choose failures or interpret oracles.

**Non-Goals:**

- Assign one permanent purpose to a reusable model type, template, or skill.
- Force ordinary non-Guard skills to use model-purpose closure.
- Add a selectable strict/core/deep mode, an escape hatch, or a second model registry.
- Claim that a declaration alone proves the model catches anything; native good/bad evidence remains required.

## Decisions

### 1. Purpose belongs to a concrete model instance, not a reusable model type

The canonical record uses `model_instance_id` and `task_intent_id`. It may list one or many `protected_failure_ids`. A later task may instantiate the same model type with a different declaration. This preserves reuse without turning a generic model into a single-purpose artifact.

Alternative considered: store one fixed `guarded_purpose` on each reusable model type. Rejected because it would create the misunderstanding the user explicitly ruled out and would prevent task-specific modeling.

### 2. Extend the current regression manifest directly

The manifest schema advances in place and each current entry carries one `purpose_closure` object for the checked-in regression instance. The shared `flowguard.model_purpose` validator owns structural and identity checks; `flowguard.model_regressions` consumes it before selecting or running children. There is no secondary reader or fallback.

Alternative considered: add a parallel purpose registry. Rejected because two authorities can drift and because the existing manifest already owns the registered candidate and runner.

### 3. Freeze purpose before candidate construction and bind the result afterward

The lifecycle is `declare -> freeze -> build/update candidate -> bind candidate -> execute native good/bad proofs -> close`. The declaration fingerprint excludes candidate/evidence outputs so it can exist before construction. Candidate and evidence fingerprints are then joined in the terminal closure. Current checked-in models are directly re-adopted under a frozen declaration and revalidated; this does not claim historical creation order.

Alternative considered: one all-fields record written only after tests. Rejected because it cannot distinguish an upfront purpose from a post-hoc description.

### 4. Native oracles remain native

Every protected failure maps to exactly one declared known-bad case and an owning native oracle. At least one known-good case is required. FlowGuard checks identity, coverage, currentness, and terminal status; it does not replace route-specific semantics with a generic pass/fail oracle.

### 5. All FlowGuard skill routes use one mandatory wording contract

Every skill entrypoint says that model creation or material model change starts with the purpose declaration. If the route does not create or materially change a model, it does not invent one merely to satisfy this rule. This is one fixed conditional workflow, not an optional mode.

### 6. SkillGuard remains a generic execution supervisor

FlowGuard declares the exact native checks that prove the purpose loop. SkillGuard compiles that inventory, runs or reuses each exact owner receipt, and enforces closure. It neither recognizes Guard families nor mandates paired examples for unrelated skills.

## Risks / Trade-offs

- [Risk] Fifty-nine existing entries require direct adoption and could receive shallow labels. -> Mitigation: require distinct task intent, reviewable purpose text, explicit finite failure ids, per-failure case/oracle bindings, and exact model/runner fingerprints; add negative fixtures for generic placeholders and disconnected ids.
- [Risk] Source edits after declaration make evidence stale. -> Mitigation: bind current model, runner, declaration, and proof fingerprints and block stale closure before execution can support a protection claim.
- [Risk] Prompt text drifts across seventeen skills. -> Mitigation: add a single canonical marker and compile/check every source and installed projection.
- [Risk] Full validation is expensive. -> Mitigation: run focused owner tests while editing, freeze one final validation plan after source identities settle, and execute exactly one final full owner.

## Migration Plan

1. Add the current purpose-closure schema and validator.
2. Directly upgrade all 59 manifest entries with current instance declarations and exact candidate/runner bindings.
3. Make manifest audit and regression execution fail closed on missing or stale closure.
4. Add focused positive and negative tests, including one-to-many failure mapping and reusable-type/different-instance behavior.
5. Add the mandatory loop to all seventeen skill sources, regenerate their current SkillGuard contracts, and run exact declared checks.
6. Install the FlowGuard suite last, verify source/install parity, freeze the final validation owner, and run OpenSpec verification.

Rollback is repository-level reversal of this change before release; normal runtime keeps no v1 reader or fallback success path.

## Open Questions

None. The user has fixed the key choices: no optional modes, SkillGuard remains generic, model purpose is task/instance-specific, and FlowGuard is upgraded last.
