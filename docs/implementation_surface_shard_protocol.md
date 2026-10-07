# Implementation-surface shard protocol

FlowGuard's reverse implementation observation is source-only and bounded to
5,000 rows per child observation. A source tree that would exceed that bound
must be planned and merged as a complete shard set:

    plan -> discover each frozen shard -> verify/merge -> author reverse map

Example commands:

    python scripts/discover_behavior_surface_shards.py \
      --root . --mode plan --output .flowguard/structure/reverse-surfaces/current-shard-plan.json

    python scripts/discover_behavior_surface_shards.py \
      --root . --mode discover \
      --plan .flowguard/structure/reverse-surfaces/current-shard-plan.json \
      --shard-id implementation-surface-0000 \
      --output .flowguard/structure/reverse-surfaces/implementation-surface-0000.json

    python scripts/discover_behavior_surface_shards.py \
      --root . --mode merge \
      --plan .flowguard/structure/reverse-surfaces/current-shard-plan.json \
      --shard-file .flowguard/structure/reverse-surfaces/implementation-surface-0000.json \
      --output .flowguard/structure/reverse-surfaces/current-discovery.json

## Currentness profiles

The reverse audit has two explicit currentness profiles. `light` (the default
for ordinary use) checks the current source boundary once and reuses each
producer source identity when its recorded size and modification-time pointer
is unchanged; a changed or missing pointer is read exactly once and becomes a
new source fingerprint. `full` is the release-grade route: it rereads every
source file and replays the complete source-only producer. A direct discovery
is reproduced directly; a merged discovery is reproduced by rebuilding the
shard plan with its persisted `shard_max_rows`, discovering every planned
shard, and merging that exact set. The stored plan fingerprint, shard ids,
source identities, rows, call graph, counts, and final discovery fingerprint
must equal the replay. A caller cannot make an incomplete merged denominator
current by deleting rows and resealing its fingerprint. The light profile is a
performance projection, not a fallback reader and not a second authority; the
merged discovery artifact and its content fingerprint remain the only source
observation authority. Use `--profile full` for final full validation.

The merge command must receive every planned shard. A merged result records the
exact row bound used by its plan so a later currentness gate can reproduce the
same partition. It verifies the plan fingerprint and that each source still
matches the bytes used to create that plan, reads each source once per phase
for hashing and parsing, checks exact source-path conservation, rejects overlap,
foreign rows, duplicate surface ids, stale rows, missing call graphs, and
over-budget children. The merged call graph consumes the child-observed call
site denominator for module, class-body, and function callers, then recomputes
cross-shard target resolution from that complete set. A merged report is a
terminal source observation when its boundary, call-site rows, and target
identities are current. A finite source candidate set is emitted as
`resolved_static_dispatch`; dynamic or external expressions receive a
deterministic `contract:<kind>:<hash>` current external-contract id. No
unresolved ambiguity/unknown or boundary-only resolution is current;
missing/orphan/stale/structurally invalid edges remain blockers.

The merged `surface_count`, `component_grouped_surface_count`, and
`discovery_fingerprint` are the only current reverse-discovery denominator and
identity.  Do not copy a number from a dated audit, a predecessor map, or an
archived receipt into a current claim.  A source change creates a new
discovery fingerprint and the current map must be re-authored against that
new denominator; there is no fixed-count compatibility path.

Every child row and every merged row also carries one stable
`surface_class` from the finite code/API/CLI/UI-like/config/effect/fault/
recovery/install vocabulary. Merge-time recomputation (including the global
recomputation of `unreachable_or_unbound`) must preserve that class; an empty,
unknown, or kind/class-mismatched value is a merge blocker rather than an
implicit `code` fallback.

## Review granularity: rows are not source lines

The reverse observer records source spans so a reviewer can find the exact
implementation, but a span is only an anchor. It is not an intent row and it
does not create a requirement for every line, local variable, or private
helper.

Each observation is assigned a deterministic `review_group_id` and one of two
granularities:

* `surface` — an independently addressable CLI command/option, public API or
  export, UI-like action, configuration/artifact, effect, installer, fault,
  recovery, or other externally observable boundary. These remain individually
  reviewable because a user or consumer can encounter them independently.
* `component` — internal implementation observations grouped by their owning
  component. One component proof may cover the group only when every member is
  explicitly bound to the same current owner, intent, obligation, test and
  terminal evidence boundary. Grouping is not an inferred pass.

The map must still account for every observation. Unreachable or unbound
members remain `blocked_gap` until explicitly closed; call-boundary identity is
already closed by the discovery producer and cannot be hidden by grouping,
renamed as generic code, or silently inherited from an older map.

## Component-group authoring compression

The current reverse-map schema may use one explicit `component_groups` row for
an entire deterministic component group, but only when every member is an
ordinary `module`, `function`, or `class` observation. The row must list the
complete current `surface_ids` set and carries one shared intent/model/
obligation/test/owner/receipt binding. The validator expands the row back to
each member before checking the ordinary reverse-closure rules, so the
effective mapped-surface count never shrinks. Public/API/CLI/UI-like,
configuration, effect, fault, recovery, installation, dynamic, plugin,
placeholder, and unreachable/unbound observations remain individual rows.
An omitted member, overlapping group, or public member in `component_groups`
is a visible blocker; grouping is authoring compression, not semantic proof.

The observer records local source-only call-graph edges. Child-local
unreachable_or_unbound rows are discarded and recomputed after merge so a
callee referenced by a caller in another shard is not falsely classified as
dead. A function with no uniquely resolved local incoming edge and no explicit
export/API/console binding remains an unreachable_or_unbound observation.
Dynamic imports, reflection, plugin registration, and entry-point loading
remain explicit surface observations, while their call-site rows close to
deterministic dynamic/external boundary ids. The independently authored
reverse map must still close affected implementation surfaces as
blocked_gap or not_applicable_proven with current proof. Static discovery
never invents an intent, model owner, test, or terminal receipt.
