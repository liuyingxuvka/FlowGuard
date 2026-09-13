## 1. Canonical BCL authority

- [x] 1.1 Add the typed independent behavior inventory item, inventory, and
  reconciliation report to `flowguard.behavior_commitment`.
- [x] 1.2 Include stable identity/fingerprint, public surface, intent,
  success, error, recovery, owner, disposition, discovery evidence, and claim
  boundary fields.
- [x] 1.3 Add canonical modeled, delegated-to-named-owner,
  explicitly-out-of-scope-with-reason, and blocked-gap dispositions while
  keeping historical BCL source-surface values separate.
- [x] 1.4 Integrate optional inventory review and the explicit completeness gate
  into `review_behavior_commitment_ledger` without creating a second authority.
- [x] 1.5 Add the bounded native-manifest materializer that resolves only
  explicitly declared source paths and computes current source fingerprints;
  it must reject test/BCL source derivation and never infer behavior ids.

## 2. Serialization and public route

- [x] 2.1 Extend exact current BCL payload round-trip and the legacy artifact
  upgrader defaults.
- [x] 2.2 Update the canonical adoption ledger and public template with a
  null/false opt-in inventory boundary.
- [x] 2.3 Export the inventory types, constants, validator, and route starter
  entries through the existing BCL public module.

## 3. Focused evidence

- [x] 3.1 Add tests for valid independent round-trip and fingerprint identity.
- [x] 3.2 Add conservation tests for missing, unexpected, and duplicate ids.
- [x] 3.3 Add disposition tests for named delegation, explicit scope, modeled
  owner, and blocked-gap failure/visibility.
- [x] 3.4 Run focused BCL, inventory, and public-template tests.
- [x] 3.5 Populate the current native public-behavior inventory from the
  discovery owner. The current manifest records its complete declarable
  surface classes, finite behavior domains, explicit intent adjudications, and
  exact source boundary; it remains independent from BCL rows, tests, and
  implementation discovery.
- [x] 3.6 Add the fail-closed public-surface gap report. Count explicit
  production API/CLI/template/console declarations and source fingerprints,
  preserve zero generated behavior rows, and license the complete claim only
  when the authored manifest covers every class with current authority.
- [x] 3.7 Add focused gap-report tests for both a scoped/incomplete fixture and
  the current complete manifest; verify declaration names never generate
  semantic rows and a current-authority blocker remains visible.
- [x] 3.8 Run broader model, full/resume, release, and explorer/model-revision
  validation only under the parent task's frozen identity and ownership.
- [x] 3.9 Upgrade the independent inventory to the current v2 schema with
  explicit intent provenance/disposition, model/function/route/test/oracle
  links, failure/recovery cases, and a complete lifecycle envelope; reject v1
  directly and cover missing-link/lifecycle negative cases.

## 4. Reverse implementation-surface closure

- [x] 4.1 Add a bounded, production-source-only implementation surface
  discovery adapter. It records stable surface ids, source spans, source and
  surface fingerprints for Python modules/functions/classes, exports, API
  declarations, CLI commands/entrypoints, templates, configuration files,
  effects, faults, recovery calls, placeholders, installation boundaries, and
  UI-like actions, with a finite normalized surface class. It does not import
  the target or derive rows from models or tests.
- [x] 4.2 Add the independent reverse map review with typed
  `governed`/`internal_proven`/`retired_proven`/
  `not_applicable_proven`/`blocked_gap` dispositions. Missing mapping, owner,
  intent/model owner, test reference, terminal receipt, stale source identity,
  orphan test/receipt, unknown model obligation, and unmodeled UI-like action
  remain blockers. Internal, retired, and N/A rows require typed proof.
- [x] 4.3 Add reverse model-obligation to implementation-surface conservation,
  package/script exports, bounded discovery budgets, deterministic fingerprints,
  and mutation-negative tests for missing rows, owners, tests, obligations,
  stale source, and orphan test references.
- [x] 4.4 Partition a source boundary whose single observation would exceed the
  hard 5,000-row bound into a frozen, content-addressed source-path plan.
  Execute each child independently and merge only a complete, non-overlapping,
  current shard set; missing, duplicate, foreign, stale, or over-budget shards
  remain blockers.
- [x] 4.5 Add a source-only call-graph observation and explicit
  unreachable_or_unbound rows. Recompute reachability over the merged
  boundary so cross-shard callers are not mistaken for dead code. Dynamic,
  plugin, and external-entrypoint surfaces receive explicit current boundary
  identities and still require an independently authored surface disposition;
  discovery never invents semantic coverage.
- [x] 4.6 Add deterministic reverse-map negative coverage for zero mapping,
  duplicate/unknown/orphan references, empty test targets, missing terminal
  receipts, and mismatched normalized surface classes; preserve a visible
  blocked status for each mutation.
- [x] 4.7 Close the two-way surface contract explicitly: every observed
  surface maps to intent/model/obligation/test/owner/receipt, every governed
  model obligation maps back to a current surface, and typed proof rows are
  validated without treating a model-only row as implementation coverage. A
  current model obligation that the target owner cannot yet prove remains an
  explicit `blocked_gap` row with no surface binding; it must not be relabeled
  `model_only_proven`. The current source-only discovery, independently
  authored semantic map, current identity join, and terminal receipts now close
  the full product boundary; any identity change requires direct-current
  re-authoring rather than predecessor inheritance.
- [x] 4.8 Close the merged call-graph observation boundary: preserve every
  child-observed module/class/function call edge, recompute cross-shard target
  resolution from that complete edge denominator, and add full-vs-merged
  regression tests plus current terminal evidence.
- [x] 4.9 Close every dynamic, external, and finite-dispatch call edge with a
  deterministic current target identity; remove the unresolved ambiguity and
  unknown resolution vocabulary, add validation for boundary ids and dispatch
  sets, update full/merged tests, and regenerate current semantic evidence.
- [x] 4.10 Replace boundary-only dynamic observations with explicit current
  external-contract identities, conserve the contract registry in full and
  merged discovery, and re-author every previously typed dynamic/plugin/
  unreachable/placeholder row to a current governed, internal, or retired
  disposition. No `ambiguous`, `unknown`, legacy boundary resolution, or
  typed N/A remains in the current reverse closure.
- [x] 4.11 Add the persistent reverse-surface owner authority. Keep one exact
  current receipt per persistent owner route, independent of delta-local model
  revision evidence; bind its discovery, owner-bindings, model-parent, model
  child receipts, and active authority identities; replace matching delta-local
  identities in the reverse join instead of appending duplicates; reject stale,
  missing, duplicate, or foreign receipts; and cover the replacement rule with
  negative/positive tests and a current 14,864-surface reverse audit.
