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

The ledger is also not a user-account, persona, or permission catalog for the
target software. Product roles such as administrator, operator, customer, or
service account belong in that software's own behavior model. The ledger only
registers the externally verifiable promise and its one primary model owner.

The read-only understanding-status API and CLI are therefore registered as one
FlowGuard product promise, not as new target-software roles and not as an
activity log. Its two public surfaces share one intent and one model owner.

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

The ledger is one machine-readable file,
`.flowguard/behavior/inventory/ledger.json` by default. It is the behavior
inventory; it is not a second project map. Which code and models belong to
which component still lives in `.flowguard/map.json`. Use
`load_behavior_commitment_ledger()`, `write_behavior_commitment_ledger()`, and
`behavior_commitment_ledger_fingerprint()` at tool boundaries. The fingerprint
is a stable content identity: when it changes, lookups and reviews made against
the old fingerprint are stale and must be rerun.

The bundled template emits the complete current ledger shape. The loader
rejects omitted fields instead of filling them silently; update a producer
directly whenever the shape changes.

Commitments connect through typed `BehaviorCommitmentRelation` rows:
`depends_on`, `invokes`, `validates`, `governs`, or
`requires_evidence_from`. Cross-plane relations need a reason and never move
the target commitment into the source plane. Author typed relations directly,
then rerun the affected models and tests (`python -m flowguard change` lists
what to rerun).

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

```python
from flowguard import BehaviorLookupQuery, query_behavior_commitments_from_path

report = query_behavior_commitments_from_path(
    ".flowguard/behavior/inventory/ledger.json",
    BehaviorLookupQuery(
        "start the UI test and check the port bridge",
        primary_plane="agent_operation",
        canonical_terms=("port_bridge",),
    ),
)
print(report.format_text())
```

The report includes deterministic match reasons, relation roles, ambiguity or
fallback status, and the ledger fingerprint (`ledger_fingerprint`). This is explainable
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
-> TestMesh shards + risk gates
```

The ledger does not recreate alternate-path detection: a path-sensitive
behavior is reviewed by `review_primary_path_authority()` on its own plan.

## Public API Shape

Core objects:

- `BehaviorCommitmentLedger`
- `BehaviorSourceSurface`
- `BehaviorCommitment`
- `BehaviorEvidenceBinding`
- `BehaviorExternalDifference`
- `BehaviorLookupBinding`
- `BehaviorCommitmentRelation`
- `BehaviorLookupQuery`
- `BehaviorCommitmentHit`
- `BehaviorLookupReport`
- `review_behavior_commitment_ledger()`
- `query_behavior_commitments()`
- `query_behavior_commitments_from_path()`
- `load_behavior_commitment_ledger()`
- `write_behavior_commitment_ledger()`
- `behavior_commitment_contract_exhaustion_plan()`

Template (the ledger plus one contract model built with the behavior-commitment kit:
`add_commitment`, `retire_commitment`, `add_path`, `retire_path`, `behavior_commitment_explorer`,
`behavior_commitment_code_facts`):

```powershell
python -m flowguard template behavior-commitment            # print
python -m flowguard template behavior-commitment --write .  # write files
```

## Broad Claim Rule

For done, release, publish, archive, production, or full-confidence claims, use
a current ledger review plus downstream evidence:

- ContractExhaustionMesh commitment coverage cases;
- TestMesh child shard ownership;
- Model-Test Alignment bindings to model obligations, code contracts, tests,
  and commitment ids;
- risk gates (`risk_gate_ids` on each commitment's evidence);
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

Before the claim, `python -m flowguard map check` must show no stale
components for the affected code, and `python -m flowguard release` runs the
strict map check, lint errors, and all executable models.
