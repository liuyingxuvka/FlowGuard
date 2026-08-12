## Context

FlowGuard already has separate mechanisms for model authority, evidence
freshness, test partitioning, skill distribution, project adoption, and
release validation. The remaining problem is not the absence of those
mechanisms; it is that their authority boundaries can still be crossed at
composition time.

Today a caller can sometimes present a value that says an input or receipt is
current instead of requiring the consumer to reload and verify the governing
identity. A validation parent can be assembled after child execution has
started, which makes its owner inventory and freshness boundary mutable.
Process liveness, PID state, or a terminal-looking log can be mistaken for
settled process-tree termination. Model candidates can be locally green
without proving that the declared observed inventory is complete or that the
affected closure was derived from the actual base and candidate snapshots.
Planning artifacts can carry proof-like fields even though planning does not
execute the behavior being claimed.

The specification surface has the same class of authority problem. Archived
delta files preserve valuable historical intent, but archive presence does not
prove that every delta reached the current specifications. A read-only audit
found exactly 77 archived ADDED or MODIFIED requirement rows whose exact
headers are absent from the current capability specs. Their required
disposition is already bounded:

| Disposition | Count | Meaning |
|---|---:|---|
| represented by a current replacement | 24 | Keep the current requirement and record the exact replacement; do not restore the historical header. |
| retired or internalized | 30 | Preserve retirement evidence and zero public/runtime authority; do not recreate an alias or compatibility route. |
| restore a minimal current contract | 12 | Restore only semantics still implemented and required now: eight compact field-schema rows, two real-payload-proof rows, and two consumer prohibition/zero-write rows. |
| merge through the existing suite/project owner | 11 | Reconcile inventory, contract governance, distribution, retired public entries, and project adoption through the owner change for package-backed consumer authority rather than creating a competing specification owner. |

The 12 restorations are not permission to revive old schemas. The field rows
describe the current thin shapes and rejection of removed fields. The payload
rows require evidence from a real surface and prohibit synthetic case
generation from acting as completion proof. The consumer rows prohibit
author-control material in the clean projection and prohibit ordinary project
operations from writing SkillGuard state.

The 11 merged rows are similarly constrained. They converge on one packaged
consumer-suite authority containing one `flowguard` kernel and fourteen public
satellites. Author-side SkillGuard inventory remains maintenance evidence for
`unit:flowguard-suite`; it is not a runtime reader, project adoption input, or
second distribution authority. Internal modes such as model-first,
PlanDetailing, AgentWorkflowRehearsal, and the development-process simulator
may remain internal route identifiers, but their retired public skill ids have
no installed, alias, or fallback authority.

OpenSpec remains the owner of proposal, design, delta, task, validation, sync,
and archive writes. FlowGuard may inspect a project-bounded WorkContext and may
run a read-only semantic-sync checker, but it must not author OpenSpec files,
invoke archive as a hidden child, manufacture provider completion, or become a
fallback archive implementation. This is especially important because
semantic preparation and successful provider movement are separate concerns:
a checker can prove the expected projection and later compare the actual
projection, but it cannot claim that a provider performed an atomic write
unless the provider supplies current evidence for that behavior.

The implementation spans the model system, receipt store, validation
orchestration, process supervision, WorkContext projection, TestMesh,
Model-Test Alignment, PlanDetail, DevelopmentProcessFlow, UI evidence,
consumer distribution, maintained skills, and selected oversized code
surfaces. Multiple agents and worktrees may operate concurrently, so source
ownership and evidence invalidation must be explicit. The design therefore
uses one dependency-ordered execution contract rather than treating each
subsystem as an independent green signal.

## Goals / Non-Goals

**Goals:**

- Derive currentness from canonical content, authority, toolchain,
  environment, dependency, and receipt identities rather than accepting
  caller-authored `current`, `match`, or equivalent success flags.
- Project OpenSpec delta semantics without writes before archive and compare
  the actual current-spec projection after archive, with a total,
  non-duplicated disposition for all 77 historical rows.
- Make the package-owned fifteen-member consumer authority the only normal
  runtime source for public FlowGuard skill membership and content.
- Require the observed model head to name a completely materialized declared
  inventory, and replace it only through a base-bound, evidence-complete,
  pointer-last model revision transaction.
- Freeze the component graph, affected owner closure, owner DAG, validation
  request, and parent identity before a producer starts.
- Reuse only immutable terminal-success receipts that independently match the
  same frozen identity; execute only stale or missing affected owners.
- Supervise the full descendant process tree and keep timeout,
  cancellation, interruption, and cleanup uncertainty visible.
- Make one `validation-parent:full` receipt the sole evidence subject for broad
  done, release, archive, publish, or full-confidence claims.
- Preserve exact proof references through planning and evidence meshes while
  preventing planners from creating proof or terminal status.
- Reduce maintained skill prompt weight and split oversized code only after
  behavior, ownership, and facade parity are fixed.
- Preserve peer work and support safe parallel investigation while preventing
  two agents, worktrees, or launchers from owning the same producer identity.

**Non-Goals:**

- Reimplementing or wrapping OpenSpec authoring, validation, sync, or archive
  as a FlowGuard execution path.
- Restoring every historical requirement verbatim or treating historical
  intent as automatically current product policy.
- Adding a compatibility reader, alias, converter, fallback authority, dual
  manifest, or parallel public skill for a retired route or schema.
- Treating SkillGuard author contracts, receipts, router state, or suite maps
  as consumer-runtime or ordinary-project dependencies.
- Making reports, logs, progress events, receipts, or pointer mtimes source
  freshness inputs unless an owner explicitly declares their content as a
  functional input.
- Claiming unrestricted global optimality for affected-only execution or
  guaranteeing that an external provider is atomic without provider-owned
  evidence.
- Letting a source refactor change observable behavior, public imports, route
  ownership, field shapes, error behavior, or evidence semantics.
- Running repeated full validations after each repair. Focused and
  affected-only checks precede exactly one final full parent for a frozen
  identity.

## Decisions

### 1. Use a two-sided, read-only OpenSpec semantic-sync contract

The semantic-sync gate has two immutable observations:

1. `pre_archive_projection`, built from the current spec bytes, delta bytes,
   provider semantic version, normalized requirement identities, and declared
   operations.
2. `post_archive_observation`, built by rereading the actual current specs and
   archived change after the provider operation has terminated.

Projection applies the provider's current semantic order:
`RENAMED -> REMOVED -> MODIFIED -> ADDED`. Requirement matching uses the exact
normalized current header. A rename must name one existing source and one
absent target; a following MODIFIED block must use the new header. MODIFIED
must retain every current scenario unless an explicit removal operation owns
the deletion. Fuzzy title matching, nearest-title replacement, implicit
renaming, and silent duplicate collapse are invalid.

The projection record contains:

- project root and provider identity;
- change id and exact delta file hashes;
- current capability file hashes;
- ordered normalized operations;
- expected post-spec semantic and raw hashes;
- the historical-disposition ledger hash;
- missing, duplicate, conflicting, or unresolved rows;
- a claim boundary stating that the projection does not execute archive.

The 77-row disposition ledger keys each row by archived change, capability,
operation kind, and exact historical requirement title. Each key appears
exactly once. A terminal ledger row has one of:

- `current_replacement`, with a current capability and requirement identity;
- `retired`, with the current retirement/zero-residual owner and evidence;
- `restore_current`, with the target current capability and requirement;
- `external_owner`, with the exact active owner change and terminal handoff.

`undecided`, duplicate keys, missing archive inputs, or a non-terminal
`external_owner` block archive and broad confidence. The final ledger contains
no pending status. The archived source files remain immutable; the ledger
records disposition rather than rewriting history.

After provider archive, the checker requires semantic equality between every
expected projected capability and its actual current spec. It also requires
the archived delta identity to match the pre-observed change. A mismatch is a
provider-operation failure boundary: FlowGuard reports exact changed and
missing requirements, keeps archive/current-spec confidence blocked, and does
not repair or rerun the provider automatically.

This checker is a validation consumer, not an archive launcher. If OpenSpec
later publishes a native transaction receipt, the checker may consume it as
external evidence after independently verifying its identity. Until then,
pre/post equality detects incomplete outcomes but does not relabel sequential
provider writes as atomic.

**Rejected alternatives:**

- Archive presence alone was rejected because it does not prove delta
  projection.
- Comparing file counts or task checkboxes was rejected because neither
  proves requirement semantics.
- A FlowGuard archive wrapper was rejected because it would create a second
  provider execution path.
- Restoring all 77 headers was rejected because 54 are already replaced or
  deliberately retired, and blind restoration would recreate obsolete
  authority.

### 2. Make the packaged fifteen-skill consumer authority singular

Normal runtime loads one immutable package resource containing:

- the ordered public member ids;
- exactly one `flowguard` kernel and fourteen satellites;
- every target-owned consumer file and its content identity;
- projection and schema identity;
- package version identity and an explicit claim boundary.

Installed-currentness, project audit, and project upgrade compare the global
consumer projection with this authority. They do not read the author suite
map, a source checkout, a target-local skill tree, a private registry, or a
fallback literal list. Missing packaged authority is a visible pre-mutation
blocker.

Current specifications refer to the authority and its invariants rather than
pinning prose to a historical release number. Tests may assert that the
current authority has fifteen members, but release/process specifications bind
the selected package and manifest identities rather than embedding `0.64.0`
or another transient version as permanent policy.

The author-source inventory remains separate. SkillGuard may validate author
controls for the one maintenance unit, but compiler output produces a clean
consumer projection containing no `.skillguard`, contract, receipt, router,
run-store, or maintenance dependency. Installation is transactional:
stage, validate exact content and reference closure, activate, perform a
read-only currentness check, and restore the previous projection if a required
post-activation check fails.

The 11 historical merge rows remain owned by
`remove-project-upgrade-author-suite-dependency` until an explicit handoff.
This change may consume that owner's terminal current-spec result or receive a
documented transfer of the exact delta files; it must not edit the same
requirements concurrently. The semantic-sync parent treats those rows as
blocked while their external owner is non-terminal.

**Rejected alternatives:**

- Keeping 15 as duplicated literals across specs, scripts, prompts, and tests
  was rejected because it repeats the drift mechanism.
- Reading the author suite map in ordinary projects was rejected because it
  makes consumer use depend on a maintainer checkout.
- Supporting retired public ids through aliases was rejected because internal
  capability ids already preserve necessary routing without creating another
  installed success path.

### 3. Replace observed model authority through one complete transaction

An observed candidate is admissible only when every model and runner declared
by the selected system inventory is either materialized with a resolved input
identity or carries an explicit, evidence-backed exclusion. Discovery of a
subset is not completeness. Local child green status does not authorize a
system head.

The model revision transaction freezes:

- system id and current observed head;
- complete base snapshot and declared inventory;
- live candidate snapshot rebuilt from current resolved inputs;
- independently derived base-to-candidate change set;
- affected model, relation, field, test, and sibling closure;
- native obligations and current owner evidence for that closure;
- toolchain and environment identity;
- expected head value for compare-and-swap.

The diff and affected closure are derived by the transaction builder, never
supplied as authoritative caller flags. Required evidence is looked up by
exact subject and frozen inputs. The transaction first persists candidate
snapshot, revision set, evidence bindings, and activation receipt. It updates
the sole head last with compare-and-swap against the frozen base. A concurrent
head change rejects activation and requires a new candidate/diff/closure; it
does not merge or retry automatically.

Rollback is another explicit revision transaction. Reversible effects restore
or compensate the prior materialized state, revalidate the restored affected
closure, persist the reverse record, and update the head last. Irreversible
effects keep the current head and require forward repair. Direct pointer
rewind without effect accounting is not rollback.

**Rejected alternatives:**

- Trusting a caller-provided affected list was rejected because omitted
  siblings would remain falsely current.
- Updating the head before records was rejected because crashes could expose
  authority that cannot be reconstructed.
- Allowing both old and candidate heads was rejected because observed
  implementation has one current truth.

### 4. Freeze a component-to-owner DAG before execution

Validation planning is a pure, read-only phase. It compiles governed source,
configuration, model, test, toolchain, environment-policy, installation, and
specification components into a deterministic component graph. Every
functional component maps to exactly one owner or an explicitly declared
shared dependency node. Unknown, ambiguous, missing, foreign-unit, and cyclic
mappings block planning; the fallback is never run-all.

From that graph, the planner derives an affected owner closure and freezes a
DAG containing:

- owner id, subject, request, scope, obligations, and evidence outputs;
- exact consumed component fingerprints;
- owner dependencies and dependency receipt identities;
- toolchain and environment policy plus observed environment;
- resource keys and single-flight lease identity;
- one disposition: `execute`, `reuse_current`, or `blocked`;
- the complete required owner and obligation inventory;
- the final parent identity.

Each child receipt is immutable and content-addressed. A reuse consumer reloads
the receipt from the canonical store and recomputes:

- producer and execution-owner identity;
- evidence subject and scope;
- source/component, request, dependency, toolchain, and environment
  fingerprints;
- obligation and coverage inventory;
- terminal result, exit status, result artifact, and sidecar hashes;
- process-tree terminality and cleanup state;
- supersession/current-head relation.

Caller objects may request lookup but cannot supply authoritative
`current=True`, `matches=True`, or equivalent flags. PlanDetail and WorkContext
may preserve exact receipt or proof references as opaque inputs; they cannot
create a producer receipt, successful status, exit code, or freshness
decision.

Reports, receipts, logs, progress, and authority pointers are outputs. Their
creation or mtime does not invalidate the DAG unless a specific owner declares
their content as a functional input. This prevents evidence from recursively
staling itself.

**Rejected alternatives:**

- Freezing owners lazily as execution proceeds was rejected because later
  discovery changes the meaning of already-produced evidence.
- Reusing by command text or path alone was rejected because two executions
  can have different subjects, inputs, dependencies, or environments.
- Running every owner after an unknown mapping was rejected because it hides
  an incomplete authority graph and recreates the cost problem.

### 5. Supervise processes and resources to settled terminality

Every executing owner acquires a lease over its frozen owner identity and all
declared exclusive resource keys. Leases are canonical state, not advisory
logs. Concurrent identical requests wait for or consume the one producer's
verified terminal receipt. Conflicting mutable-resource owners do not overlap.

The launcher records the initial process and supervises the complete
descendant tree through a platform adapter. POSIX uses process-group/session
termination where available; Windows uses a Job Object or an equivalently
verified descendant-tree mechanism. A launcher timeout, cancellation,
interruption, missing terminal sidecar, or vanished parent PID is not proof
that descendants stopped.

On abnormal termination the supervisor:

1. stops admission of dependent owners;
2. requests bounded graceful termination;
3. escalates through the platform adapter;
4. verifies descendant count is zero and resource use is settled;
5. records cleanup as `confirmed` or `unconfirmed`.

`cleanup-unconfirmed` publishes no reusable success receipt, does not release a
residual resource lease as safe, does not start a later conflicting owner, and
does not schedule or perform an unattended retry. Manual recovery identifies
and settles the same execution; it does not create a second owner attempt.

Liveness events remain useful for monitoring but never support completion.
Only a terminal receipt with confirmed process-tree settlement can enter
parent composition.

**Rejected alternatives:**

- PID disappearance was rejected because descendants can survive their
  launcher.
- A fixed sleep followed by retry was rejected because Windows file/process
  settlement is not proven by elapsed time.
- Scheduled Tasks, background resume, and autonomous retries were rejected
  because they create unowned execution against a mutable worktree.

### 6. Publish exactly one broad parent per frozen identity

`validation-parent:full` is the only evidence subject that supports a broad
done, release, archive, publish, or full-confidence claim. Model, test,
SkillGuard, OpenSpec, installation, UI, payload, project-audit, and other child
receipts retain their specialist meanings but cannot substitute for the full
parent.

Plan-only freezes the complete DAG, required inventories, source/model
authority, installed projection, validation-input manifest, release-tree
inputs when applicable, and parent id before starting zero producers.
Execution then follows the frozen DAG. The parent may compose exact-current
receipts from previous and current runs, but every receipt is independently
verified against the same frozen identity.

A parent passes only when:

- every required owner and obligation has exactly one accepted child receipt;
- every accepted child is terminal-success, exact-current, correctly scoped,
  and cleanup-confirmed;
- required UI and payload evidence is real-surface and current;
- no required child is failed, blocked, stale, skipped, running,
  progress-only, or not run;
- current model head, current specs, package authority, installed/shadow
  projection, source, toolchain, and environment still match the frozen
  identity.

The parent itself is single-flight. There is at most one final full producer
for a frozen identity. A repeated identical request consumes the same verified
parent or composes it without heavy execution; it does not launch a ceremonial
second full run. A changed functional identity produces a new parent identity
and invalidates only its affected closure before one new final parent is
allowed.

If publication occurs and a remote tag, tree, version, target, asset policy, or
receipt comparison fails, the release remains incomplete. An immutable tag is
not moved; correction uses a new version after a new frozen parent.

**Rejected alternatives:**

- Allowing each subsystem to emit broad green was rejected because child scope
  cannot prove whole-flow completeness.
- Freezing the parent after child execution was rejected because it permits
  post-hoc owner selection.
- Rerunning all children before publication was rejected because verified
  exact-current receipts are the intended reusable evidence.

### 7. Apply specification, skill, and structure work in dependency order

The implementation order is:

1. Freeze active-change ownership and parallel-worktree baselines.
2. Add the semantic-sync ledger/checker and reconcile current specification
   authority, including the 12 restorations and terminal handling of the 11
   externally owned merge rows.
3. Implement complete model materialization and revision transactions.
4. Implement receipt verification, component mapping, owner DAG freezing,
   leases, process supervision, and final-parent composition.
5. Align WorkContext, PlanDetail, TestMesh, Model-Test Alignment, UI, payload,
   project adoption, and distribution consumers with the new identities.
6. Run focused behavior and structure characterization checks.
7. Reduce maintained prompts under SkillGuard supervision without changing
   route ownership, native checks, hard gates, or claim boundaries.
8. Split oversized implementation surfaces behind existing public facades.
   Preserve public imports, serialization, CLI, error, and behavior parity;
   remove the old internal implementation only after parity passes.
9. Compile the clean consumer projection, install transactionally, and verify
   source/package/author/installed/shadow identities.
10. Freeze and execute the one final full parent, then perform release steps.

Skill reduction precedes code-structure splitting only after runtime semantics
are fixed, because prompt and contract boundaries must describe the current
owners. Structure splitting follows characterization because facade parity is
its acceptance contract. Neither reduction is allowed to weaken checks merely
to fit a size target.

**Rejected alternatives:**

- Refactoring first was rejected because moving unstable ownership obscures
  whether behavior changed.
- Prompt compression before current spec and route reconciliation was rejected
  because it could preserve stale public routes in a smaller form.
- Combining author validation and consumer installation was rejected because
  they have distinct inputs, outputs, and rollback boundaries.

### 8. Treat parallel agents and worktrees as freshness events, not rollback authority

Every implementation workstream freezes a base commit, exact owned paths, and
consumed component identities. A peer or unknown write to an owned or consumed
component invalidates the affected plan and evidence. It does not authorize
resetting, deleting, or overwriting the peer's work.

Two changes may proceed in parallel only when their path ownership and derived
owner closures are disjoint. Shared current specs, package authority,
generated projections, model head, installation root, and final validation
store are serialized. Cross-worktree evidence is reusable only when content,
toolchain, environment, request, owner, and dependency identities are exact;
branch name, path similarity, or shared commit ancestry is insufficient.

For the existing suite/project owner change, the allowed choices are:

- let that owner finish and consume its terminal post-state; or
- record an explicit handoff of exact delta files and requirements before this
  change edits them.

Silent concurrent editing is blocked. Generated artifacts are rebuilt only by
their declared compiler owner and only after source ownership is settled.

## Alternatives Considered

### Keep the current system and improve messaging

Better messages would make repeated work more understandable but would not
remove caller-authoritative currentness, incomplete owner inventories, or
multiple broad-green subjects. Rejected because the defect is authority, not
presentation.

### Run a complete full suite after every meaningful edit

This is simple but converts every local correction into whole-project cost and
still does not prove that owner discovery was complete. Rejected in favor of a
fail-closed component graph, affected closure, and one final full parent.

### Cache by Git revision

Git revision is useful provenance but too coarse for local model, toolchain,
environment, installed projection, WorkContext, and owner-specific
currentness. It also cannot represent peer writes in a mutable worktree.
Rejected as the sole reuse key.

### Add compatibility for old receipts, fields, skill ids, and authorities

Compatibility would keep the ambiguous success paths that this change is
intended to remove. Historical artifacts may be read only at an explicit
upgrade boundary with a closing disposition. Rejected for normal runtime.

### Let PlanDetail or WorkContext pre-approve evidence

Planning needs to name expected evidence, but allowing it to create success
would collapse plan and execution ownership. Rejected; both surfaces preserve
references and claim boundaries only.

### Make FlowGuard responsible for OpenSpec archive reliability

That would duplicate provider lifecycle ownership and couple FlowGuard to
provider writes. Rejected. FlowGuard checks expected and observed semantics;
the provider owns archive execution and any native transaction/rollback.

## Risks / Trade-offs

- **[Impact graph misses a functional edge]** → Unknown or unmapped components
  block planning; mutation tests remove declared edges and require a visible
  blocker. No run-all fallback hides the defect.
- **[Over-conservative edges rerun too much]** → Record owner reasons and
  consumed components, then narrow edges only with focused equivalence
  evidence. Safety is preferred over speculative reuse.
- **[The 77-row ledger becomes new historical authority]** → Limit it to
  disposition and traceability. Current requirements and package/model
  authorities remain normative; the ledger cannot reactivate behavior.
- **[External archive partially writes before failing]** → Precompute expected
  bytes, retain pre-state hashes, require post equality, and block claims on
  mismatch. Recovery remains provider-owned; no automatic FlowGuard rewrite.
- **[Package authority is missing from a non-editable install]** → Block
  project mutation and installation currentness with an exact package finding.
  Do not consult a checkout or local suite map.
- **[Model inventory grows and makes activation expensive]** → Materialize
  complete identities but execute only the independently derived affected
  closure. Completeness metadata is not permission to skip affected evidence.
- **[Receipt verification becomes more expensive than reuse saves]** → Keep
  receipts content-addressed and owner-local; verify compact hashes and exact
  sidecars before loading large traces. Telemetry measures the trade-off but
  never controls freshness.
- **[Receipt storage grows]** → Garbage collection is a separate plan-bound
  lifecycle consuming reachability and parent heads. Ordinary validation
  never performs persistent cleanup.
- **[Windows descendant settlement is uncertain]** → Prefer Job Object
  supervision; otherwise retain `cleanup-unconfirmed`, the lease, and the
  blocker. Never infer cleanup from timeout or parent exit.
- **[A lease owner crashes]** → Recovery inspects the same execution and
  process tree. Lease expiry alone cannot authorize a second producer while
  resource settlement is unknown.
- **[A peer changes source after planning]** → Recompute the affected plan from
  the peer-inclusive state. Preserve the peer change and invalidate only
  consuming owners.
- **[Prompt reduction removes a necessary hard gate]** → Target-declared
  semantic checks, prompt parity, contract compilation, and clean consumer
  projection all remain independent required children.
- **[Structure splitting changes public behavior]** → Characterization,
  import/API/serialization/CLI parity, dependency-cycle tests, and facade
  delegation evidence block removal of the old implementation.
- **[A final parent passes but publication identity differs]** → Publication
  remains incomplete; the tag is not moved and a corrective version requires
  another frozen identity and parent.

## Migration Plan

### Phase 0: Freeze authority and ownership

1. Record the base commit, dirty/untracked paths, active worktrees, active
   change owners, current model head, package authority, and installed/shadow
   projection identities.
2. Claim exact paths for this change.
3. Resolve the 11 suite/project rows by terminal external-owner completion or
   explicit handoff. Do not edit overlapping specs before that point.
4. Treat every later peer write as an affected freshness event.

### Phase 1: Establish current specification truth

1. Materialize the 77-row immutable disposition ledger and verify 77 unique
   keys with zero undecided rows.
2. Implement read-only pre-archive projection and post-archive comparison.
3. Restore the 12 minimal current contracts without compatibility:
   compact field schemas and rejection of removed fields; PlanDetail and
   TestMesh real-payload proof preservation; consumer prohibition and ordinary
   project zero-write behavior.
4. Apply the 11 suite/project outcomes through their sole owner.
5. Remove stale seventeen-member, `16/17`, retired public-skill, and fixed old
   release-version authority from current specs.
6. Strict-validate the change and all current specs. Do not archive while an
   owner or disposition is non-terminal.

### Phase 2: Direct-migrate runtime authority

1. Add current receipt schemas and independent loaders.
2. Change consumers to derive currentness from loaded identities.
3. Remove caller-authoritative current/match inputs in the same bounded
   migration; add no dual reader.
4. Materialize complete model inventories and introduce the transaction
   builder, affected closure, persistence order, CAS head, and reverse
   transaction.
5. Update PlanDetail and WorkContext to preserve references without creating
   proof.

### Phase 3: Freeze and execute owner plans

1. Compile the component graph and owner DAG in plan-only mode.
2. Add exact receipt resolution and affected-only execution.
3. Add resource leases and platform process-tree supervision.
4. Publish child receipts only after terminality and confirmed cleanup.
5. Compose a parent from current receipts and prove that repeated identical
   execution starts zero heavy producers.

### Phase 4: Align product and distribution consumers

1. Update DPF, TestMesh, MTA, UI, payload, project adoption, and distribution
   gates.
2. Compile the packaged consumer authority from the current author source.
3. Under SkillGuard supervision, reduce prompts while preserving every
   declared route/check/closure contract.
4. Characterize and split oversized code behind stable facades.
5. Build and validate a clean consumer projection, activate it
   transactionally, and compare installed and shadow trees with package
   authority.

### Phase 5: Validate and release

1. Run unit and focused checks after each owned repair.
2. Run affected model and integration owners after their frozen inputs settle.
3. Strict-validate OpenSpec and semantic-sync post-state.
4. Freeze validation and release identities once source, current specs, model
   head, package authority, and installed/shadow projections are final.
5. Start exactly one `validation-parent:full` producer for that identity.
6. After it passes, permit only excluded evidence outputs, create the immutable
   release identity, and perform read-only remote comparison without rerunning
   heavy producers.

## Rollback and Failure Branches

| Failure | Required branch |
|---|---|
| Pre-archive projection has a missing, duplicate, conflicting, or undecided historical row | Block archive. Correct the delta or disposition under its owner; run no provider write. |
| Provider archive terminates but current specs differ from projection | Mark semantic sync failed and broad confidence blocked. Preserve exact pre/post hashes; use the provider's repair/rollback workflow. Do not auto-run archive again. |
| An external owner for one of the 11 rows changes or remains incomplete | Invalidate the consuming plan and keep those rows blocked. Wait for terminal handoff or re-freeze after explicit ownership transfer. |
| Packaged consumer authority is missing or mismatches installed/shadow content | Block project mutation, install currentness, and release. Leave the active consumer projection unchanged or restore the prior transactionally validated projection. |
| Candidate model inventory is incomplete | Reject the candidate before revision activation. Preserve the old observed head. |
| Model head changes before CAS | Reject activation, discard its authority claim, rebuild candidate/diff/closure from the new head, and reuse only still-exact receipts. |
| Activation fails after records but before pointer update | Old head remains authoritative; orphaned immutable candidate records are non-current and may be handled by later plan-bound GC. |
| Reversible effect fails during reverse revision | Keep rollback incomplete and broad confidence blocked until compensation and old-snapshot revalidation finish. |
| Effect is irreversible | Do not rewind the head. Open a forward-repair revision with the real observed state. |
| One child owner fails while siblings pass | Preserve exact-current sibling receipts, repair the failed owner, and execute only its affected closure under a newly frozen parent identity if functional inputs changed. |
| Launcher times out or is interrupted | Supervise and settle the same descendant tree. Until zero descendants and resources are confirmed, retain blocker and residual lease; publish no reusable receipt and start no retry. |
| Prompt or contract parity fails | Keep author validation and consumer installation blocked. Do not weaken the target check or install a partial suite. |
| Post-activation installed check fails | Restore the prior validated consumer projection and report the new projection as rejected. |
| Final parent input changes before tag | Invalidate the parent, recompute affected owners, and produce one new parent for the new frozen identity. |
| Published target differs after immutable release | Keep release incomplete and create a corrective version; never move the existing tag. |

## Parallel AI and Worktree Boundaries

- Each agent records one base commit, worktree path, owned path set, consumed
  component set, and intended generated outputs before editing.
- No two agents edit the same current spec, package authority, generated
  projection, model head, installation root, or validation-store identity.
- The agent owning `remove-project-upgrade-author-suite-dependency` retains the
  11 merged rows until terminal completion or explicit handoff.
- Agents may inspect peer diffs but may not reset, overwrite, delete, stage, or
  commit peer-owned paths.
- A peer write to a consumed input invalidates affected evidence; it never
  authorizes rollback of the peer write.
- Generated files are written by their declared compiler owner after source
  inputs freeze. Another agent does not regenerate them to manufacture parity.
- Long-running producer ownership is global to the frozen identity, not local
  to a shell or worktree. Another agent consumes liveness or the terminal
  receipt and never launches a duplicate owner.
- Cross-worktree receipt reuse requires exact source, model, request,
  dependency, toolchain, environment, and owner identities. Same branch,
  commit, path, or command is not sufficient.
- Integration occurs only after each path owner reports its terminal diff and
  focused evidence. The orchestrator rechecks the combined tree and derives a
  new affected closure.

## Test Strategy

### Layer 1: Static specification and authority tests

- Parse all 77 archive keys and require exactly one terminal disposition.
- Verify each current replacement and restored requirement resolves to one
  current capability/requirement.
- Verify retired rows have zero public/runtime authority.
- Reject seventeen-member, `16/17`, stale fixed release-version, retired
  public-skill, fake-payload-completion, and compatibility-field wording in
  current owner specs.
- Verify current suite membership and files derive from the package authority,
  while author and consumer path policies remain distinct.

### Layer 2: Unit tests

- Delta normalization, operation order, exact rename/modify behavior, duplicate
  detection, scenario preservation, and pre/post hash comparison.
- Receipt identity, tamper detection, supersession, subject/scope mismatch,
  dependency mismatch, and caller-currentness rejection.
- Component mapping, affected closure, cycle/ambiguity/missing-edge blockers,
  deterministic DAG and parent identities.
- Lease identity, identical-request single flight, resource conflict, and
  cleanup-state transitions.
- Complete model inventory, derived diff, sibling closure, CAS, pointer-last
  persistence, and reverse-revision construction.

### Layer 3: Executable model and property tests

- Native good and known-bad cases for incomplete inventory, omitted affected
  sibling, stale receipt, wrong subject, forged proof, dual public skill
  authority, and unmapped component.
- Cartesian cases for owner state, receipt state, process terminality,
  cleanup state, dependency freshness, and parent eligibility.
- Progress/fairness checks proving required owners either settle terminally or
  remain visibly blocked; no hidden retry loop can manufacture progress.

### Layer 4: Focused integration tests

- OpenSpec pre-projection versus actual post-archive state in a temporary
  provider project, including wrong MODIFIED header, rename then modify,
  missing scenario, provider failure, and partial/mismatched post-state.
- PlanDetail and WorkContext preserve an existing proof reference but cannot
  create a successful receipt or currentness.
- TestMesh and MTA require real payload execution proof.
- Model revision activation rejects concurrent head change and incomplete
  affected evidence.
- Parent planning starts zero producers; execution invokes only affected
  owners; parent composition preserves exact-current sibling receipts after
  one failure.

### Layer 5: Process fault injection

- Parent exits while child survives.
- Timeout with a grandchild holding a file/resource.
- Graceful termination succeeds, escalation succeeds, and cleanup cannot be
  confirmed.
- Concurrent identical requests start one producer.
- Conflicting resource owners serialize.
- No new owner or retry starts while a residual lease is blocked.

### Layer 6: Skill, distribution, and structure parity

- All fifteen author members retain exact target-declared semantic checks.
- Clean consumer projection contains no SkillGuard control material and every
  reference resolves.
- Package authority matches source projection, normal package contents,
  installed consumer, and shadow workspace.
- Prompt budgets decrease without a ceiling increase or missing route/hard
  gate.
- Facade characterization proves import, API, CLI, serialization, error, and
  behavior parity; removed implementations have zero alternate authority.

### Layer 7: Final full validation

After every functional input is frozen, plan the complete owner DAG once.
Focused and affected checks may have produced reusable child receipts, but only
one full parent producer may run for the frozen identity. The final test
asserts:

- one complete owner and obligation inventory;
- one producer at most per owner/resource identity;
- exact-current terminal receipts for all required children;
- confirmed descendant cleanup;
- current spec, model head, package authority, installed/shadow, source,
  toolchain, and environment equality;
- exactly one accepted `validation-parent:full`;
- an identical second request executes zero heavy producers;
- any changed functional component creates a different parent identity and
  executes only its declared affected closure before the next single final
  parent.

## Open Questions

No product-authority decision remains open. Two platform implementation
details are resolved by fail-closed defaults:

- If the installed OpenSpec version cannot provide native atomic archive
  evidence, FlowGuard continues to use pre/post semantic equality and reports
  provider atomicity as outside its claim boundary.
- If the Windows runtime cannot provide a reliable Job Object or equivalent
  descendant-settlement adapter, affected executions remain
  `cleanup-unconfirmed` and are not reusable or releasable.
