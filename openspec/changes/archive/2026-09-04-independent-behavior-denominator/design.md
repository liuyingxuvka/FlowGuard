## Context

BehaviorCommitmentLedger is already the current BCL authority and already
records independent source-surface identity. `CurrentEffectiveIntentView`
remains the authority for model intent ownership, but it does not contain the
public surface and outcome details needed for an externally observable
behavior denominator. A parallel inventory authority would reproduce the
existing split, so the smallest safe extension is a typed child payload on the
current BCL ledger.

## Decisions

1. `BehaviorInventory` is supplied by a native discovery owner. The caller
   provides the exact expected id list, discovery revision, source fingerprint,
   evidence ids, and claim boundary. The validator never infers the expected
   set from commitment rows, test names, or the materialized item list.
   `scripts/discover_behavior_inventory.py` is only a bounded manifest
   materializer: it resolves the manifest's declared source files and computes
   their fingerprints; it is not a semantic scanner or an automatic behavior
   discovery engine.
2. `BehaviorInventoryItem` carries the immutable behavior identity and the
   minimum external contract needed for later model/test alignment: source
   kind/ref/fingerprint, public surface, intent, success, errors, recovery,
   owner, and disposition.
3. Inventory disposition names are canonical and explicit:
   `modeled`, `delegated_to_named_owner`,
   `explicitly_out_of_scope_with_reason`, and `blocked_gap`. Existing BCL
   `delegated` and `scoped` values remain separate source-surface values and
   are not accepted as inventory dispositions; the existing source-surface
   BCL constants and semantics remain unchanged.
4. The inventory validator performs set conservation over expected ids and
   materialized rows, rejects duplicate expected/materialized ids, rejects
   reuse of the BCL ledger identity or fingerprint as discovery authority, and
   checks each disposition's owner handoff fields.
5. The BCL reviewer validates an attached inventory whenever present. A
   missing inventory blocks only when
   `require_complete_behavior_inventory=true`; this keeps current adopters
   loadable while making the activation boundary explicit for the parent audit
   and the eventual native discovery owner.
6. Serialization includes schema and content fingerprints and is strict for
   current payloads. Legacy BCL mappings are upgraded through the existing
   artifact-upgrade owner with empty/false inventory defaults; no compatibility
   reader or second authority is added.
7. A separate native public-surface audit emits
   `flowguard.public_behavior_surface_gap.v1`. It may inspect explicit
   production declaration registries and source identities, but it does not
   derive `BehaviorInventoryItem` rows from API names, parser names, tests, or
   model artifacts. Its current result is a visible blocked gap report until
   every declarable surface class has independently authored semantic rows and
   current authority evidence.
8. The reverse implementation audit is a source observation plus an
   independent author map. The source adapter is bounded to production roots
   and deterministic limits, emits stable surface ids/spans/fingerprints, and
   records code/API/export/CLI/template/config/effect/fault/recovery/
   placeholder/UI-like/install observations plus one finite `surface_class`.
   The map carries the typed `governed`, `internal_proven`, `retired_proven`,
   `not_applicable_proven`, or `blocked_gap` disposition. Every non-blocked
   row cites a current terminal receipt. Review performs both
   surface-to-intent/model/obligation/test/owner/receipt and
   model-obligation-to-surface conservation; empty tests, zero mapped rows,
   unknown/orphan references, and missing typed proof remain blockers. It
   never promotes a model or test name into a discovered surface. The merged
   shard owner consumes each child call-graph observation as the complete
   call-site denominator, including module and class-body callers; it does not
   reconstruct calls only from surface-row facts that intentionally omit
   module-level aggregates. A merged source observation is terminal when
   source paths, rows, call-site edges, and target identities are current and
   conserved. A finite source candidate set is represented as
   `resolved_static_dispatch`; dynamic or external expressions receive a
   deterministic current external-contract id. No unresolved ambiguity/unknown
   or boundary-only resolution is emitted;
   structural, stale, orphan, or missing-edge findings remain blockers.

## Verification

- Focused inventory tests cover valid round-trip, conservation failures,
  disposition handoff failures, identity independence, and the blocking gate
  for an opted-in missing denominator.
- Existing BCL ledger and public-template tests cover unchanged historical
  source-surface semantics and canonical current payload loading.
- OpenSpec validation is run for this change only. Full/resume/release and
  broad model or explorer validation are outside this bounded package.
