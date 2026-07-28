## Context

The repository contains 61 registered executable model directories. Their checked-in `model.py` and native `run_checks.py` files are the real model source, while the local checkout also contains generated release evidence, temporary build products, and extra worktrees. The tracked repository is about 15 MB, but the working directory is about 369 MB because generated state is retained repeatedly.

The largest avoidable multiplier is the full skill-suite runner: one child JSON report is captured as raw stdout, embedded again in the child's `result.json`, then embedded a third time in the parent's `result.json`. The model-regression runner already owns selection, isolation, timeouts, mutation detection, and receipts through the canonical manifest, but it is exposed mainly as a repository script rather than a package-level simulator command.

The change must preserve target ownership. A model's native runner decides its domain result; the simulator selects and invokes it. SkillGuard later verifies only the exact checks declared by each FlowGuard skill and may not invent a deeper requirement.

## Goals / Non-Goals

**Goals:**

- Provide one stable simulator command for manifest audit, model listing, and selected/all-model execution.
- Remove full-payload replication while retaining complete stdout/stderr as verifiable compressed evidence.
- Make current evidence, retained history, collectible history, quarantine, and purge explicit and auditable.
- Keep release verification and failure diagnosis possible from compact parent/child summaries plus immutable artifact references.
- Document the boundary between model source, native adapters, generated evidence, installed skills, package/build outputs, and unrelated local worktrees.

**Non-Goals:**

- Do not merge 61 domain models into one universal model file.
- Do not replace native `run_checks.py` owners with a generic interpretation engine.
- Do not delete old evidence automatically or infer that the newest timestamp is authoritative.
- Do not migrate or rewrite historical result files into a second supported current format.
- Do not remove a model-local wrapper without separate equivalence and public-entrypoint parity evidence.

## Decisions

### Use the canonical regression manifest as the simulator's sole catalog

`python -m flowguard simulator` delegates to the existing model-regression orchestration APIs. `--list` audits and reports the manifest; `--model` accepts exact ids or globs; `--all` makes broad execution explicit. An unmatched selector or execution request with neither selectors nor `--all` is invalid input. This avoids a second model inventory and preserves one native runner per model.

Alternative considered: discover and import every `model.py` directly. Rejected because the models expose heterogeneous native checks and artifact requirements; bypassing their runners would silently take over domain judgment.

### Store complete streams once as deterministic compressed objects

Each retained run has an `objects/sha256/` store. Logical stdout/stderr bytes are hashed, deterministically gzip-compressed (`mtime=0`), and written once per hash. Child results contain logical hash, byte count, stored hash, compressed byte count, media type, and relative object path. Empty or identical streams share one object inside the run.

Bounded tail text remains in the child result only for diagnosis. Parsed child payloads are fingerprinted and summarized, not nested. The complete JSON payload remains recoverable from the stdout object.

Alternative considered: truncate stdout. Rejected because that loses evidence. Alternative considered: keep raw and compressed copies. Rejected because it preserves the duplication problem.

### Keep canonical parent semantics compact

`ValidationChildResult` remains the common summary type, but aggregate writers store only status, summary, receipt id, claim boundary, and artifact/object descriptors in `payload`. Model-regression reports keep one explicit result row per model; their validation-child projection no longer embeds a second copy of the same row.

Release verification already consumes child ids/statuses and therefore does not need nested full results. Tests will lock this consumption boundary.

### Treat evidence lifecycle as reachability, not age-only deletion

A completed writer records an immutable `evidence-run.json` manifest and transactionally updates a scoped `CURRENT.json` head only after the terminal result is durable. Optional `PINS.json` entries preserve named release evidence. Audit classifies runs as current, pinned, collectible, legacy-unmanaged, quarantined, or invalid.

Garbage collection is four distinct operations:

1. audit is read-only;
2. plan freezes root identity, current heads, pins, candidates, and hashes;
3. apply revalidates the exact plan and moves only still-unreachable candidates into a named quarantine;
4. purge revalidates current/pinned replay and deletes only that exact quarantine.

Ordinary validation may remove only unpublished temporary captures it created after a failed write; it never invokes persistent GC.

Alternative considered: keep the newest N directories automatically. Rejected because timestamp recency is not evidence authority and could delete release-pinned history.

### Historical evidence is visible but not rewritten

Existing result directories without a current run manifest are reported as legacy-unmanaged. They do not become current by inference and are not silently upgraded. A maintainer can pin, quarantine, or retain them explicitly after audit.

### Version and distribution boundary

The package and project records advance to 0.59.0. The installed AI-agent skill suite remains a clean projection of `.agents/skills`; evidence stores, OpenSpec change artifacts, author-side SkillGuard contracts, build outputs, and worktrees are not copied into consumer skills.

## Risks / Trade-offs

- [Tools expecting raw `stdout.txt` may break] → The changed files are validation evidence internals, and current repository consumers are updated to descriptors; complete content remains accessible through a documented gzip object.
- [A crash between result write and head update leaves an unheaded run] → Audit reports it as collectible/orphaned; it is never promoted automatically.
- [A stale GC plan could target newly current evidence] → Apply and purge recompute root/head/pin identities and refuse stale or reachable targets.
- [A single public simulator may be mistaken for one homogeneous model format] → Help text and docs state that it dispatches to native model runners and does not interpret domain semantics.
- [Old evidence remains large until an explicit disposition] → The first v0.59 audit makes legacy state visible; cleanup is deliberate and recoverable rather than automatic.

## Migration Plan

1. Add evidence object/run/head primitives and unit tests.
2. Convert model-regression and full-suite writers to compact descriptors and current run manifests.
3. Add simulator and evidence lifecycle CLI commands plus contract tests.
4. Run focused checks, strict OpenSpec validation, existing-model/architecture-reduction models, and the full release suite from one frozen source snapshot.
5. Recompile and validate all 15 SkillGuard-maintained FlowGuard skills under SkillGuard 0.4.0, then refresh the installed clean consumer projection.
6. Advance package/project/docs to 0.59.0, publish source/tag/release, and verify the remote identity.

Rollback is source rollback before publication. Quarantined evidence is restored by the lifecycle command before purge; purged evidence has no product rollback promise and therefore requires separate explicit authorization.
