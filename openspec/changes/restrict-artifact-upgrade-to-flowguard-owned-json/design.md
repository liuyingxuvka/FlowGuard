## Context

`review_artifact_upgrades()` scans several ordinary project directories. Its
JSON classifier currently grants FlowGuard ownership when any mapping contains
a numeric-looking `schema_version`. That field name and value shape are not
FlowGuard-specific, so the classifier can write target-owned data that merely
shares the key.

The failure is a post-green model miss: v0.58.3 passed its project-upgrade and
release gates, but a real Khaos upgrade changed a canonical test fixture and
made Khaos's own evaluator fail closed. The repair must narrow the existing
project-adoption upgrade owner, not add a second scanner or a target-specific
exclusion.

## Goals / Non-Goals

**Goals:**

- Make one finite FlowGuard ownership classifier the authority for JSON
  handling.
- Bind exact current `report`/`trace` registrations to observation only, and
  bind the exact historical `56083c1e` bare behavior-ledger producer shape to
  the only JSON writer.
- Preserve unregistered JSON byte-for-byte regardless of path, producer label,
  `schema_version` value type, or coincidental envelope-like fields.
- Preserve the evidence-bound direct-to-current migration for the separately
  typed historical behavior ledger.
- Keep registered `report` and `trace` envelopes current-only: exact current
  shapes remain untouched, while malformed or unsupported versions block
  without writing.
- Prove the positive and negative branches in one real `project-upgrade` run.

**Non-Goals:**

- Add a Khaos-specific filename or directory exclusion.
- Infer ownership from `flowguard` name prefixes, scan paths, `created_by`, or
  numeric version syntax.
- Add a legacy reader, fallback parser, compatibility mode, alternate upgrade
  command, or target-project registration mechanism.
- Change target-owned JSON schemas or repair Khaos data.

## Decisions

### Exact in-package JSON migration registry

FlowGuard will keep one in-package registry keyed by exact `artifact_type`.
Every `report`/`trace` entry declares its complete producer field set, exact
field types, required values, and current versions. These registrations have
no writer. Separately, the behavior-ledger migrator accepts only the complete
bare `to_dict()` shape emitted by commit
`56083c1e47602654089e05701e9f5b42cce6c9a1`, including exact top-level, row,
source-surface, evidence, and path-authority field inventories and types. The
generic numeric `schema_version` predicate and the `created_by == "flowguard"`
shortcut cease to grant ownership.

An explicit registry is chosen over a prefix rule because prefixes establish
only naming resemblance, not ownership. It is chosen over a path allowlist
because FlowGuard artifacts may be stored in different project locations and
target-owned files can legitimately live inside scanned directories.

### Unregistered mappings are outside the migration result

After parsing a JSON mapping, the scanner will first check the separately typed
behavior-ledger shape, then resolve an exact artifact registration. If neither
matches, it returns no upgrade item and performs no serialization. Avoiding
serialization is necessary for byte and content-hash identity.

The scanner will not emit a compatibility warning item for unknown JSON.
Unknown target data is not an old FlowGuard artifact and therefore is not part
of FlowGuard's migration authority.

### Current-only envelopes plus one evidence-bound migration owner

The exact `report` and `trace` registrations describe current producer shapes;
they are not evidence of a historical migration. A matching current envelope
remains byte-identical. A malformed, old, future, or namespaced version blocks
without writing because no evidence-bound migrator exists.

The historical behavior ledger is separate. Its complete legacy shape and
dedicated migrator are backed by repository history, so it retains one
deterministic direct-to-current writer. Migration must materialize the complete
current canonical envelope through the current dataclass serializer before
writing; runtime defaults are not a compatibility reader. Every historical row
must already carry the upgrade-AI's explicit `migration_behavior_plane` and
`migration_actor_kind` disposition in its free-form legacy metadata. Text,
label, actor, owner, and commitment-kind heuristics never synthesize those new
semantics. Zero or one historical `primary_path_ids` is converted explicitly
at the upgrade boundary; multiple values block for an evidence-bound unique
disposition. Current, malformed, old, or future behavior-ledger envelopes are
never migration input: only an exact current canonical envelope is unchanged,
and every other declared BCL envelope blocks without writing. No generic
version-field writer, second reader, or alternate migration branch is
introduced.

The bundled public behavior-ledger template is a current producer, so it must
spell out the complete current canonical envelope rather than depend on
dataclass defaults during loading. Template execution and a direct canonical
round-trip test bind that producer to the strict current-only runtime contract.

### Model-miss closure at both public upgrade entrypoints

The existing `latest_schema_upgrade_policy` model owns direct
`artifact-upgrade`; it will gain exact-bounded-owner and target-owned JSON
cases.
The existing `project_adoption_version_gate` consumer model will gain an
artifact ownership/write state and a known-bad variant that treats numeric
schema syntax as authority. Both models will reject target-owned JSON writes,
and the executable regression will bind those invariants to the real
`upgrade_project()` owner code.

## Risks / Trade-offs

- [A historical FlowGuard artifact type has no evidence-bound migrator] → It
  remains untouched when unregistered, or blocks without writing when its
  exact declared current-only type is recognized. Add a migrator only with
  producer history, an exact old shape, and migration tests.
- [A target deliberately uses an exact registered FlowGuard artifact type] →
  The exact type declaration is treated as FlowGuard ownership; tests require
  the registered shape and field contract.
- [Formatting changes on migrated FlowGuard artifacts] → Only the dedicated
  behavior-ledger migration serializes a new current artifact; current
  envelopes and unknown artifacts are never serialized.
- [A future developer restores partial-ledger, prefix, producer-label, or
  numeric inference] → Direct artifact-policy and project-adoption known-bad
  checks plus byte/hash project-upgrade regressions fail.
- [A target mapping contains every historical required field plus target-only
  top-level or row fields] → Exact field equality excludes it from ownership;
  scanner and public migrator tests require zero writes.
- [A bundled producer omits new current fields] → Public-template execution and
  exact serializer round-trip fail; repair the producer directly rather than
  widening the runtime loader.

## Migration Plan

1. Add the exact registration boundary and remove generic ownership inference.
2. Add model and real project-upgrade negative/positive evidence.
3. Update versioned guidance and compile the maintained FlowGuard suite
   contract and consumer authority.
4. Run affected checks, one frozen final full gate, clean installation parity,
   GitHub CI, and the published verifier.
5. Publish v0.58.4 as a source-only release and hand its exact immutable commit
   to Khaos. Rollback before publication is the previous v0.58.3 tag; after
   publication a failed v0.58.4 identity is deleted and rebuilt, not supported
   by a runtime fallback.
