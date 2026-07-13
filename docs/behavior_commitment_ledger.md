# FlowGuard Behavior Commitment Ledger

Behavior Commitment Ledger is the full behavior account book for a project,
work package, or release boundary.

In plain language: before an AI says a feature, project, release, UI flow, CLI
command, skill, or workflow is covered, the ledger asks, "What exact external
behaviors are promised, where did those promises come from, and which model is
the one primary owner for each one?"

## What Counts As A Commitment

A commitment is an external, verifiable promise. Examples:

- a public API or CLI command behavior;
- a UI capability users can perform;
- a documented workflow;
- a skill or agent workflow behavior;
- a release, archive, publish, or process behavior that downstream work relies on.

A commitment is not every helper function, private class, implementation file,
internal field, or model. A model proves a commitment; it is not automatically
the whole feature inventory.

## Execution Plane And Actor

Every production commitment is classified exactly once by who owns the
behavior:

| `behavior_plane` | Plain meaning | Typical `actor_kind` |
| --- | --- | --- |
| `product_runtime` | The application promises an external result. | `end_user`, `external_system`, `application` |
| `agent_operation` | The current AI agent operates tools to complete work. | `ai_agent` |
| `development_process` | Development, validation, installation, archive, publish, or release is governed. | `developer`, `automation` |

`commitment_kind` still describes the form (`ui`, `cli`, `workflow`, and so
on); it does not answer who owns the behavior. Product software that itself
contains an AI feature remains `product_runtime`. `agent_operation` is for the
Codex/development agent operating the project.

## Change Modes

Before editing or claiming behavior coverage, classify the ledger work:

- `bootstrap_ledger`: no baseline ledger exists, so the AI investigates README,
  docs, API/CLI, skills, templates, spec-tool records, issues, changelog, and
  historical traces.
- `add_behavior`: a new external behavior is added.
- `change_behavior`: an existing behavior changes.
- `remove_or_replace_behavior`: old behavior is removed, deprecated, or
  replaced; no old or alternate surface is left as a second success path.
- `coverage_gap_backfill`: a historical external behavior was visible but not
  registered.
- `model_miss_check`: a runtime/test/replay/manual failure after a green claim
  triggers a check for missing or stale behavior registration.

## Canonical Ledger And Relations

The project source of truth is the machine-readable
`.flowguard/behavior_commitment_ledger/ledger.json`. The adjacent `model.py` is
a thin loader/check adapter and `result.json` is run evidence; neither is a
second behavior inventory. Use `load_behavior_commitment_ledger()`,
`write_behavior_commitment_ledger()`, and
`behavior_commitment_ledger_fingerprint()` at tool boundaries.

Commitments connect through typed `BehaviorCommitmentRelation` rows:
`depends_on`, `invokes`, `validates`, `governs`, or
`requires_evidence_from`. Cross-plane relations need a reason and never move
the target commitment into the source plane. Legacy
`dependency_commitment_ids` is migration-only input; normal runtime rows use
typed relations and do not retain an old successful authority path.

## What The Ledger Checks

The ledger checks both directions:

- every in-scope source surface maps to one or more commitments;
- every in-scope commitment maps back to source evidence or source surfaces.

It also checks:

- missing expected commitments;
- extra invented commitments with no source;
- changed, missing, or unchecked source surfaces;
- one primary owner model per commitment;
- stale owner-model/sibling/child-model review;
- replaced or deprecated behavior without disposition;
- TestMesh shards that are stale, missing, progress-only, or release-only;
- model-miss backfeed that does not map to an existing commitment, owner model,
  and same-class/DCAR coverage;
- supporting or child models that accidentally overlap the primary owner;
- unknown relation targets, invalid relation types, disallowed cross-plane
  relations, or cross-plane relations without a rationale;
- scoped-out behavior without owner, reason, validation boundary, and rationale;
- broad claims without current evidence or risk gates.

The same exact external intent has one stable `business_intent_id` and one
active commitment. Surface shape is not identity: a page button, menu item,
API, CLI, alias, adapter, wrapper, or compatibility facade maps to the same
commitment when actor, preconditions, expected terminal, failure boundary,
material state writes, and side effects are the same. A separate intent needs
a typed external difference, owner, validation boundary, rationale, and
current evidence. A thin delegating surface never receives a second
"delegate commitment."

## Lookup Binding And Read-Only Query

`BehaviorLookupBinding` stores bounded recall clues: task terms, path patterns,
tool ids, error signatures, and workflow families. Lookup selects one primary
plane before scoring. Only same-plane hits can guide the current operation;
typed related hits are shown separately as invoked targets, validation targets,
governing processes, or evidence sources.

```powershell
python -m flowguard behavior-commitment-query "start the UI test and check the port bridge" --root . --plane agent_operation --term port_bridge --json
```

The output includes deterministic match reasons, relation roles, ambiguity or
fallback status, and the canonical ledger fingerprint. This is explainable
recall, not a runtime supervisor: it does not execute commitments, force every
ordinary action through FlowGuard, or guarantee future AI compliance.

## How It Connects To Primary Path Authority

The ledger is upstream. Primary Path Authority is downstream.

Use this rule:

```text
Behavior Commitment Ledger
-> path_sensitive=true commitment
-> Primary Path Authority
-> no automatic A failed -> B succeeded path
-> TestMesh shards + Risk Evidence Ledger gates
```

The ledger should not recreate alternate-path detection. If a behavior is
path-sensitive, attach PPA evidence with
`behavior_path_binding_from_primary_path_report()`. If PPA blocks, the ledger
blocks that commitment and any broad claim depending on it.

The current binding emits one `primary_path_id`. Legacy `primary_path_ids`
input is accepted only when it contains one distinct non-empty value and does
not conflict with the singular value. Empty, multi-path, or conflicting input
is an ambiguity blocker rather than a list-order selection rule.

## Public API Shape

Core objects:

- `BehaviorCommitmentLedger`
- `BehaviorSourceSurface`
- `BehaviorCommitment`
- `BehaviorEvidenceBinding`
- `BehaviorExternalDifference`
- `BehaviorLookupBinding`
- `BehaviorCommitmentRelation`
- `BehaviorPathAuthorityBinding`
- `BehaviorLookupQuery`
- `BehaviorCommitmentHit`
- `BehaviorLookupReport`
- `review_behavior_commitment_ledger()`
- `query_behavior_commitments()`
- `query_behavior_commitments_from_path()`
- `load_behavior_commitment_ledger()`
- `write_behavior_commitment_ledger()`
- `behavior_path_binding_from_primary_path_report()`
- `behavior_commitment_contract_exhaustion_plan()`

Template:

```powershell
python -m flowguard behavior-commitment-ledger-template --output <target>
```

## Broad Claim Rule

For done, release, publish, archive, production, or full-confidence claims, use
current ledger evidence plus downstream evidence:

- ContractExhaustionMesh commitment coverage cases;
- TestMesh child shard ownership;
- Model-Test Alignment bindings to model obligations, code contracts, tests,
  and commitment ids;
- Risk Evidence Ledger gates;
- PPA evidence for every `path_sensitive=true` commitment.

If the ledger says behavior is missing, extra, overlapping, stale, or
PPA-blocked, repair the root commitment, owner model, evidence, or primary
path. Do not add a second runtime path as a workaround.

## Model Miss Backfeed

A model miss does not automatically mean a new feature exists. First classify
which execution plane's promise failed, then search that plane for an existing
commitment and owner model. If the commitment exists, repair the model, code
contract, tests, evidence, lookup error signatures, and DCAR/same-class
coverage under that commitment. Create or backfill a gap only when the
external behavior was never registered in the affected plane. Other planes
remain typed incident context and do not take over ownership.
