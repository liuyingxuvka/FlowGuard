## Context

FlowGuard currently has compact route intentions but three implementation
paths defeat them in ordinary use:

1. Existing Model Preflight can materialize every observed model when no path
   hint is supplied.
2. Validation aggregators preserve complete evidence correctly, but also echo
   large successful child payloads through nested stdout/result structures.
3. Prompt tests budget individual documents rather than the actual first-read
   bundle an agent receives.

The change crosses runtime lookup, evidence serialization, WorkContext
admission, BCL discovery, skill prompts, tests, models, installation, and
release. Complete evidence, negative-path visibility, one observed model
authority, and the existing owner routes are protected contracts.

## Goals / Non-Goals

**Goals:**

- Reduce routine preflight context from inventory-wide expansion to a bounded
  selected-owner closure.
- Reduce successful terminal validation output by an order of magnitude while
  preserving complete immutable result artifacts.
- Measure and gate representative first-read prompt bundles.
- Prevent planning context and bootstrap discovery from silently widening
  ordinary behavior coverage work.
- Make reuse proof independently checkable by its consumer.
- Preserve one current FlowGuard route and one SkillGuard-maintained consumer
  projection.

**Non-Goals:**

- We do not weaken FlowGuard invariants, reduce required failure evidence, or
  hide skipped/not-run/stale work.
- We do not delete historical models or immutable evidence.
- We do not add a tokenizer dependency or require network access for budget
  checks.
- We do not make OpenSpec a FlowGuard execution or evidence owner.
- We do not introduce compatibility output aliases or a second verbose
  success path.

## Decisions

### 1. Select before materializing

Existing Model Preflight will run canonical plane-first BCL lookup first, map
the top bounded primary/supporting owner ids to exact observed instances, and
then add only typed one-hop relations and explicitly affected models. Light
mode returns identities, purpose, fingerprints, boundary, and route. Full mode
materializes ownership details only for this closure.

An explicit broad inventory mode remains available only to bootstrap,
coverage-gap backfill, or an explicit full-inventory audit. Ordinary missing
path hints no longer imply "all models."

Alternative considered: keep all-model materialization and truncate the JSON.
Rejected because it saves output tokens but still spends search, parsing, and
reasoning context.

### 2. Compact terminal envelope, complete artifact

Validation producers continue writing the complete canonical result and
compressed stdout/stderr objects. Default terminal JSON contains status,
counts, run/result identity, result path and hash, failed/blocked/not-run child
ids, and a bounded diagnostic only when non-pass evidence exists.

Successful child stdout and nested parsed payloads are not repeated in the
parent terminal envelope. Complete details remain addressable from the result
artifact. There is no `--verbose` alternate authority; explicit artifact reads
are the sole detail path.

Alternative considered: discard successful streams. Rejected because it would
weaken auditability and immutable evidence.

### 3. Budget actual prompt bundles

A deterministic prompt-budget manifest will name representative routes and
their guaranteed first-read components: root `AGENTS.md`, selected `SKILL.md`,
one automatically required reference, and optional route configuration.
Checks record UTF-8 bytes, characters, lines, and a conservative token estimate
derived from bytes. The estimate is a regression metric, not a billing claim.

Individual-file limits remain useful local diagnostics but cannot satisfy the
combined hot-path gate alone.

### 4. Guaranteed-loaded shared core

Repeated invariant text will move into one shared core that the route loader or
consumer projection explicitly includes for every maintained FlowGuard skill.
Satellite shells retain purpose, trigger, ownership, route-specific gates,
local reference routing, and claim boundary. A plain hyperlink that the agent
may ignore is insufficient.

### 5. Context admission and discovery breadth are explicit

WorkContext artifacts remain fingerprinted change inputs. They enter the
behavior-source inventory only through explicit
`behavior_source_surface_ids`/admission rows. BCL `bootstrap_ledger` and
`coverage_gap_backfill` may derive broad inventories; add/change/remove and
model-miss modes default to affected commitments and explicitly mapped sources.

### 6. Reuse is verified, not asserted

Test-result reuse validation recomputes and compares producer identity,
command, source, artifact, dependencies, environment, result, and coverage
fingerprints. A boolean/current string supplied by the caller is diagnostic
input, not proof.

### 7. Reuse existing FlowGuard owners

The observed owner set will be updated through one ModelRevisionSet. Existing
guidance-compression, existing-model-preflight, evidence lifecycle,
WorkContext/BCL, TestMesh, and DevelopmentProcessFlow models are extended; no
parallel "token optimizer" authority is created. Historical overlapping models
remain immutable evidence but ordinary recall follows active BCL owner and
observed-snapshot relations.

### 8. Prove shard safety before enabling parallel execution

An `isolated_output` declaration is necessary but not sufficient to mark a
model regression as shard-safe. The regression manifest will bind a shard
safety proof contract to the UI content-visibility owner. A current proof runs
one serial baseline and two simultaneous copies with distinct output roots,
then checks terminal equivalence, child-result equivalence, disjoint artifact
ownership, stable input identities, and zero repository mutation.

The UI aggregate may set `shard_safe=true` only while this executable proof
contract remains present and current. Pytest cache writes are disabled for its
child suites so concurrent copies cannot share that mutable cache. A proof
receipt is release evidence, not a permanent compatibility path or a substitute
for the ordinary model regression.

## Risks / Trade-offs

- [A bounded lookup may miss a relevant owner] → Preserve ambiguity as a
  blocker, include exact typed relations/changed-path affected closure, and
  test known cross-owner scenarios.
- [Compact output may make debugging less convenient] → Keep result path/hash
  and failure diagnostics in the envelope; retain complete immutable artifacts.
- [Prompt bundle budgets may be platform-sensitive] → Normalize text and use
  UTF-8 byte/character/line metrics with fixed manifest inputs.
- [Shared-core extraction may accidentally hide a required gate] → Require
  loader/projection inclusion and native skill checks for every maintained
  member.
- [Old callers expect nested success stdout] → Treat the compact current shape
  as a deliberate release change; provide artifact references rather than a
  compatibility reader.
- [Parallel UI checks may collide through caches or child evidence] → Disable
  shared pytest caches, inject a unique output root into every child, compare
  serial/parallel semantic projections, and reject any repository mutation or
  overlapping artifact path.

## Migration Plan

1. Add and validate OpenSpec delta requirements.
2. Update the existing FlowGuard model owners and candidate snapshot.
3. Implement runtime selection, compact result projection, mode/admission
   gates, reuse verification, and prompt telemetry.
4. Add the UI shard-safety proof, execute it, and enable the shard only after
   the proof passes.
5. Update maintained skill source and compile/audit it under SkillGuard.
6. Run focused tests and OpenSpec verification.
7. Freeze source/toolchain/check inventory and run one final full release
   validation.
8. Activate the ModelRevisionSet, bump to `0.63.0`, build/install the package,
   transactionally install all consumer skills, and verify parity.
9. Fast-forward local `main`, push only `main`, create immutable `v0.63.0`, and
   publish the GitHub Release.

Rollback before publication restores the previous source/installed projection.
After publication, any correction uses a new version and tag.

## Open Questions

None. The default output is compact, complete evidence remains artifact-backed,
and `0.63.0` is the release target.
