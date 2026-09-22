# Public lifecycle request contract

The only public lifecycle entrypoints are `read`, `change`, and `release`:

```powershell
python -m flowguard read --root <project-root> --request read.json --json
python -m flowguard change --root <project-root> --request change.json --json
python -m flowguard release --root <project-root> --request release.json --json
```

Every request file is an ordinary JSON file below `--root`. The dispatcher
uses only the explicit operation and root in that request. A malformed request
is blocked before any owner producer starts; there is no legacy command,
compatibility reader, or fallback validator.

## `read`

The exact request object is:

```json
{
  "operation": "read",
  "target_id": "planning-tool",
  "scope": ["model:absence-record-lifecycle"]
}
```

`scope` is a non-empty array of unique model ids. `read` validates the actual
observed current head, selected model identities, source freshness, and typed
relations. It never runs an owner, writes a receipt, creates a head, or repairs
an old source. Its result reports `producer_count: 0`,
`execution_evidence_status: "not_run"`, and the exact `as_of` head/snapshot
fingerprints.

If the target has no `[model_authority]` section, the result is blocked with
`reason: "current_model_missing"`, `current_authority: "missing"`, and
`producer_count: 0`. This is the explicit first-current bootstrap state; it is
not a successful model read and it does not run a producer.

## `change`

The exact top-level request object is:

```json
{
  "operation": "change",
  "target_id": "planning-tool",
  "scope": ["model:absence-record-lifecycle"],
  "expected_current": null,
  "bootstrap": true,
  "revision_input": {
    "path": "reports/flowguard/revision-preparation.json",
    "sha256": "<64 lowercase hexadecimal bytes hash>"
  }
}
```

For an existing current head, set `bootstrap` to `false` and set
`expected_current` to the exact current head fingerprint. The preparation file
must have the exact `flowguard.revision_preparation.v1` fields below:

```json
{
  "schema": "flowguard.revision_preparation.v1",
  "target_id": "planning-tool",
  "base_head_fingerprint": null,
  "snapshot_id": "snapshot:planning-tool-v13-1",
  "revision_set_id": "revision:planning-tool-v13-1",
  "task_id": "task:planning-tool-v13-1",
  "decision_reason": "<bounded reason for this revision>",
  "intent_contributions": [],
  "intent_dispositions": [],
  "effective_intent_transitions": [],
  "removal_dispositions": [],
  "current_design_intent_contributions": [],
  "accepted_boundary_contract_ref": null,
  "bootstrap_staging_root": ".flowguard/work/bootstrap/<request-id>"
}
```

The bootstrap shape requires `base_head_fingerprint: null`, an existing
non-symlink staging directory under `.flowguard/work/bootstrap/`, and non-empty
`current_design_intent_contributions`. It contains no current-revision
transitions. The activation receipt identity is generated from the accepted
read-projection index; callers never provide it. The existing-current shape
requires the opposite boundary: `base_head_fingerprint` must equal
`expected_current` and `bootstrap_staging_root` must be `null`.

For either shape, the dispatcher freezes the request and source identities,
runs the declared native model owners, retains their leaf and parent evidence,
builds the accepted `ModelRevisionSet`, and only then attempts the authority
compare-and-swap. Missing candidates, wrong source hashes, failed native cases,
missing leaf evidence, stale expected heads, and CAS conflicts block
acceptance. A failed change may retain diagnostic evidence, but it cannot move
the observed current pointer.

## `release`

The release request references a separately hashed contract:

```json
{
  "operation": "release",
  "target_id": "planning-tool",
  "scope": ["model:absence-record-lifecycle"],
  "expected_current": "sha256:<current-head-fingerprint>",
  "release_contract": {
    "path": "reports/flowguard/release-contract.json",
    "sha256": "<64 lowercase hexadecimal bytes hash>"
  },
  "artifact": null
}
```

The contract schema is `flowguard.release_contract.v1` and contains exactly
`required_model_ids`, `required_check_ids`, `required_source_paths`, and
`artifact_members` in addition to `schema` and `target_id`. `release` only
qualifies already accepted local current source and an explicitly declared
artifact. It does not install, tag, push, or publish.

## Evidence boundary

`read` is an as-of navigation result. `change` is the only lifecycle operation
that executes native owners and can accept a new current authority. A passing
transport result is not a substitute for the native owner receipts, accepted
revision, source identity, or target-specific business validation represented
by the request. Historical heads and receipts may explain provenance, but they
are never copied as current evidence.
