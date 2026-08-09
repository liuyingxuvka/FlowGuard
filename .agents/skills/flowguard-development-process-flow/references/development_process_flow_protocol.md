# DevelopmentProcessFlow Protocol

Use `development_process_flow` as the public development-process simulator for
non-trivial planning, multi-skill work, staged execution, freshness, sync,
release/archive/publish, and final process claims. It owns lifecycle order and
evidence freshness; it consumes specialist evidence without taking over the
specialist's judgment.

## Modes

Record applicable modes in this order:

1. `plan_detailing`: run the internal plan-detailing route for rough or
   underspecified plans when structured rows are needed.
2. `strategy_selection`: an internal, conditional process-optimization mode.
3. `agent_workflow`: run the internal agent-workflow route for multi-skill,
   tool, plugin, or external-side-effect rehearsal.
4. `execution_freshness`: review artifact versions, evidence, sync, and final
   claim closure here.

The internal mode id remains `strategy_selection`; it is not a public route or
a mandatory choice for every task.

## Conditional Local Material

- Read `process_optimization_protocol.md` only when `explicit_request`,
  `multiple_equivalent_routes`, `material_rework_risk`, or
  `diagnostic_boundary_choice` applies.
- Read `failure_triage_protocol.md` only after failed, stale, skipped,
  timeout, not-run, progress-only, ambiguous, or materially surprising
  evidence needs classification or root-cause grouping.
- Read `distribution_release_protocol.md` only when installation,
  distribution, sync, full validation, release, archive, publish, or broad-done
  identity is in scope.

With no optimization reason, record `not_needed` and add no candidates, cost
records, repair groups, or optimization evidence gate.

Model-path quality is not another public mode. It is a ModelMaturation-owned
subdecision whose exact result identities are ordered and refreshed here.

## Ownership

- DevelopmentProcessFlow owns process order, artifact versions, invalidation,
  current decision references, peer-write handling, and process claims.
- Internal `plan_detailing` owns structured plan rows, not execution proof.
- Internal `agent_workflow` owns AI-operation skill/tool order.
- TestMesh owns diagnostic boundaries, actual execution accounting, findings,
  skips, and terminal test receipts.
- Finding Ledger owns stable raw finding ids.
- Every external planning provider owns its native artifacts, status,
  validation, and lifecycle. DevelopmentProcessFlow may consume only current
  declared read-only `WorkContext` values; it owns no provider execution
  bridge.
- Model-Test Alignment owns ordinary obligation, primary CodeContract owner,
  and TestEvidence closure.
- Product models retain product-runtime behavior; process references are typed
  targets, not ownership transfers.

## Intake

Capture grouped rows for:

- Changed artifacts: id, type, current version/fingerprint, path/owner, upstream ids;
- Process steps: id/type, status, reads, writes, invalidations, order, actor plane,
  typed target planes/commitments/relations, required and produced evidence;
- simulator modes: reason, delegate, required evidence, scoped gaps;
- validations: obligation id, required artifacts/evidence kinds, scope,
  command, V-style pair where relevant;
- Validation evidence: id, kind, owner route, status, covered and verifier versions,
  command/result, skip/background/release caveats, and proof artifact;
- Freshness rules: upstream change, affected artifacts/evidence, and rationale;
- synchronization domains: source, shadow, formal repository, package,
  installed skills, and Git revision/receipt;
- model-authority intent mode (`bootstrap|refine|blocked`), current accepted
  revision/effective-view fingerprints, revision-local delta, complete typed
  transition inventory, independent model-owner denominator/bindings, and any
  one-way bootstrap receipt;
- final claim: routine versus release/archive/publish scope and consuming Risk
  Evidence Ledger evidence.

For an explicitly triggered target blueprint, additionally capture the target
descriptor/profile, frozen layer plan, provider results/registry/snapshot,
applicable independent inventory, binding/topology, resource/intent/oracle,
model-test design/execution, normalized projection, and ordered qualification
identities.

Keep read-only WorkContext adapter/native/artifact/fingerprint ids distinct from
FlowGuard's own obligation, validation, execution, and receipt ids.

## Execution Shape

Use a staged plan, but do not make every diagnostic depend on the previous
diagnostic's success. Independent focused diagnostics should all report their
findings within the chosen boundary so one ordinary failure does not hide the
rest of the issue surface. A hard blocker stops descendants whose results
would be invalid, unsafe, or unauthorized; those descendants stay visible as
not run with a reason.

After the diagnostic boundary closes, relate findings, repair the primary
owner/root cause, and rerun only affected obligations. Repeat diagnosis only
when the repair or new material evidence changes the remaining boundary.

Ordinary changes consume the compact current blueprint identity through the
direct affected reader and invalidate only affected inventory/binding/resource/
intent/test/projection shards plus their declared graph neighborhood. They do
not first construct, rescan, serialize, or export the whole target. Full
inventory and qualification run only for an
explicit blueprint/export/qualification scope or a named release obligation.

Reserve broad full verification for a stable frozen integration snapshot.
Freeze source, toolchain, check inventory, dependencies, and exactly one owner
per heavy check. Run exactly one parent full-validation owner whose frozen
child-owner plan recomposes exact model/test leaf receipts; receipt consumers
project its immutable success and do not rerun producers.

Inside that one bounded owner invocation, construct one complete immutable
validation observation after the owner plan is frozen. Resolve and semantically
verify each exact-current child once, then let sibling rows and aggregates
consume exact subsets of that same observation. After all native producers
terminate, make one fresh governed source/dependency/toolchain/environment/owner
comparison. Publish every newly executed leaf from those exact fresh owner
contexts without rebuilding source currentness or scanning the receipt store
per leaf. Reconcile the content-addressed leaf identities once, then complete
the parent boundary without a third repository scan. Matching identities
authorize reuse of the already verified objects; they do not justify repeating
native semantic verification. Any drift blocks the whole candidate operation,
and an omitted final source comparison or receipt reconciliation is `not_run`.
Never persist this observation as a cache, receipt alias, alternate store, or
cross-invocation authority.

Before execution, freeze the complete native owner inventory and derive one
deterministic plan whose rows are only `execute`, `reuse_current`, or
`blocked`. Missing or valid-stale proof executes only its declared owner;
independently verified exact-current terminal-pass proof is reused. Unknown
ownership, damaged or conflicting proof, or a live exact execution lease
blocks before any producer starts. Plan-only creates no output, lease, receipt,
run manifest, or current pointer. Persist each successful child before parent
composition so sibling or parent failure does not force it to execute again.

If a launcher times out or is interrupted, confirm that its descendant process
tree is gone before accepting evidence or starting another owner.

## Per-Model Path-Quality Lifecycle

Freeze one affected-model denominator for every new or materially changed
model. For each member, order exact actions and dependencies as:

1. model owner and complete effective-intent closure;
2. ModelMaturation's lightweight path-quality review;
3. ModelMaturation's deep review only when exact current trigger evidence
   exists;
4. behavior-sensitive implementation, if authorized;
5. affected validation;
6. one candidate `ModelRevisionSet`; and
7. compare-and-swap activation of that same compact result.

Each review, candidate, and activation row carries one exact compact result
fingerprint per model. A current `single_clear_path` result proceeds from step
2 without candidate expansion or deep ceremony. A deep-triggered model cannot
cross the corresponding implementation or activation claim until the finite
deep result closes. If a model, implementation, binding, test, oracle,
provider, dependency, intent, obligation, or evidence input changes after a
review, stale and minimally refresh that affected model; then refresh triggered
deep evidence before candidate/activation. Exact unchanged rows may reuse
current results.

ModelMaturation decides path quality; DPF checks only denominator, order,
fingerprint currentness, invalidation, and affected validation. Keep faithful
`observed` behavior separate from a cleaner `normative_target`, and keep user
execution choice separate from verified understanding and admission. The
ordinary lifecycle contains no reconstruction phase. Reimplementation,
language translation, or empirical reconstruction appears only when the user
explicitly requests that target outcome and never substitutes for static
closure, model-path evidence, or ordinary validation.

## Freshness And Sync

Peer or unknown-writer changes are preserved. Re-read and merge them, stale
only affected evidence, and derive affected revalidation; never roll back peer
work to recover an older green snapshot.

Progress logs, PIDs, heartbeats, and running states prove liveness only. Final
evidence requires terminal status, exit code, concrete result artifact and
fingerprint, covered ids, inventory revision, and current artifact/verifier
versions.

When distribution or release identity is in scope, load
`distribution_release_protocol.md`. DevelopmentProcessFlow consumes the typed
owner evidence and orders gates; it never owns suite inventory or installation
semantics.

## Read-only WorkContext

Read external requirements, plans, designs, tasks, status, and history only
through explicitly registered, project-bounded WorkContext adapters. Preserve
adapter id, native owner/work id, artifact roles/ids/source refs/fingerprints,
subject lane, and context fingerprint. FlowGuard may use that material to
understand scope and order its own work.

It must not write provider artifacts, execute provider checks, open sessions,
create caches or receipts, claim provider execution ownership, or fan one
provider status into FlowGuard evidence consumers. FlowGuard validations
remain ordinary FlowGuard validations with native owners/evidence, and every
provider retains its own lifecycle decisions.

## Failure Routing

Classify non-pass evidence before editing or rerunning. Ordinary defects may
use the ordinary repair path. Route oversized models to ModelMesh; layered,
slow, hidden, or release-only validation to TestMesh; obligation/code/test
mismatch to Model-Test Alignment; new post-green behavior misses to Model Miss
Review; anchored future-use hazards to Model Topology Hazard Review; UI or
payload evidence changes to their native owners.

A later green command does not close a specialist handoff by itself. The
specialist must produce current evidence and the parent process must consume
its id.

## Hard Gates

- Use the real FlowGuard check engine and managed project record; never create
  a substitute mini-framework.
- Keep sibling semantics, provider authority, product behavior, and test
  execution with their native owners.
- Failed, skipped, timeout, not-run, running, stale, progress-only, or hidden
  evidence cannot satisfy a current requirement.
- A cheaper route is eligible only after outcome, obligation/evidence, safety,
  protected side effect, dependency authority, and execution-owner authority
  are equal.
- Compare hard-equivalent process candidates by current named cost dimensions
  with Pareto dominance. Missing values are not zero; trade-offs/equality stay
  unresolved, and no scalar sum, caller tie-break, or global optimum is valid.
- Material new evidence stales the decision. A repair stays open until every
  affected obligation has current revalidation.
- A static blueprint result promoted beyond its exact provider and binding
  evidence is a hard claim-boundary failure.
- Broad done/release/archive/publish claims require current proof artifacts,
  current Risk Evidence Ledger closure, and all required freshness domains.

## Model-system activation and recovery

Treat current authority, target construction, experiment execution, activation,
and recovery as separate process states. A target or experiment never mutates
the observed head. Freeze `bootstrap` only for the explicit one-way legacy
migration; otherwise freeze `refine` against the exact current accepted
revision and complete effective-view fingerprint. Keep the revision-local delta
separate, require a complete typed retain/supersede/retire transition inventory,
independently derive the current model-owner denominator and bindings,
recompute the complete base/candidate and affected-closure diff, consume current
owner receipts, persist immutable records, then update the sole pointer last
under the shared project-manifest lock. Legacy current authority, missing
transition input, or an unlinked prior view is `blocked`, never an implicit
history/latest-delta fallback.

Before operational rollback, require a new current-schema reverse revision
whose effective-intent base fingerprint equals the presently accepted view;
rolling back toward a pre-current-schema snapshot still reconstructs that
target state in the current schema and never revives a legacy reader. Then
restore or compensate declared code, data,
configuration, migration, and external effects and rerun old-snapshot
conformance. Exact rollback is allowed only when every effect is restorable;
compensation must remain visible; irreversible effects route to forward repair.
Timeout, cancellation, stale head, or missing restoration evidence blocks the
pointer update.

## Output

Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`,
`claim_boundary`, `typed_next_actions`, selected modes, freshness status, and
required affected revalidation. Include process-optimization details only when
the mode is active. A diagram should show order, invalidation, hard stops, and
required revalidation rather than decorative detail.

For machine-facing validation, write the complete report to an immutable
artifact and return a compact terminal envelope. Successful child payloads and
stream tails stay out of the terminal envelope; failed, blocked, and skipped
child identities remain visible with the artifact path and content hash.

## Completion

The process claim is supported only when references and owners resolve,
evidence covers current artifact/verifier versions, specialist handoffs are
reattached, skipped/not-run work remains visible, peer changes are preserved,
required synchronization domains are current, and the requested claim scope
has terminal proof. Otherwise return blocked or explicitly scoped confidence.

For blueprint scope, report static readiness, identity, depth, and gaps.

## Implementation Admission

When production work is requested, consume one independently verified current
`VerifiedModelMaturation` produced from a canonical EvidenceReceipt and
separately decide `ready`, `ready_scoped`,
`no_code_requested`, `blocked`, or `stale`. Normal `ready` requires
closed-for-task full confidence with no open gaps. `ready_scoped` additionally
requires a current authorization matching task, candidate, coverage, input,
evidence, accepted gap set, and every requested action/artifact/path.

Authorization never changes the maturation decision or hides gaps. It cannot
waive unavailable real tooling, destructive or irreversible ambiguity, active
owner conflicts, or other declared non-waivable blockers. Any later task,
candidate, coverage, evidence, request-scope, or owner change stales admission.

## Blueprint Layer Lifecycle

For explicit whole-target scope, first qualify the frozen profile-matching layer
plan, provider results/registry, and target snapshot, then track exact identities
and freshness for every ordered plan layer. The canonical software plan uses
implementation inventory, traceability, independent semantics, model-code-test,
resource/intent/oracle, and final static qualification; a non-code workflow uses
its real workflow layers without fabricated software rows. Native specialists retain layer semantics;
DevelopmentProcessFlow sequences producers, consumes receipts, invalidates
affected edges, and reports status without rescoring them.
Software specialization embeds the complete `ProjectTestInventory`; every
consumer load requires its independent current-test-source audit before any
test-inventory or `model_code_test` freshness claim.

Return `deepest_proven_layer` as the longest exact-current complete prefix and
the first unresolved native owner/member/evidence gap. Missing, duplicate,
ambiguous, stale, or unknown-impact ownership blocks; never substitute the
FlowGuard self-model, authoritative root, unrelated route, generic catchall, or
run-all. A later layer cannot hide an earlier incomplete one.

Whole-target materialization/final qualification needs an explicit
blueprint/export/qualification task fact or named release/self-qualification
obligation. Ordinary implementation consumes the current blueprint identity
and revalidates affected layers plus declared graph neighbors only.

Keep `user_execution_choice`, `verified_model_maturation`, and
`implementation_admission` as separate state machines and identities.

Track exact fingerprints for the behavior report, resource inventory, intent
inventory, normalized projection, and readiness report.
After a normal change, invalidate only affected blocks/shared objects and load
their verified neighborhood directly from the normalized index. Before release cleanup, consume the read-only
self-architecture-reduction review bound to the same self blueprint; route
only proof-ready candidates into StructureMesh and leave `risky_keep` visible.
Cleanup never authorizes deletion by size or similarity alone.

## Release order for portable DNA changes

Use affected and compact blueprint reads while behavior is changing. After the
functional implementation and one consolidated ArchitectureReduction/
StructureMesh review, freeze OpenSpec, model authority, skill projections,
installation, and version identities. Only then run the one supervised final
parent. A portable export records static, portable, and execution statuses; it
does not replace final validation.
