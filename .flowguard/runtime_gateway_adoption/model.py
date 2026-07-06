"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Reviews Runtime Gateway Adoption evidence for critical state writer inventory.

Guards against:
- claiming runtime-gateway protection with only an opaque inventory id;
- using stale or non-passing writer inventory as proof;
- leaving a critical state surface uncovered by structured writer inventory;
- scoping out a discovered writer without a reason;
- accepting inventory evidence with no proof artifact.

Run:
python .flowguard/runtime_gateway_adoption/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass

from flowguard import (
    ADOPTION_LEVEL_RUNTIME_GATEWAY,
    RUNTIME_WRITE_GATEWAY,
    RuntimeGatewayAdoptionPlan,
    RuntimeGatewayContract,
    RuntimeStateSurface,
    RuntimeWriteObservation,
    RuntimeWriterInventoryEvidence,
    review_runtime_gateway_adoption,
)


@dataclass(frozen=True)
class RuntimeGatewayCase:
    name: str
    plan: RuntimeGatewayAdoptionPlan
    expected_ok: bool
    expected_codes: tuple[str, ...] = ()


def surface() -> RuntimeStateSurface:
    return RuntimeStateSurface(
        "router_state",
        paths=("runtime/router_state.json",),
        critical=True,
        owner_gateway_ids=("control_plane_gateway",),
    )


def gateway() -> RuntimeGatewayContract:
    return RuntimeGatewayContract(
        "control_plane_gateway",
        managed_surface_ids=("router_state",),
        step_contract_ids=("consume_controller_receipt",),
        code_boundary_ids=("control_plane_gateway.boundary",),
        runtime_node_ids=("runtime:control_plane_gateway",),
    )


def write_observation() -> RuntimeWriteObservation:
    return RuntimeWriteObservation(
        "router_state_write",
        "router_state",
        write_kind=RUNTIME_WRITE_GATEWAY,
        gateway_id="control_plane_gateway",
        step_contract_ids=("consume_controller_receipt",),
        code_boundary_ids=("control_plane_gateway.boundary",),
        runtime_node_ids=("runtime:control_plane_gateway",),
        proof_artifact_ids=("artifact:router-state-write",),
    )


def inventory(**overrides: object) -> RuntimeWriterInventoryEvidence:
    values = {
        "evidence_id": "inventory:critical-state-writers",
        "covered_surface_ids": ("router_state",),
        "discovered_writer_ids": ("writer:router_state_write",),
        "proof_artifact_ids": ("artifact:writer-inventory",),
        "current": True,
        "result_status": "passed",
    }
    values.update(overrides)
    return RuntimeWriterInventoryEvidence(**values)


def plan(*inventories: RuntimeWriterInventoryEvidence, inventory_ids=("inventory:critical-state-writers",)) -> RuntimeGatewayAdoptionPlan:
    return RuntimeGatewayAdoptionPlan(
        "runtime-gateway-writer-inventory",
        target_level=ADOPTION_LEVEL_RUNTIME_GATEWAY,
        state_surfaces=(surface(),),
        gateways=(gateway(),),
        write_observations=(write_observation(),),
        complete_inventory_evidence_ids=inventory_ids,
        writer_inventory_evidence=inventories,
    )


def cases() -> tuple[RuntimeGatewayCase, ...]:
    return (
        RuntimeGatewayCase("structured_inventory_passes", plan(inventory()), True),
        RuntimeGatewayCase(
            "opaque_inventory_id_without_structured_evidence_blocks",
            plan(),
            False,
            ("missing_structured_writer_inventory_evidence",),
        ),
        RuntimeGatewayCase(
            "missing_inventory_blocks",
            plan(inventory_ids=()),
            False,
            ("missing_complete_writer_inventory", "missing_structured_writer_inventory_evidence"),
        ),
        RuntimeGatewayCase(
            "stale_inventory_blocks",
            plan(inventory(current=False, result_status="skipped")),
            False,
            ("writer_inventory_stale", "writer_inventory_not_passing"),
        ),
        RuntimeGatewayCase(
            "uncovered_critical_surface_blocks",
            plan(inventory(covered_surface_ids=("other_surface",))),
            False,
            ("writer_inventory_missing_critical_surface",),
        ),
        RuntimeGatewayCase(
            "scoped_writer_without_reason_blocks",
            plan(inventory(scoped_out_writer_ids=("writer:legacy_router_state",))),
            False,
            ("writer_inventory_scoped_without_reason",),
        ),
        RuntimeGatewayCase(
            "proofless_inventory_blocks",
            plan(inventory(proof_artifact_ids=())),
            False,
            ("writer_inventory_missing_proof_artifact",),
        ),
    )


def run_inventory_review() -> tuple[tuple[str, bool, tuple[str, ...]], ...]:
    results: list[tuple[str, bool, tuple[str, ...]]] = []
    for case in cases():
        report = review_runtime_gateway_adoption(case.plan)
        codes = tuple(finding.code for finding in report.findings)
        ok_matches = report.ok is case.expected_ok
        codes_match = all(code in codes for code in case.expected_codes)
        results.append((case.name, ok_matches and codes_match, codes))
    return tuple(results)


__all__ = ["cases", "run_inventory_review"]
