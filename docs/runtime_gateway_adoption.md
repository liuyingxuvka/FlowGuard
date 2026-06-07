# Runtime Gateway Adoption

Runtime Gateway Adoption is the FlowGuard review layer for projects that claim
FlowGuard protects real runtime state writes.

It answers a narrow question:

```text
Did every critical runtime state write path go through a declared
FlowGuard-backed gateway, with current inventory, boundary, step, replay, and
proof evidence?
```

## Adoption Levels

FlowGuard adoption has three practical levels:

| Level | Meaning | What it can claim |
| --- | --- | --- |
| `design_model` | A model exists and can guide design. | The model checked the declared abstract behavior. |
| `test_aligned` | Model obligations are compared with tests or code-boundary evidence. | Tests or observations support the declared obligations. |
| `runtime_gateway` | Critical runtime writes are forced through declared gateways and current evidence proves the known writer inventory. | FlowGuard is connected to the runtime mutation boundary for the declared state surfaces. |

Only `runtime_gateway` supports a claim that FlowGuard protects production state
mutation. The lower levels can still be useful, but their confidence must stay
scoped.

## Public API

```python
from flowguard import (
    ADOPTION_LEVEL_RUNTIME_GATEWAY,
    RUNTIME_WRITE_GATEWAY,
    RuntimeGatewayAdoptionPlan,
    RuntimeGatewayContract,
    RuntimeStateSurface,
    RuntimeWriteObservation,
    review_runtime_gateway_adoption,
)

plan = RuntimeGatewayAdoptionPlan(
    "flowpilot",
    target_level=ADOPTION_LEVEL_RUNTIME_GATEWAY,
    complete_inventory_evidence_ids=("inventory:critical-state-writers",),
    state_surfaces=(
        RuntimeStateSurface(
            "router_state",
            paths=("runtime/router_state.json",),
            owner_gateway_ids=("control_plane_gateway",),
        ),
    ),
    gateways=(
        RuntimeGatewayContract(
            "control_plane_gateway",
            managed_surface_ids=("router_state",),
        ),
    ),
    write_observations=(
        RuntimeWriteObservation(
            "router_state_write",
            "router_state",
            write_kind=RUNTIME_WRITE_GATEWAY,
            gateway_id="control_plane_gateway",
            step_contract_ids=("consume_controller_receipt",),
            code_boundary_ids=("control_plane_gateway.boundary",),
            proof_artifact_ids=("artifact:router-state-write",),
        ),
    ),
)

report = review_runtime_gateway_adoption(plan)
print(report.format_text())
```

## What Blocks Runtime-Gateway Adoption

The review blocks runtime-gateway confidence when:

- no complete writer inventory evidence is supplied;
- a critical state surface has no declared gateway owner;
- a gateway owner is unknown;
- a gateway does not require atomic commit or replay observation;
- a critical writer observation bypasses the gateway;
- a declared legacy bypass remains executable;
- a write goes through a gateway that does not manage the target surface;
- a gateway write lacks workflow step contract ids, code-boundary ids, runtime
  node ids, or proof artifact ids;
- a writer observation is stale, skipped, failed, timeout, not-run, running, or
  otherwise non-passing.

Use `RuntimeGatewayContract.runtime_node_ids` and
`RuntimeWriteObservation.runtime_node_ids` to bind critical state writes to the
runtime path evidence emitted by the real code. This keeps gateway progress
output tied to the FlowGuard model node it is supposed to prove.

Declared bypasses are not silently accepted. They stay visible as blockers for
`runtime_gateway` until the project removes or gates them.

## Relationship To Existing Helpers

Runtime Gateway Adoption consumes evidence produced by other helpers:

- Workflow Step Contracts explain which ordered step and receipt a write
  belongs to.
- Code Boundary Conformance explains whether observed code behavior stays
  inside a declared model boundary.
- Conformance Replay or equivalent runtime observation explains what actually
  happened in a real or replayed run.
- Proof artifacts bind evidence rows to concrete result files and
  fingerprints.
- DevelopmentProcessFlow and the Risk Evidence Ledger consume the final report
  before broad done, release, or production-confidence claims.

Code-boundary conformance alone does not prove runtime gateway adoption. It
shows a boundary observation stayed within a declared behavior surface; it does
not prove every critical write path was inventoried and mediated.

FieldLifecycleMesh can point behavior-bearing fields to gateway or boundary
evidence with `gate:` refs in `FieldProjection.evidence_refs`. Treat those refs
as route labels. A `gate:` ref does not prove runtime-gateway adoption unless
the corresponding Runtime Gateway Adoption report has current inventory,
mediated write observations, runtime path, replay, and proof evidence.

## Boundary

This helper is not a perfect source scanner. A target project must provide the
writer inventory from source audit, runtime instrumentation, tests, or replay.
FlowGuard then reviews whether that inventory is complete enough for the claim
and whether each known critical write path is gated.
