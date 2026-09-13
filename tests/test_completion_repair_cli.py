"""Narrow consumer-only completion-repair preparation checks."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from flowguard.completion_epoch import CompletionEpochPlan, CompletionEpochTerminalLedger
from flowguard.completion_run_manifest import build_manifest
from flowguard.evidence_receipts import fingerprint_value, save_evidence_receipt
from flowguard.validation_ownership import (
    ValidationOwnerContract,
    build_owner_current,
    _prepare_owner_receipt,
)
from flowguard.validation_owner_execution import canonical_semantic_command
from flowguard.validation_results import ValidationChildResult
from scripts import check_flowguard_skill_suite as suite_command
from scripts.prepare_completion_repair import (
    CompletionRepairPreparationError,
    prepare_completion_repair,
)


def _plan(source: str, *, attempt_index: int = 0) -> CompletionEpochPlan:
    return CompletionEpochPlan.freeze(
        source_observation_fingerprint=source,
        release_tree_fingerprint="sha256:" + "2" * 64,
        toolchain_environment_fingerprint="sha256:" + "3" * 64,
        owner_dag_fingerprint="sha256:" + "4" * 64,
        model_authority_fingerprint="sha256:" + "5" * 64,
        test_inventory_fingerprint="sha256:" + "6" * 64,
        required_terminal_action_ids=("owner",),
        attempt_index=attempt_index,
    )


def _contract() -> ValidationOwnerContract:
    return ValidationOwnerContract(
        owner_id="owner",
        command=("python", "-c", "pass"),
        input_patterns=("source.txt",),
        obligation_ids=("validation:owner",),
        resource_keys=("resource:validation-owner:owner",),
    )


def _write_manifest(
    root: Path,
    *,
    plan: CompletionEpochPlan,
    receipt_root: Path,
) -> Path:
    args = SimpleNamespace(
        root=str(root),
        completion_objective_change="",
        formal_root=str(root),
        shadow_root="",
        installed_root="",
        model_receipt_dir=str(root / "model-receipts"),
        model_jobs=1,
        model_timeout=None,
        gate_timeout=900.0,
        require_executed_evidence=True,
        skillguard="all",
    )
    spec = SimpleNamespace(
        child_id="owner",
        command=("python", "-c", "pass"),
        obligation_ids=("validation:owner",),
    )
    owner_plan = SimpleNamespace(plan_fingerprint=plan.owner_dag_fingerprint)
    payload = build_manifest(
        args=args,
        root=root,
        receipt_root=receipt_root,
        specs=(spec,),
        owner_plan=owner_plan,
        completion_epoch=plan,
        canonicalize_command=canonical_semantic_command,
        readiness_fingerprint="sha256:" + "7" * 64,
    )
    path = root / "work" / "readiness" / "completion-run-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _write_real_owner_evidence(root: Path, receipt_root: Path, contract: ValidationOwnerContract):
    current = build_owner_current(root, contract, all_contracts=(contract,))
    child = ValidationChildResult(
        child_id="owner",
        status="pass",
        summary="one supervised owner pass",
        claim_boundary="One supervised owner result.",
        payload={
            "supervised_execution": {
                "cleanup_confirmed": True,
                "timed_out": False,
                "cancelled": False,
                "interrupted": False,
                "exit_code": 0,
            }
        },
    )
    prepared = _prepare_owner_receipt(
        current,
        child,
        receipt_root,
        started_at="2026-09-10T00:00:00+00:00",
        finished_at="2026-09-10T00:00:01+00:00",
        publication_kind="supervised_producer",
    )
    prepared.proof_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.proof_path.write_bytes(prepared.proof_bytes)
    save_evidence_receipt(prepared.receipt, root, output_directory=receipt_root)
    row = {
        "artifact_fingerprint": prepared.receipt.proof_artifact_fingerprint,
        "cleanup_confirmed": True,
        "input_fingerprint": fingerprint_value(
            [current.input_snapshot.to_dict()]
        ),
        "producer_invocations": 1,
        "receipt_fingerprint": prepared.receipt.fingerprint,
        "receipt_id": prepared.receipt.receipt_id,
        "status": "pass",
    }
    return row


def test_prepare_completion_repair_consumes_real_receipt_and_proof(
    tmp_path,
    monkeypatch,
):
    root = tmp_path
    (root / "source.txt").write_text("current\n", encoding="utf-8")
    receipt_root = root / "work" / "owner-receipts"
    receipt_root.mkdir(parents=True)
    contract = _contract()
    monkeypatch.setattr(
        suite_command,
        "_full_child_specs",
        lambda args, root: (SimpleNamespace(child_id="owner"),),
    )
    monkeypatch.setattr(suite_command, "_owner_contracts", lambda specs: (contract,))

    previous = _plan("sha256:" + "1" * 64).claim_full_producer()
    previous_ledger = CompletionEpochTerminalLedger.aborted(previous, "owner failure")
    previous_ledger.write(root)
    current = _plan("sha256:" + "8" * 64)
    manifest_path = _write_manifest(root, plan=current, receipt_root=receipt_root)
    row = _write_real_owner_evidence(root, receipt_root, contract)
    evidence_path = root / "work" / "repair-evidence.json"
    evidence_path.write_text(
        json.dumps({"owner": row}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    group_path = root / "work" / "repair-group.json"
    link_path = root / "work" / "repair-link.json"

    result = prepare_completion_repair(
        root=root,
        previous_epoch_id=previous.epoch_id,
        current_manifest_path=manifest_path,
        repair_evidence_path=evidence_path,
        repair_group_output_path=group_path,
        repair_link_output_path=link_path,
    )

    assert result["status"] == "pass"
    assert result["failed_owner_ids"] == ["owner"]
    assert result["producer_invocations"] == 0
    assert group_path.is_file()
    assert link_path.is_file()
    link_payload = json.loads(link_path.read_text(encoding="utf-8"))
    assert link_payload["failed_owner_ids"] == ["owner"]


def test_prepare_completion_repair_rejects_row_without_canonical_receipt(
    tmp_path,
    monkeypatch,
):
    root = tmp_path
    (root / "source.txt").write_text("current\n", encoding="utf-8")
    receipt_root = root / "work" / "owner-receipts"
    receipt_root.mkdir(parents=True)
    contract = _contract()
    monkeypatch.setattr(
        suite_command,
        "_full_child_specs",
        lambda args, root: (SimpleNamespace(child_id="owner"),),
    )
    monkeypatch.setattr(suite_command, "_owner_contracts", lambda specs: (contract,))

    previous = _plan("sha256:" + "1" * 64).claim_full_producer()
    CompletionEpochTerminalLedger.aborted(previous, "owner failure").write(root)
    current = _plan("sha256:" + "8" * 64)
    manifest_path = _write_manifest(root, plan=current, receipt_root=receipt_root)
    evidence_path = root / "work" / "repair-evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "owner": {
                    "artifact_fingerprint": "sha256:" + "a" * 64,
                    "cleanup_confirmed": True,
                    "input_fingerprint": "sha256:" + "b" * 64,
                    "producer_invocations": 1,
                    "receipt_fingerprint": "sha256:" + "c" * 64,
                    "receipt_id": "receipt:validation-owner:owner:missing",
                    "status": "pass",
                }
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CompletionRepairPreparationError, match="canonical file"):
        prepare_completion_repair(
            root=root,
            previous_epoch_id=previous.epoch_id,
            current_manifest_path=manifest_path,
            repair_evidence_path=evidence_path,
            repair_group_output_path=root / "work" / "repair-group.json",
            repair_link_output_path=root / "work" / "repair-link.json",
        )
