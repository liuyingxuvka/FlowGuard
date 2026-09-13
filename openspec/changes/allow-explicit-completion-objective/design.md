## Context

The completion epoch already stores an optional
`completion_objective_fingerprint`, but the full/readiness planners currently
leave it empty and therefore derive the same default cycle from the required
terminal action ids. The persistent reservation correctly blocks a third
attempt, yet there is no public, independently checkable way to identify a
different reviewed objective. The implementation must preserve the existing
finite-cycle and repair semantics while making a new objective explicit.

## Goals / Non-Goals

**Goals:**

- Derive one deterministic objective fingerprint from a named OpenSpec change
  using only its reviewed planning artifacts.
- Use the same derived identity in readiness, full planning, epoch admission,
  and persisted cycle reservation.
- Keep the legacy default objective stable for callers that do not opt in.
- Ensure the old exhausted cycle and all of its evidence remain immutable.
- Fail closed before any producer, lease, receipt, or run directory when the
  objective reference is unsafe or incomplete.

**Non-Goals:**

- Do not increase the two-attempt budget for any objective.
- Do not infer a new objective from source drift, output paths, receipt stores,
  timestamps, random values, owner dispositions, or caller-supplied hashes.
- Do not alter repair-link semantics; repair remains inside the predecessor's
  cycle.
- Do not archive OpenSpec changes, rebuild model authority, install skills, or
  publish releases as part of objective resolution.

## Decisions

1. **Use a named OpenSpec change as the objective boundary.**
   `--completion-objective-change <name>` resolves only beneath the repository
   `openspec/changes` directory. This gives the new cycle a reviewed product
   scope instead of an opaque nonce. The existing `--objective-change` option
   remains the repair-scope locator and is not repurposed.

2. **Hash planning artifacts, not mutable task progress or execution output.**
   The resolver includes `.openspec.yaml`, `proposal.md`, `design.md`, and
   sorted `specs/**/*.md` bytes. It excludes `tasks.md` checkbox progress and
   all work/evidence/output directories, so marking an implementation task
   complete cannot silently buy another cycle. The fingerprint payload carries
   the normalized change name, schema version, relative artifact paths, sizes,
   and SHA-256 content identities.

3. **Centralize the resolver.**
   A small read-only `flowguard.completion_objective` module owns path safety,
   artifact enumeration, hashing, and error codes. Both the public readiness
   adapter and `check_flowguard_skill_suite.py` call it, eliminating a second
   interpretation of the objective boundary.

4. **Bind the existing epoch plan to the resolved fingerprint.**
   `_completion_epoch_plan` passes the derived fingerprint to
   `CompletionEpochPlan.freeze`. The existing `CompletionCycle` derivation,
   reservation store, repair validation, terminal ledger, and reuse-only path
   remain unchanged. A new objective naturally receives a new cycle id; an
   unchanged objective keeps the old id and its finite budget.

5. **Forward one explicit option through both command surfaces.**
   The full-suite parser, canonical readiness parser, and `python -m flowguard`
   forwarding table each accept `--completion-objective-change`. Readiness
   and full must receive the same value; the epoch fingerprint comparison
   blocks a mismatch before reservation.

6. **Keep legacy behavior deterministic.**
   With no explicit objective, the current default derived from required
   terminal action ids is preserved. This avoids rewriting historical ledgers
   and allows old focused callers to continue to test the finite-cycle
   contract.

7. **Bound current evidence reads without deleting history.**
   Full validation selects a run-scoped model-owner receipt directory and
   passes that exact directory to both model regression and self-blueprint
   consumers.  Historical receipt stores remain immutable diagnostic material;
   they are not part of the new cycle's currentness observation.  Native skill
   resume validates one shared suite hash per invocation and then checks each
   receipt's own contract, snapshots, proof, and fingerprint.  This preserves
   strict reuse while preventing repeated full-tree scans from masquerading as
   a stale or endlessly retryable objective.

8. **Keep temporary evidence recoverable during work.**
   Native logs, proofs, and model outputs may live in the controlled run
   workspace while a cycle is active.  Packaging and author/consumer sync
   exclude those artifacts; cleanup is a terminal policy decision, not an
   implicit producer-side deletion.

## Risks / Trade-offs

- [Risk] A reviewed OpenSpec artifact changes after readiness is generated.
  → Its content fingerprint changes, so full admission blocks on an epoch
  mismatch rather than silently using stale readiness.
- [Risk] A caller names a change with extra files or a reparse point.
  → The resolver rejects unknown files, symlinks, and unsafe paths before any
  producer or receipt write.
- [Risk] A new objective could be created for an unnecessarily small scope.
  → The objective name and artifact identities remain visible in the epoch and
  readiness evidence; OpenSpec validation and owner review remain separate
  acceptance gates.
- [Risk] Existing historical ledgers use the legacy default objective.
  → No migration or deletion is attempted. They remain readable and continue
  to block same-objective retries; only an explicit distinct objective derives
  a new cycle.

## Migration Plan

1. Add the resolver, parser forwarding, and plan binding with focused unit and
   integration tests.
2. Validate the new OpenSpec change and all existing changes strictly.
3. Generate readiness for this change with the explicit objective option and
   the same `--require-executed-evidence` setting used by the formal full
   command.
4. Run at most one full producer for this new objective, then one reuse-only
   verification. If the environment or an owner blocks, retain the typed
   result and do not retry the same objective.
5. Rollback is a source-level revert of the new option/resolver only; existing
   epoch ledgers and reservations are never removed or rewritten.
