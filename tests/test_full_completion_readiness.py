"""Focused full-scope completion-readiness and repair integration checks."""

import argparse
import json

from scripts import check_flowguard_skill_suite as suite_command
from flowguard.completion_epoch import (
    CompletionEpochPlan,
    CompletionEpochReadiness,
    CompletionEpochTerminalLedger,
    CompletionRepairLink,
    produce_completion_repair_link,
)


def _plan(*, source: str, attempt_index: int = 0) -> CompletionEpochPlan:
    return CompletionEpochPlan.freeze(
        source_observation_fingerprint=source,
        release_tree_fingerprint="sha256:" + "2" * 64,
        toolchain_environment_fingerprint="sha256:" + "3" * 64,
        owner_dag_fingerprint="sha256:" + "4" * 64,
        model_authority_fingerprint="sha256:" + "5" * 64,
        test_inventory_fingerprint="sha256:" + "7" * 64,
        required_terminal_action_ids=("model", "tests"),
        attempt_index=attempt_index,
    )


def _readiness(plan: CompletionEpochPlan, **overrides) -> CompletionEpochReadiness:
    values = {
        "openspec_terminal_receipt_fingerprint": "sha256:" + "8" * 64,
        "external_roots_sync_receipt_fingerprint": "sha256:" + "9" * 64,
        "formal_shadow_installed_sync_receipt_fingerprint": "sha256:" + "a" * 64,
        "reverse_input_acceptance_receipt_fingerprint": "sha256:" + "b" * 64,
        "owner_dag_freeze_receipt_fingerprint": "sha256:" + "c" * 64,
    }
    values.update(overrides)
    return CompletionEpochReadiness.for_plan(plan, **values)


def test_full_repair_link_and_readiness_are_consumed_without_producer(tmp_path):
    previous = _plan(source="sha256:" + "1" * 64).claim_full_producer()
    previous_ledger = CompletionEpochTerminalLedger.aborted(previous, "child failure")
    previous_ledger.write(tmp_path)

    changed_source = "sha256:" + "d" * 64
    link_path = tmp_path / "repair-link.json"
    link = produce_completion_repair_link(
        previous_plan=previous,
        current_plan=_plan(source=changed_source),
        previous_ledger=previous_ledger,
        repair_evidence={},
        repository_root=tmp_path,
        link_output_path=link_path,
    )

    base = _plan(source=changed_source)
    args = argparse.Namespace(completion_repair_link=str(link_path))
    repaired, loaded_previous, repair_error = suite_command._apply_completion_repair(
        base,
        args=args,
        root=tmp_path,
    )

    assert repair_error == ""
    assert loaded_previous == previous_ledger
    assert repaired.attempt_index == 1
    assert repaired.completion_cycle_id == previous.completion_cycle_id
    assert repaired.validate_repair(previous, previous_ledger) == ()

    readiness = _readiness(
        repaired,
        previous_aborted_epoch_ledger_fingerprint=previous_ledger.fingerprint,
    )
    args.completion_readiness = readiness.to_dict()
    loaded_readiness, readiness_error = suite_command._load_completion_readiness(
        args,
        repaired,
    )
    assert readiness_error == ""
    assert loaded_readiness == readiness

    admission = suite_command._completion_epoch_admission(
        repaired,
        args,
        readiness=loaded_readiness,
        readiness_error=readiness_error,
    )
    assert admission.ok


def test_full_repair_missing_or_corrupt_previous_ledger_blocks_closed(tmp_path):
    previous = _plan(source="sha256:" + "1" * 64).claim_full_producer()
    link = CompletionRepairLink(
        completion_cycle_id=previous.completion_cycle_id,
        previous_epoch_id=previous.epoch_id,
        previous_attempt_index=previous.attempt_index,
        repair_group_id="repair-1",
        failed_owner_ids=("tests",),
        repair_receipt_fingerprint="sha256:" + "e" * 64,
        changed_input_fingerprints={
            "source_observation_fingerprint": "sha256:" + "d" * 64,
        },
    )
    link_path = tmp_path / "repair-link.json"
    link_path.write_text(json.dumps(link.to_dict()), encoding="utf-8")
    args = argparse.Namespace(completion_repair_link=str(link_path))

    repaired, loaded_previous, repair_error = suite_command._apply_completion_repair(
        _plan(source="sha256:" + "d" * 64),
        args=args,
        root=tmp_path,
    )

    assert loaded_previous is None
    assert repaired.attempt_index == 0
    assert repair_error == "completion_repair_previous_terminal_ledger_missing"


def test_full_parser_exposes_canonical_readiness_and_repair_inputs():
    args = suite_command.build_parser().parse_args(
        [
            "--completion-readiness",
            "readiness.json",
            "--completion-repair-link",
            "repair.json",
            "--completion-objective-change",
            "allow-explicit-completion-objective",
            "--model-receipt-dir",
            "model-receipts",
        ]
    )

    assert args.completion_readiness == "readiness.json"
    assert args.completion_repair_link == "repair.json"
    assert args.completion_objective_change == "allow-explicit-completion-objective"
    assert args.model_receipt_dir == "model-receipts"
