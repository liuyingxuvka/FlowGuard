"""Focused canonical completion-repair admission checks."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from flowguard._completion_readiness_impl import _prepare_repair_admission
from flowguard.completion_epoch import (
    CompletionEpochPlan,
    CompletionEpochTerminalLedger,
    load_completion_repair_admission_group,
)


def _plan(source: str) -> CompletionEpochPlan:
    return CompletionEpochPlan.freeze(
        source_observation_fingerprint=source,
        release_tree_fingerprint="sha256:" + "2" * 64,
        toolchain_environment_fingerprint="sha256:" + "3" * 64,
        owner_dag_fingerprint="sha256:" + "4" * 64,
        model_authority_fingerprint="sha256:" + "5" * 64,
        test_inventory_fingerprint="sha256:" + "6" * 64,
        required_terminal_action_ids=("owner",),
    )


def test_repair_admission_group_is_canonical_and_producer_free(tmp_path: Path):
    previous = _plan("sha256:" + "1" * 64).claim_full_producer()
    previous_ledger = CompletionEpochTerminalLedger.aborted(previous, "owner failed")
    previous_ledger.write(tmp_path)
    current = _plan("sha256:" + "8" * 64)
    evidence = tmp_path / "targeted-regression.json"
    evidence.write_text(
        json.dumps(
            {
                "schema_version": "flowguard.completion_repair_regression_evidence.v1",
                "scope": "patch_regression",
                "status": "pass",
                "exit_code": 0,
                "cleanup_confirmed": True,
                "tested_input_manifest": {
                    "source_observation_fingerprint": current.source_observation_fingerprint,
                },
                "failed_owner_ids": ["owner"],
                "producer_invocations": 1,
            }
        ),
        encoding="utf-8",
    )
    repaired, loaded, link_path, group_path = _prepare_repair_admission(
        args=SimpleNamespace(
            repair_from_epoch=previous.epoch_id,
            repair_regression_evidence=str(evidence),
        ),
        root=tmp_path,
        current_plan=current,
        output_dir=tmp_path / "readiness",
    )

    assert loaded == previous_ledger
    assert repaired.attempt_index == 1
    assert repaired.full_producer_attempts == 0
    assert link_path.is_file()
    assert group_path.is_file()
    assert not CompletionEpochTerminalLedger.load_for_epoch_id(repaired.epoch_id, tmp_path).is_valid
    group = load_completion_repair_admission_group(
        repaired.repair_link,
        tmp_path,
        previous_ledger=previous_ledger,
        current_plan=current,
    )
    assert group.producer_invocations == 0
    assert group.repair_kind == "attempt_admission"


def test_repair_admission_group_tamper_is_rejected(tmp_path: Path):
    previous = _plan("sha256:" + "1" * 64).claim_full_producer()
    previous_ledger = CompletionEpochTerminalLedger.aborted(previous, "owner failed")
    previous_ledger.write(tmp_path)
    current = _plan("sha256:" + "8" * 64)
    evidence = tmp_path / "targeted-regression.json"
    evidence.write_text(
        json.dumps(
            {
                "scope": "patch_regression",
                "status": "pass",
                "tested_input_manifest": {"source_observation_fingerprint": current.source_observation_fingerprint},
                "failed_owner_ids": ["owner"],
            }
        ),
        encoding="utf-8",
    )
    repaired, _, _, group_path = _prepare_repair_admission(
        args=SimpleNamespace(
            repair_from_epoch=previous.epoch_id,
            repair_regression_evidence=str(evidence),
        ),
        root=tmp_path,
        current_plan=current,
        output_dir=tmp_path / "readiness",
    )
    payload = json.loads(group_path.read_text(encoding="utf-8"))
    payload["producer_invocations"] = 1
    group_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="producer invocations"):
        load_completion_repair_admission_group(
            repaired.repair_link,
            tmp_path,
            previous_ledger=previous_ledger,
            current_plan=current,
        )
