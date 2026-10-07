## Context

See `proposal.md` for motivation. The update uses the existing three public FlowGuard operations and the current owner boundaries. The affected paths already have exact receipt, full-parent, output-shape, and author-contract checks; the efficiency changes must fit those checks rather than add a second authority or global cache. The required behavior deltas are in `specs/`.

## Goals / Non-Goals

**Goals:** Reduce work only where the current contract already proves reuse or safe omission: exact-current affected owners, repeated raw-file hashing within one verifier call, repeated conversion of exact native result shapes, cost comparison for one declared candidate, and rehearsal for a handoff with no additional risk trigger. Preserve the full parent gate and make each bounded result reproducible.

**Non-Goals:** Change public CLI/JSON contracts, alter PlanningTool, install or synchronize the consumer skill, change SkillGuard itself, cache evidence across invocations, optimize the parallel model scheduler, compare all 51 owners concurrently, or claim end-to-end time saved without comparable timing evidence.

## Decisions

1. **Keep exact identity as the reuse authority.** Affected membership does not override `reuse_current`; only existing complete currentness checks decide reuse. Raw SHA-256 values are cached by normalized artifact path for one verifier call, but each row's declared digest is still compared independently. Envelope parsing and fingerprinting consume the same bytes.

2. **Publish serial leaf results through a bounded transaction.** The serial `jobs=1` branch checks the exact owner input set before and after execution, confirms descendant cleanup, checks the frozen tracked-metadata guard, and writes the immutable leaf before starting the next owner. It reuses the initial manifest and does not recalculate the repository inventory per leaf. The parent still performs a complete live source/receipt comparison, exact receipt reconciliation, and CAS. `jobs>1` retains its existing batch path.

3. **Project only exact native types early.** `_write_results` skips deep conversion only for the exact known non-report types named in the R2 findings. An exact `ScenarioReviewReport` is structurally checked before one conversion. Unknown supported objects keep the existing conversion and post-check path. The exact `OracleReviewResult` may reuse its already converted nested `scenario_run` mapping inside `_captured_structured_cases`. No cross-stage or cross-call object memo is added, and public serializers remain unchanged.

4. **Use a declared-set check for the single-candidate route.** Candidate count is measured before hard filtering. Exactly one declared candidate still runs all hard outcome, evidence, DAG, owner, freshness, and isolation checks; invalid data supplied by the caller remains invalid. Only optional cost-vector construction and Pareto ranking are skipped. A declaration with multiple candidates stays on the comparison path even if just one survives filtering. A multi-route activation reason paired with one declaration is a contradiction.

5. **Separate handoff freshness from rehearsal risk.** `cross_owner_handoff` becomes an execution-freshness input. The rehearsal admission set remains explicit rehearsal, shared write, post-validation-invalidating write, route/workflow change, or multiple-owner irreversible effect. Coexisting risk still admits rehearsal.

   Independently, an action that writes or invalidates a registered artifact with a non-empty owner must name that exact owner in `ProcessAction.actor`. Review checks the complete action write set before validation freshness, so a foreign pre-validation writer cannot be hidden by a later passing evidence record. Reads and artifacts without an owner remain outside this check.

6. **Bind author requests to the current contract and external persistent state.** The author wrapper consumes the currently installed SkillGuard command and exact request schema, keeps change/release/read ordering, threads the real accepted identity, and stops at the first non-pass result. Request files use only the exact fixed runtime-output prefix; contract, compiled contract, and check manifest remain source inputs. The private self-maintenance child calls the current native builder once and projects its current compact result; the deleted public child command is not restored.

7. **Resolve archived completion objectives by exact identity.** The resolver accepts only a unique direct archive child named by a valid dated prefix plus the unchanged change name. It rejects missing, ambiguous, malformed, or unsafe paths and preserves the objective identity across archive movement.

8. **Bind author reuse to declared bytes and safe state.** The author wrapper fingerprints the exact contract-declared inputs and contract bytes, validates an existing external state root before full admission, and rechecks source/toolchain identity around each CLI call. It recovers only an exact recorded accepted mutation confirmed by a current read; absent or ambiguous records stay blocked.

9. **Preserve parallel residual leases before final checks.** A completed batch marks all cleanup-unconfirmed leases before terminal metadata reads or final freshness checks that can raise. This closes the inherited lease-loss path without changing parallel scheduling or batch publication.

## Risks / Trade-offs

- [A serial owner-local check may miss an unmodeled input edge] → Freeze each owner's exact input mapping before execution; retain the full final parent comparison and block on unmapped inputs.
- [A narrowly skipped conversion may remove data used by downstream quality review] → Skip only exact known non-report types; preserve complete report payloads and use byte/shape parity tests for accepted inputs.
- [A single-candidate declaration may hide omitted alternatives] → Apply the fast path only to the complete declared set of length one, reject a multi-route reason with one declaration, and make no optimality claim.
- [A request output exclusion could mask maintained author inputs] → Exclude only the exact `runtime-requests/full-author-assurance/` subtree; retain adjacent contract and manifest files in source identity.
- [Current FlowGuard/SkillGuard identities can drift during work] → Freeze source and toolchain identities before final validation, use the explicit private roots from `workspace.json`, and stop on stale identity or CAS conflict.

## Migration Plan

1. Freeze the isolated clone, source owners, model/check mapping, and current author schema.
2. Implement and focused-check the four non-overlapping lanes; then integrate the bounded workflow changes and exact runtime-output exclusion.
3. Update the accepted FlowGuard model and affected evidence map through the current `change` lifecycle after source edits settle.
4. Run the five cross-lane checks and finite three-sample measurements. Freeze source, docs, patch version, exact owner map, and release target before completing the change tasks.
5. Once every implementation and candidate-preparation task is complete, archive this change without reapplying specs that are already synchronized. Resolve readiness from the unique archived objective, inspect the full-parent plan, and execute one foreground final parent. Then verify the local candidate, commit only the frozen allowlist, create and publish the non-overwriting source-only patch release, and read back the remote main, tag, and release identities. These post-archive runs and publication are immutable release evidence, not task-checkbox updates. Rollback consists of reverting only the isolated candidate commit before publication; after publication, use a new patch rather than replacing a tag.

## R7 selected-use and continuation

FULL+SELECTED checks complete owner/state/effect/field/contracts inside actual triggered closure, without global audit; BROAD is explicit whole scope. Same invocation shares physical source bytes and distinct raw/functional/intent projections including task checkbox/LF rules. Next invocation reobserves content even with restored size/mtime.

One direct-current external continuation descriptor binds source/evidence/unit/work/base/approved paths/component inputs/one producer owner/operation paths/qualification selectors/env/policy/seal. Controller policy and functional identity are distinct; reports/checkboxes do not reopen checks. Pure decision shares one observation; owner pre/post/CAS/publication remain fresh. Unknown edges block instead of run-all; launcher timeout is non-success, never functional completion.

Add actual failed-sibling-to-model-parent bridge to existing four interactions; failure executes only changed connection once, exact siblings reuse, no retry/failed reuse/success parent, outer consumer rejects, writes0/tree0. Preserve six paired labels and three samples per side; record physical read counts and same-task compact bytes with equal refs, no invented actual-token or total-speed percentage.

Generated outputs finish before final freeze and consolidated qualification. Preserve actual354 nodes plus all R7 mandatory nodes. Archive/readiness/plan-only/unique foreground full and official local-candidate/tag/published verifier phases remain ordered.
