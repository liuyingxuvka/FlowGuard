# Behavior Commitment Ledger Protocol

Use the ledger against an upstream expected-source inventory that was derived
independently of the ledger candidate. Source surfaces come from declared
WorkContexts, native UI observed-surface inventories, native field inventories,
APIs, commands, skills, tests, release notes, process docs, or another bounded
discovery owner. Commitments are the external promises those surfaces make.

Discovery breadth follows the declared ledger mode. `bootstrap_ledger` and
`coverage_gap_backfill` require broad source discovery. `add_behavior`,
`change_behavior`, `remove_or_replace_behavior`, and `model_miss_check` stay
bounded to the affected commitment, its owner, and typed relations unless a
concrete unregistered external behavior is found.

The source inventory in this protocol is an external-promise inventory. It is
not the software-blueprint implementation inventory. Internal production
files, modules, symbols, helper calls, implementation dispositions, build
internals, and developer/user activity logs remain with their native target
model or independent implementation-inventory owner and must not be copied
into `ledger.json`.

Freeze the exact expected source ids, source-inventory revision/fingerprint,
and discovery evidence before assigning dispositions. Every expected source
has exactly one disposition:

- `modeled`: maps to exactly one active commitment;
- `delegated`: names one specialist owner, typed relation, and current native
  evidence without creating another commitment;
- `scoped`: records a bounded reason, owner, and validation boundary.

Missing, unexpected, duplicated, stale, or self-declared-only inventory rows
block broad coverage. Supporting, observed, and historical sources inform the
ledger but cannot displace a declared normative target.

Stored `freshness_state=current` is never source-currentness evidence by
itself. Resolve source references against one explicit project root with
`audit_behavior_commitment_source_inventory()`: strip a logical `#anchor` only
for physical file resolution, split semicolon composites, expand only globs
whose first wildcard follows at least one fixed directory segment, reject
absolute, escaping, escaping-symlink, root-level-glob, and duplicate-member
references, sort the resulting unique repository-relative POSIX member paths,
and hash every file with FlowGuard's canonical newline-aware source identity. A
one-file surface uses that file hash directly. A composite or glob surface uses
the versioned canonical member aggregate. The top physical inventory
fingerprint is derived from surface ids, authored source refs, sorted members,
and content identities only; ownership, authority role, artifact classification,
and declared semantic fingerprints remain separate authored semantics.

Use `refresh_behavior_commitment_source_inventory()` only as the explicit pure
refresh step after the authored source boundary is accepted. It returns a new
ledger and writes nothing; it preserves commitments, declared semantic
fingerprints, mappings, roles, and rationale while refreshing physical member
identity, content fingerprints, row/top inventory revision, discovery evidence,
and stored currentness. Writing the returned canonical ledger remains a
separate deliberate action.

The ledger has one structure and three production owner planes:
`product_runtime` for application promises, `agent_operation` for AI/tool-use
promises, and `development_process` for build/test/release lifecycle promises.
`commitment_kind` remains the surface form; `actor_kind` records the structured
actor. Migration-only `unclassified` never passes runtime review.

Use the canonical `ledger.json` as authority and a thin `model.py` loader. The
project-native owner must derive one live audit from the repository root and
combine it with the static ledger review so missing, unsafe, unbounded-glob,
empty-glob, anchor, duplicate-member, content, membership, and top-inventory
drift fail before a green result. An external caller that needs one integrated
report may pass `project_root` to `review_behavior_commitment_ledger()`; a
native runner that already holds a live audit must not scan the same inventory
again.
Before non-trivial work, query task terms and any exact commitment, path, tool,
workflow, or error-signature clues. Select same-plane hits as primary. Traverse
only registered typed relations for related-plane context, keep that context
separate from instructions, and preserve the ledger fingerprint. Ambiguous or
stale lookup is visibly blocked or unverified, not permission to guess.

Each commitment records actor, trigger, expected result, failure boundary,
source refs, one primary owner model, subordinate supporting or child models,
dependencies, evidence ids, validation boundary, and rationale. A scoped-out
row still needs owner, reason, validation boundary, and rationale.

For an existing modeled project, the ledger revision and every primary owner
used for current confidence must be bound into the observed model-system
snapshot. A ledger row pointing to an absent, target-only, experimental, or
retired model is an authority gap. Supporting models remain subordinate and
cannot silently replace an unavailable primary owner. A changed commitment,
owner, relation, state write, or side effect belongs in the affected closure
of the next whole-system revision set.

Runtime relationships use typed `relations`, not legacy dependency ids.
Same-plane dependencies/invocations/validations and the allowed agent/process
cross-plane directions must reference registered targets. Every cross-plane
relation needs rationale. Reverse context may be derived during lookup; do not
duplicate inverse rows or merge the two owners.

Identity is the exact external promise, not the surface name. Compare actor,
trigger/preconditions, expected result/terminal, failure boundary, and material
state writes/side effects. Give that promise one stable `business_intent_id`
and one active commitment. Equivalent UI, API, CLI, alias, adapter, wrapper,
helper, and compatibility surfaces map to it and delegate to the selected path;
do not create a second surface/delegate commitment. A distinct intent requires
typed external differences, an owner, validation boundary, rationale, and
current evidence.

For `path_sensitive=true`, attach Primary Path Authority evidence with
`behavior_path_binding_from_primary_path_report()`. The ledger does not run a
second path checker. If PPA is blocked, the commitment is blocked.

The canonical binding emits singular `primary_path_id` for the same intent and
commitment. Accept legacy `primary_path_ids` input only when it contains one
distinct non-empty id and does not conflict with a singular value. Never choose
authority by list order; ambiguity blocks broad confidence.

For broad done, release, publish, archive, production, or full confidence,
project the ledger through `behavior_commitment_contract_exhaustion_plan()`.
Pass generated case ids, shard ids, receipt ids, and risk gate ids to
Model-Test Alignment, TestMesh, and Risk Evidence Ledger.

For an explicit software-blueprint qualification, BCL contributes only its
current ledger fingerprint and exact external commitment/source/primary-path
ids plus unresolved external-promise gaps. The blueprint owner references that
handoff alongside the separately owned implementation inventory and binding
report. BCL does not discover internal implementation surfaces, decide their
terminal dispositions, prove source-independent behavior semantics, or export
blueprint shards.

For task-level maturation, emit a typed contribution containing only the
triggered task's independently frozen commitment/source/path coverage,
unresolved ledger or PPA gaps, native evidence identity, status, and
fingerprints. Preserve product roles and actors exactly as target-software
semantics; do not create FlowGuard-global end-user, administrator, developer,
or AI roles. The contribution informs the denominator but never declares the
whole task understood.

Ordinary ledger work remains in the affected commitment closure. The presence
of a whole-software blueprint does not turn `change_behavior` or
`model_miss_check` into broad discovery.
