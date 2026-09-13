"""Regression tests for the one-shot FlowGuard completion epoch."""

from dataclasses import replace
import json

import pytest

from flowguard.completion_epoch import (
    CYCLE_EXHAUSTED,
    CYCLE_REPAIR_REQUIRED,
    EPOCH_LEDGER_ABSENT,
    EPOCH_LEDGER_INVALID,
    EPOCH_LEDGER_VALID,
    EPOCH_ABORTED,
    EPOCH_ADMITTED,
    EPOCH_TERMINAL_PASS,
    CompletionEpochAdmissionError,
    CompletionEpochLedgerLoadResult,
    CompletionEpochPlan,
    CompletionEpochReadiness,
    CompletionEpochSourceDriftError,
    CompletionEpochTerminalLedger,
    CompletionCycleReservation,
    CompletionCycleReservationError,
    CompletionRepairLink,
    produce_completion_repair_link,
    RESERVATION_ACTIVE,
    RESERVATION_ABORTED,
    RESERVATION_SETTLED,
    abort_full_producer,
    reserve_full_producer,
    settle_full_producer,
)
from flowguard.validation_ownership import (
    manifest_fingerprint,
    validation_input_manifest,
)


def make_plan(**overrides):
    values = {
        "source_observation_fingerprint": "sha256:" + "1" * 64,
        "release_tree_fingerprint": "sha256:" + "2" * 64,
        "toolchain_environment_fingerprint": "sha256:" + "3" * 64,
        "fixed_owner_dag_fingerprint": "sha256:" + "4" * 64,
        "model_authority_head_fingerprint": "sha256:" + "5" * 64,
        "model_authority_snapshot_fingerprint": "sha256:" + "6" * 64,
        "test_inventory_fingerprint": "sha256:" + "7" * 64,
        "required_terminal_action_ids": ("model", "tests"),
        "remaining_governed_write_ids": (),
    }
    values.update(overrides)
    return CompletionEpochPlan.freeze(**values)


def make_readiness(plan, **overrides):
    values = {
        "openspec_terminal_receipt_fingerprint": "sha256:" + "8" * 64,
        "external_roots_sync_receipt_fingerprint": "sha256:" + "9" * 64,
        "formal_shadow_installed_sync_receipt_fingerprint": "sha256:" + "a" * 64,
        "reverse_input_acceptance_receipt_fingerprint": "sha256:" + "b" * 64,
        "owner_dag_freeze_receipt_fingerprint": "sha256:" + "c" * 64,
    }
    values.update(overrides)
    return CompletionEpochReadiness.for_plan(plan, **values)


def test_remaining_governed_write_blocks_final_admission():
    plan = make_plan(remaining_governed_write_ids=("openspec/tasks.md",))

    admission = plan.admit()

    assert not admission.ok
    assert admission.status == "blocked"
    assert "remaining_governed_writes" in admission.blockers
    assert "completion_readiness_missing" in admission.blockers
    with pytest.raises(CompletionEpochAdmissionError):
        plan.assert_final_admitted()


def test_positive_readiness_is_required_for_final_admission():
    plan = make_plan()

    admission = plan.admit()

    assert admission.status == "blocked"
    assert admission.blockers == ("completion_readiness_missing",)

    ready = make_readiness(plan)
    admitted = plan.admit(readiness=ready)
    assert admitted.ok
    assert admitted.checks["completion_readiness_current"] is True


def test_readiness_identity_or_required_action_mismatch_blocks():
    plan = make_plan()
    readiness = make_readiness(
        plan,
        required_terminal_action_ids=("model",),
    )

    admission = plan.admit(readiness=readiness)

    assert not admission.ok
    assert "completion_readiness_required_terminal_actions_mismatch" in admission.blockers


def test_initial_readiness_cannot_carry_foreign_repair_context():
    plan = make_plan()
    readiness = replace(
        make_readiness(plan),
        previous_aborted_epoch_id="sha256:" + "d" * 64,
        previous_aborted_epoch_ledger_fingerprint="sha256:" + "e" * 64,
        repair_link_fingerprint="sha256:" + "f" * 64,
    )

    admission = plan.admit(readiness=readiness)

    assert not admission.ok
    assert "completion_readiness_unexpected_repair_context" in admission.blockers


def test_one_full_producer_attempt_is_allowed_per_epoch():
    plan = make_plan()
    claimed = plan.claim_full_producer()

    assert plan.full_attempt_available
    assert not claimed.full_attempt_available
    with pytest.raises(RuntimeError, match="already consumed"):
        claimed.claim_full_producer()


def test_source_drift_aborts_old_epoch_and_requires_new_identity():
    plan = make_plan()

    with pytest.raises(CompletionEpochSourceDriftError):
        plan.assert_source_current("sha256:" + "9" * 64)

    repaired = CompletionEpochPlan.freeze(
        source_observation_fingerprint="sha256:" + "9" * 64,
        release_tree_fingerprint=plan.release_tree_fingerprint,
        toolchain_environment_fingerprint=plan.toolchain_environment_fingerprint,
        owner_dag_fingerprint=plan.owner_dag_fingerprint,
        model_authority_fingerprint=plan.model_authority_fingerprint,
        test_inventory_fingerprint=plan.test_inventory_fingerprint,
        required_terminal_action_ids=plan.required_terminal_action_ids,
    )
    assert repaired.epoch_id != plan.epoch_id


def test_epoch_nonce_is_not_a_current_plan_field():
    with pytest.raises(TypeError):
        CompletionEpochPlan.freeze(
            source_observation_fingerprint="sha256:" + "1" * 64,
            release_tree_fingerprint="sha256:" + "2" * 64,
            toolchain_environment_fingerprint="sha256:" + "3" * 64,
            fixed_owner_dag_fingerprint="sha256:" + "4" * 64,
            model_authority_head_fingerprint="sha256:" + "5" * 64,
            model_authority_snapshot_fingerprint="sha256:" + "6" * 64,
            test_inventory_fingerprint="sha256:" + "7" * 64,
            epoch_nonce="arbitrary-retry-token",
        )


def test_terminal_ledger_is_output_only_and_does_not_change_source_fingerprint(
    tmp_path,
):
    source = tmp_path / "flowguard" / "source.py"
    source.parent.mkdir(parents=True)
    source.write_text("SOURCE = 1\n", encoding="utf-8")
    task = tmp_path / "openspec" / "changes" / "demo" / "tasks.md"
    task.parent.mkdir(parents=True)
    task.write_text("- [ ] final gate\n", encoding="utf-8")
    plan = make_plan().claim_full_producer()
    before = manifest_fingerprint(validation_input_manifest(tmp_path))
    task_before = task.read_bytes()

    ledger = CompletionEpochTerminalLedger.terminal_pass(
        plan,
        verified_child_action_ids=("model", "tests"),
    )
    ledger_path = ledger.write(tmp_path)

    after = manifest_fingerprint(validation_input_manifest(tmp_path))
    assert before == after
    assert task.read_bytes() == task_before
    assert ledger_path.is_file()
    assert ledger_path.is_relative_to(tmp_path / ".flowguard" / "evidence")
    assert ledger_path.parent.name == "completion-epochs"
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert payload["status"] == EPOCH_TERMINAL_PASS
    assert payload["epoch_id"] == plan.epoch_id
    loaded = CompletionEpochTerminalLedger.load_for_plan(plan, tmp_path)
    assert loaded.status == EPOCH_LEDGER_VALID
    assert loaded.is_valid
    assert loaded.ledger == ledger


def test_terminal_ledger_requires_all_declared_actions():
    plan = make_plan().claim_full_producer()

    with pytest.raises(ValueError, match="missing required actions"):
        CompletionEpochTerminalLedger.terminal_pass(
            plan,
            verified_child_action_ids=("model",),
        )


def test_terminal_ledger_rejects_remaining_governed_writes():
    plan = make_plan(remaining_governed_write_ids=("openspec/tasks.md",))

    with pytest.raises(ValueError, match="remaining governed writes"):
        CompletionEpochTerminalLedger.terminal_pass(
            plan,
            verified_child_action_ids=("model", "tests"),
        )


def test_aborted_terminal_ledger_is_stable_and_blocks_reuse(tmp_path):
    plan = make_plan().claim_full_producer()
    ledger = CompletionEpochTerminalLedger.aborted(plan, "timeout")
    path = ledger.write(tmp_path)

    assert path == ledger.write(tmp_path)
    loaded = CompletionEpochTerminalLedger.load_for_plan(plan, tmp_path)
    assert loaded.status == EPOCH_LEDGER_VALID
    assert loaded.ledger is not None
    assert loaded.ledger.status == EPOCH_ABORTED
    assert loaded.ledger.blockers == ("timeout",)


def test_aborted_terminal_ledger_preserves_only_known_completed_actions():
    plan = make_plan().claim_full_producer()
    ledger = CompletionEpochTerminalLedger.aborted(
        plan,
        "one child blocked",
        completed_terminal_action_ids=("model",),
    )

    assert ledger.completed_terminal_action_ids == ("model",)
    assert ledger.status == EPOCH_ABORTED

    with pytest.raises(ValueError, match="foreign completed actions"):
        CompletionEpochTerminalLedger.aborted(
            plan,
            "one child blocked",
            completed_terminal_action_ids=("unknown",),
        )


def test_missing_ledger_is_distinct_from_invalid_ledger(tmp_path):
    plan = make_plan()

    absent = CompletionEpochTerminalLedger.load_for_plan(plan, tmp_path)
    assert absent.status == EPOCH_LEDGER_ABSENT
    assert absent.is_absent

    path = tmp_path / ".flowguard" / "evidence" / "completion-epochs"
    path.mkdir(parents=True)
    ledger_path = path / (
        "epoch-" + plan.epoch_id.split(":", 1)[-1] + ".json"
    )
    ledger_path.write_text("{not-json", encoding="utf-8")

    invalid = CompletionEpochTerminalLedger.load_for_plan(plan, tmp_path)
    assert invalid.status == EPOCH_LEDGER_INVALID
    assert invalid.is_invalid
    assert invalid.ledger is None
    assert invalid.error


def test_corrupt_ledger_bytes_never_become_absent(tmp_path):
    plan = make_plan()
    ledger_dir = tmp_path / ".flowguard" / "evidence" / "completion-epochs"
    ledger_dir.mkdir(parents=True)
    ledger_path = ledger_dir / ("epoch-" + plan.epoch_id.split(":", 1)[-1] + ".json")

    ledger_path.write_bytes(b"\xff\xfe")
    corrupt = CompletionEpochTerminalLedger.load_for_plan(plan, tmp_path)
    assert corrupt.status == EPOCH_LEDGER_INVALID
    assert corrupt.error


@pytest.mark.flowguard_capability("path_escape.posix_symlink")
def test_broken_symlink_ledger_paths_never_become_absent(tmp_path):
    plan = make_plan()
    ledger_dir = tmp_path / ".flowguard" / "evidence" / "completion-epochs"
    ledger_dir.mkdir(parents=True)
    ledger_path = ledger_dir / ("epoch-" + plan.epoch_id.split(":", 1)[-1] + ".json")

    try:
        ledger_path.symlink_to(tmp_path / "missing-ledger.json")
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable in focused test environment: {exc}")
    broken_link = CompletionEpochTerminalLedger.load_for_plan(plan, tmp_path)
    assert broken_link.status == EPOCH_LEDGER_INVALID
    assert "symlink" in broken_link.error


def test_epoch_id_loader_is_structural_and_plan_loader_binds_identity(tmp_path):
    plan = make_plan().claim_full_producer()
    ledger = CompletionEpochTerminalLedger.aborted(plan, "failure")
    ledger.write(tmp_path)

    structural = CompletionEpochTerminalLedger.load_for_epoch_id(
        plan.epoch_id,
        tmp_path,
    )
    assert structural.status == EPOCH_LEDGER_VALID
    assert structural.ledger == ledger

    wrong_plan = make_plan(
        source_observation_fingerprint="sha256:" + "f" * 64,
    ).claim_full_producer()
    bound = CompletionEpochTerminalLedger.load_for_plan(wrong_plan, tmp_path)
    assert bound.status == EPOCH_LEDGER_ABSENT


def test_terminal_ledger_loads_against_fresh_unclaimed_plan(tmp_path):
    """Execution claim state is ledger state, not semantic plan identity."""

    unclaimed = make_plan()
    claimed = unclaimed.claim_full_producer()
    ledger = CompletionEpochTerminalLedger.terminal_pass(
        claimed,
        verified_child_action_ids=("model", "tests"),
    )
    ledger.write(tmp_path)

    loaded = CompletionEpochTerminalLedger.load_for_plan(unclaimed, tmp_path)

    assert loaded.status == EPOCH_LEDGER_VALID
    assert loaded.ledger == ledger


def test_wrong_or_tampered_ledger_fails_closed(tmp_path):
    plan = make_plan().claim_full_producer()
    ledger = CompletionEpochTerminalLedger.aborted(plan, "failure")
    ledger_path = ledger.write(tmp_path)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["source_observation_fingerprint"] = "sha256:" + "f" * 64
    # Keep the old declared fingerprint so the loader must reject the content
    # rather than silently accept a plan-addressed but stale record.
    ledger_path.write_text(json.dumps(payload), encoding="utf-8")

    invalid = CompletionEpochTerminalLedger.load_for_plan(plan, tmp_path)

    assert invalid.status == EPOCH_LEDGER_INVALID
    assert "mismatch" in invalid.error


def test_terminal_ledger_wire_shape_is_strict(tmp_path):
    plan = make_plan().claim_full_producer()
    ledger = CompletionEpochTerminalLedger.aborted(plan, "failure")
    payload = ledger.to_dict()

    missing = dict(payload)
    del missing["metadata"]
    with pytest.raises(ValueError, match="missing required fields"):
        CompletionEpochTerminalLedger.from_dict(missing)

    unknown = dict(payload)
    unknown["epoch_nonce"] = "obsolete"
    with pytest.raises(ValueError, match="unsupported fields"):
        CompletionEpochTerminalLedger.from_dict(unknown)


def test_terminal_ledger_wire_types_are_strict():
    plan = make_plan().claim_full_producer()
    payload = CompletionEpochTerminalLedger.aborted(plan, "failure").to_dict()

    wrong_ids = dict(payload)
    wrong_ids["terminal_action_ids"] = "model"
    with pytest.raises(ValueError, match="must be a sequence of ids"):
        CompletionEpochTerminalLedger.from_dict(wrong_ids)

    wrong_metadata = dict(payload)
    wrong_metadata["metadata"] = ["not", "an", "object"]
    with pytest.raises(ValueError, match="metadata must be an object"):
        CompletionEpochTerminalLedger.from_dict(wrong_metadata)


def test_old_epoch_schema_and_obsolete_nonce_are_not_read_as_current(tmp_path):
    plan = make_plan().claim_full_producer()
    ledger = CompletionEpochTerminalLedger.aborted(plan, "failure")
    ledger_path = ledger.write(tmp_path)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["schema_version"] = "flowguard.completion_epoch_terminal_ledger.v1"
    payload["epoch_nonce"] = "legacy"
    ledger_path.write_text(json.dumps(payload), encoding="utf-8")

    invalid = CompletionEpochTerminalLedger.load_for_plan(plan, tmp_path)

    assert invalid.status == EPOCH_LEDGER_INVALID
    assert "unsupported fields" in invalid.error or "unsupported" in invalid.error


def test_completion_cycle_has_two_attempts_and_no_more():
    plan = make_plan()
    cycle = plan.completion_cycle
    first = cycle.claim()
    second = first.claim()

    assert first.status == CYCLE_REPAIR_REQUIRED
    assert second.status == CYCLE_EXHAUSTED
    assert second.consumed_full_attempts == 2
    with pytest.raises(RuntimeError, match="budget exhausted"):
        second.claim()


def test_terminal_pass_cycle_cannot_reopen_a_full_attempt():
    plan = make_plan()
    terminal = replace(plan.completion_cycle, status="terminal_pass")

    with pytest.raises(RuntimeError, match="terminal completion cycle"):
        terminal.claim()


def test_second_epoch_cannot_be_fabricated_without_repair_link():
    with pytest.raises(ValueError, match="typed repair link"):
        make_plan(attempt_index=1)


def test_current_plan_and_readiness_round_trip_reject_obsolete_fields():
    plan = make_plan()
    payload = plan.to_dict()
    assert CompletionEpochPlan.from_dict(payload) == plan
    payload["epoch_nonce"] = "obsolete"
    with pytest.raises(ValueError, match="unsupported fields"):
        CompletionEpochPlan.from_dict(payload)

    readiness = make_readiness(plan)
    readiness_payload = readiness.to_dict()
    assert CompletionEpochReadiness.from_dict(readiness_payload) == readiness
    readiness_payload["readiness_fingerprint"] = "sha256:" + "f" * 64
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        CompletionEpochReadiness.from_dict(readiness_payload)


def test_plan_rejects_inconsistent_model_authority_aliases():
    with pytest.raises(ValueError, match="model authority fingerprints disagree"):
        make_plan(
            model_authority_fingerprint="sha256:" + "f" * 64,
        )


def test_repair_link_round_trip_requires_its_fingerprint():
    previous = make_plan().claim_full_producer()
    link = CompletionRepairLink(
        completion_cycle_id=previous.completion_cycle_id,
        previous_epoch_id=previous.epoch_id,
        previous_attempt_index=previous.attempt_index,
        repair_group_id="repair-1",
        failed_owner_ids=("owner",),
        repair_receipt_fingerprint="sha256:" + "e" * 64,
        changed_input_fingerprints={
            "source_observation_fingerprint": "sha256:" + "d" * 64,
        },
    )
    payload = link.to_dict()
    assert CompletionRepairLink.from_dict(payload) == link
    del payload["repair_link_fingerprint"]
    with pytest.raises(ValueError, match="fingerprint is required"):
        CompletionRepairLink.from_dict(payload)


def test_typed_repair_link_requires_failed_previous_epoch_and_changed_input():
    previous = make_plan().claim_full_producer()
    previous_ledger = CompletionEpochTerminalLedger.aborted(previous, "failure")
    changed_source = "sha256:" + "d" * 64
    link = CompletionRepairLink(
        completion_cycle_id=previous.completion_cycle_id,
        previous_epoch_id=previous.epoch_id,
        previous_attempt_index=previous.attempt_index,
        repair_group_id="repair-1",
        failed_owner_ids=("self_maintenance_review",),
        repair_receipt_fingerprint="sha256:" + "e" * 64,
        changed_input_fingerprints={
            "source_observation_fingerprint": changed_source,
        },
    )
    repaired = CompletionEpochPlan.for_repair(
        previous,
        source_observation_fingerprint=changed_source,
        release_tree_fingerprint=previous.release_tree_fingerprint,
        toolchain_environment_fingerprint=previous.toolchain_environment_fingerprint,
        model_authority_fingerprint=previous.model_authority_fingerprint,
        test_inventory_fingerprint=previous.test_inventory_fingerprint,
        repair_link=link,
    )

    assert repaired.attempt_index == 1
    assert repaired.completion_cycle_id == previous.completion_cycle_id
    assert repaired.validate_repair(previous, previous_ledger) == ()

    readiness = make_readiness(repaired)
    admission = repaired.admit(readiness=readiness)
    assert not admission.ok
    assert "completion_readiness_previous_aborted_epoch_ledger_missing" in admission.blockers
    ready_repair = make_readiness(
        repaired,
        previous_aborted_epoch_ledger_fingerprint=previous_ledger.fingerprint,
    )
    assert repaired.admit(readiness=ready_repair).ok


def _repair_evidence_for(action_ids):
    return {
        action_id: {
            "artifact_fingerprint": "sha256:" + "a" * 64,
            "cleanup_confirmed": True,
            "input_fingerprint": "sha256:" + "b" * 64,
            "producer_invocations": 1,
            "receipt_fingerprint": "sha256:" + "c" * 64,
            "receipt_id": f"receipt-{action_id}",
            "status": "pass",
        }
        for action_id in action_ids
    }


def test_repair_link_producer_derives_failed_and_changed_sets_and_is_idempotent(tmp_path):
    initial = make_plan()
    previous = initial.claim_full_producer()
    previous_ledger = CompletionEpochTerminalLedger.aborted(previous, "timeout")
    current = replace(
        initial,
        source_observation_fingerprint="sha256:" + "d" * 64,
        release_tree_fingerprint="sha256:" + "e" * 64,
    )
    evidence = _repair_evidence_for(previous.required_terminal_action_ids)
    group_path = tmp_path / "repair-group.json"
    link_path = tmp_path / "repair-link.json"

    link = produce_completion_repair_link(
        previous_plan=previous,
        current_plan=current,
        previous_ledger=previous_ledger,
        repair_evidence=evidence,
        repair_group_output_path=group_path,
        link_output_path=link_path,
    )

    assert link.failed_owner_ids == previous.required_terminal_action_ids
    assert link.changed_input_fingerprints == {
        "release_tree_fingerprint": current.release_tree_fingerprint,
        "source_observation_fingerprint": current.source_observation_fingerprint,
    }
    repaired = CompletionEpochPlan.for_repair(
        previous,
        source_observation_fingerprint=current.source_observation_fingerprint,
        release_tree_fingerprint=current.release_tree_fingerprint,
        toolchain_environment_fingerprint=current.toolchain_environment_fingerprint,
        owner_dag_fingerprint=current.owner_dag_fingerprint,
        model_authority_fingerprint=current.model_authority_fingerprint,
        test_inventory_fingerprint=current.test_inventory_fingerprint,
        repair_link=link,
    )
    assert repaired.validate_repair(previous, previous_ledger) == ()

    group_before = group_path.read_bytes()
    link_before = link_path.read_bytes()
    same = produce_completion_repair_link(
        previous_plan=previous,
        current_plan=current,
        previous_ledger=previous_ledger,
        repair_evidence=evidence,
        repair_group_output_path=group_path,
        link_output_path=link_path,
    )
    assert same == link
    assert group_path.read_bytes() == group_before
    assert link_path.read_bytes() == link_before


def test_repair_link_producer_rejects_incomplete_or_foreign_repair_evidence():
    initial = make_plan()
    previous = initial.claim_full_producer()
    previous_ledger = CompletionEpochTerminalLedger.aborted(previous, "timeout")
    current = replace(
        initial,
        source_observation_fingerprint="sha256:" + "d" * 64,
    )
    evidence = _repair_evidence_for(previous.required_terminal_action_ids)
    evidence.pop("tests")
    with pytest.raises(ValueError, match="does not cover failed owners exactly"):
        produce_completion_repair_link(
            previous_plan=previous,
            current_plan=current,
            previous_ledger=previous_ledger,
            repair_evidence=evidence,
        )

    evidence = _repair_evidence_for(previous.required_terminal_action_ids)
    evidence["tests"]["unexpected"] = True
    with pytest.raises(ValueError, match="fields are not exact-current"):
        produce_completion_repair_link(
            previous_plan=previous,
            current_plan=current,
            previous_ledger=previous_ledger,
            repair_evidence=evidence,
        )


def test_repair_link_producer_never_accepts_a_same_input_or_unclaimed_predecessor():
    initial = make_plan()
    current = replace(
        initial,
        source_observation_fingerprint="sha256:" + "d" * 64,
    )
    evidence = _repair_evidence_for(initial.required_terminal_action_ids)
    with pytest.raises(ValueError, match="claimed initial attempt"):
        produce_completion_repair_link(
            previous_plan=initial,
            current_plan=current,
            previous_ledger=CompletionEpochTerminalLedger.aborted(
                initial.claim_full_producer(), "timeout"
            ),
            repair_evidence=evidence,
        )

    previous = initial.claim_full_producer()
    ledger = CompletionEpochTerminalLedger.aborted(previous, "timeout")
    with pytest.raises(ValueError, match="at least one changed governed input"):
        produce_completion_repair_link(
            previous_plan=previous,
            current_plan=initial,
            previous_ledger=ledger,
            repair_evidence=evidence,
        )


def test_repair_without_typed_link_or_with_same_input_is_blocked():
    previous = make_plan().claim_full_producer()
    previous_ledger = CompletionEpochTerminalLedger.aborted(previous, "failure")
    assert previous.validate_repair(previous, previous_ledger) == (
        "completion_repair_link_missing",
    )
    same_source = previous.source_observation_fingerprint
    link = CompletionRepairLink(
        completion_cycle_id=previous.completion_cycle_id,
        previous_epoch_id=previous.epoch_id,
        previous_attempt_index=previous.attempt_index,
        repair_group_id="repair-1",
        failed_owner_ids=("owner",),
        repair_receipt_fingerprint="sha256:" + "e" * 64,
        changed_input_fingerprints={
            "source_observation_fingerprint": same_source,
        },
    )
    with pytest.raises(ValueError, match="repair link invalid"):
        CompletionEpochPlan.for_repair(
            previous,
            source_observation_fingerprint=same_source,
            release_tree_fingerprint=previous.release_tree_fingerprint,
            toolchain_environment_fingerprint=previous.toolchain_environment_fingerprint,
            model_authority_fingerprint=previous.model_authority_fingerprint,
            test_inventory_fingerprint=previous.test_inventory_fingerprint,
            repair_link=link,
        )


def test_repair_link_must_declare_every_changed_governed_input():
    previous = make_plan().claim_full_producer()
    changed_source = "sha256:" + "d" * 64
    changed_model = "sha256:" + "e" * 64
    link = CompletionRepairLink(
        completion_cycle_id=previous.completion_cycle_id,
        previous_epoch_id=previous.epoch_id,
        previous_attempt_index=previous.attempt_index,
        repair_group_id="repair-1",
        failed_owner_ids=("owner",),
        repair_receipt_fingerprint="sha256:" + "f" * 64,
        changed_input_fingerprints={
            "source_observation_fingerprint": changed_source,
        },
    )

    with pytest.raises(ValueError, match="repair_changed_input_undeclared"):
        CompletionEpochPlan.for_repair(
            previous,
            source_observation_fingerprint=changed_source,
            release_tree_fingerprint=previous.release_tree_fingerprint,
            toolchain_environment_fingerprint=previous.toolchain_environment_fingerprint,
            model_authority_fingerprint=changed_model,
            test_inventory_fingerprint=previous.test_inventory_fingerprint,
            repair_link=link,
        )


def test_pre_run_readiness_has_required_actions_but_no_completed_actions():
    plan = make_plan()
    readiness = make_readiness(plan)
    payload = readiness.to_dict()

    assert payload["required_terminal_action_ids"] == ["model", "tests"]
    assert "completed_terminal_action_ids" not in payload
    with pytest.raises(TypeError):
        CompletionEpochReadiness.for_plan(
            plan,
            openspec_terminal_receipt_fingerprint="sha256:" + "8" * 64,
            external_roots_sync_receipt_fingerprint="sha256:" + "9" * 64,
            formal_shadow_installed_sync_receipt_fingerprint="sha256:" + "a" * 64,
            reverse_input_acceptance_receipt_fingerprint="sha256:" + "b" * 64,
            owner_dag_freeze_receipt_fingerprint="sha256:" + "c" * 64,
            completed_terminal_action_ids=("model", "tests"),
        )


def test_readiness_v1_payload_is_not_read_as_current():
    plan = make_plan()
    payload = make_readiness(plan).to_dict()
    payload["schema_version"] = "flowguard.completion_epoch_readiness.v1"
    with pytest.raises(ValueError, match="unsupported completion epoch readiness schema"):
        CompletionEpochReadiness.from_dict(payload)


def test_completion_cycle_is_anchored_to_objective_not_owner_disposition():
    objective = "sha256:" + "8" * 64
    first = make_plan(
        completion_objective_fingerprint=objective,
        owner_dag_fingerprint="sha256:" + "4" * 64,
    )
    changed_dag = make_plan(
        completion_objective_fingerprint=objective,
        owner_dag_fingerprint="sha256:" + "f" * 64,
        fixed_owner_dag_fingerprint="sha256:" + "f" * 64,
    )

    assert first.completion_cycle_id == changed_dag.completion_cycle_id
    assert first.completion_cycle_seed_fingerprint == changed_dag.completion_cycle_seed_fingerprint


def test_completion_work_id_keeps_budget_when_objective_changes(tmp_path):
    work_id = "work:stable-budget"
    initial = make_plan(
        completion_work_id=work_id,
        completion_objective_fingerprint="sha256:" + "8" * 64,
    )
    claimed, reservation = reserve_full_producer(
        initial,
        tmp_path,
        producer_id="initial",
    )
    previous_ledger = CompletionEpochTerminalLedger.aborted(
        claimed,
        "initial owner failed",
    )
    previous_ledger.write(tmp_path)
    abort_full_producer(
        reservation,
        tmp_path,
        terminal_ledger_fingerprint=previous_ledger.fingerprint,
    )

    changed_objective = make_plan(
        source_observation_fingerprint="sha256:" + "9" * 64,
        completion_work_id=work_id,
        completion_objective_fingerprint="sha256:" + "a" * 64,
    )
    assert changed_objective.completion_cycle_id == initial.completion_cycle_id
    with pytest.raises(CompletionCycleReservationError) as error:
        reserve_full_producer(
            changed_objective,
            tmp_path,
            producer_id="must-not-start",
        )
    assert error.value.code == "completion_cycle_attempt_already_consumed"


def test_completion_repair_declares_objective_change_without_opening_new_cycle():
    work_id = "work:objective-repair"
    previous = make_plan(
        completion_work_id=work_id,
        completion_objective_fingerprint="sha256:" + "1" * 64,
    ).claim_full_producer()
    previous_ledger = CompletionEpochTerminalLedger.aborted(previous, "owner failed")
    current = make_plan(
        source_observation_fingerprint="sha256:" + "2" * 64,
        completion_work_id=work_id,
        completion_objective_fingerprint="sha256:" + "3" * 64,
    )
    link = produce_completion_repair_link(
        previous_plan=previous,
        current_plan=current,
        previous_ledger=previous_ledger,
    )

    repaired = CompletionEpochPlan.for_repair(
        previous,
        source_observation_fingerprint=current.source_observation_fingerprint,
        release_tree_fingerprint=current.release_tree_fingerprint,
        toolchain_environment_fingerprint=current.toolchain_environment_fingerprint,
        owner_dag_fingerprint=current.owner_dag_fingerprint,
        model_authority_fingerprint=current.model_authority_fingerprint,
        test_inventory_fingerprint=current.test_inventory_fingerprint,
        completion_objective_fingerprint=current.completion_objective_fingerprint,
        repair_link=link,
    )
    assert repaired.completion_cycle_id == previous.completion_cycle_id
    assert repaired.completion_objective_fingerprint == current.completion_objective_fingerprint
    assert repaired.validate_repair(previous, previous_ledger) == ()


def test_distinct_completion_work_ids_have_distinct_budgets(tmp_path):
    first = make_plan(completion_work_id="work:first")
    second = make_plan(completion_work_id="work:second")
    assert first.completion_cycle_id != second.completion_cycle_id

    first_claimed, first_reservation = reserve_full_producer(
        first,
        tmp_path,
        producer_id="first",
    )
    second_claimed, second_reservation = reserve_full_producer(
        second,
        tmp_path,
        producer_id="second",
    )
    assert first_claimed.full_producer_attempts == 1
    assert second_claimed.full_producer_attempts == 1
    assert first_reservation.cycle_id != second_reservation.cycle_id


def test_terminal_pass_requires_verified_child_set_and_rejects_old_completed_argument():
    plan = make_plan().claim_full_producer()
    with pytest.raises(TypeError):
        CompletionEpochTerminalLedger.terminal_pass(
            plan,
            completed_terminal_action_ids=("model", "tests"),
        )

    with pytest.raises(ValueError, match="independently current"):
        CompletionEpochTerminalLedger.terminal_pass_from_verified_children(
            plan,
            {
                "model": {"status": "pass", "current": False, "eligible": True},
                "tests": {"status": "pass", "current": True, "eligible": True},
            },
        )

    ledger = CompletionEpochTerminalLedger.terminal_pass_from_verified_children(
        plan,
        {
            "model": {"status": "pass", "current": True, "eligible": True},
            "tests": {"status": "pass", "current": True, "eligible": True},
        },
    )
    assert ledger.completed_terminal_action_ids == ("model", "tests")


def test_persistent_reservation_blocks_second_producer_and_keeps_terminal_state(tmp_path):
    plan = make_plan()

    claimed, reservation = reserve_full_producer(
        plan,
        tmp_path,
        producer_id="producer-a",
    )
    assert claimed.full_producer_attempts == 1
    assert reservation.status == RESERVATION_ACTIVE
    reservation_path = CompletionCycleReservation.path_for_epoch_id(
        plan.epoch_id,
        tmp_path,
    )
    assert reservation_path.is_file()
    loaded = CompletionCycleReservation.load_for_plan(plan, tmp_path)
    assert loaded.is_valid
    assert loaded.reservation == reservation

    with pytest.raises(
        CompletionCycleReservationError,
        match="completion_cycle_reservation_active",
    ) as second:
        reserve_full_producer(plan, tmp_path, producer_id="producer-b")
    assert second.value.code == "completion_cycle_reservation_active"

    terminal = CompletionEpochTerminalLedger.aborted(claimed, "producer failed")
    terminal_path = terminal.write(tmp_path)
    settled = abort_full_producer(
        reservation,
        tmp_path,
        terminal_ledger_fingerprint=terminal.fingerprint,
        cleanup_status="confirmed",
    )
    assert settled.status == RESERVATION_ABORTED
    assert settled.terminal_ledger_fingerprint == terminal.fingerprint
    assert reservation_path.is_file()
    assert CompletionCycleReservation.load_for_plan(plan, tmp_path).reservation == settled

    # A terminal ledger takes precedence for the exact epoch and remains a
    # blocker; the reservation was not deleted or reset after the abort.
    with pytest.raises(CompletionCycleReservationError) as third:
        reserve_full_producer(plan, tmp_path, producer_id="producer-c")
    assert third.value.code == "completion_epoch_terminal_already_recorded"
    assert terminal_path.is_file()


def test_source_change_without_typed_repair_cannot_reset_persistent_cycle(tmp_path):
    initial = make_plan()
    claimed, reservation = reserve_full_producer(initial, tmp_path, producer_id="producer-a")
    terminal = CompletionEpochTerminalLedger.aborted(claimed, "first attempt failed")
    terminal.write(tmp_path)
    abort_full_producer(
        reservation,
        tmp_path,
        terminal_ledger_fingerprint=terminal.fingerprint,
    )

    changed = make_plan(source_observation_fingerprint="sha256:" + "9" * 64)
    assert changed.completion_cycle_id == initial.completion_cycle_id
    with pytest.raises(CompletionCycleReservationError) as blocked:
        reserve_full_producer(changed, tmp_path, producer_id="producer-b")
    assert blocked.value.code == "completion_cycle_attempt_already_consumed"
    assert "completion_cycle_initial_attempt_already_consumed" in blocked.value.blockers


def test_typed_repair_can_consume_only_second_persistent_cycle_attempt(tmp_path):
    previous = make_plan()
    claimed, reservation = reserve_full_producer(previous, tmp_path, producer_id="producer-a")
    previous_ledger = CompletionEpochTerminalLedger.aborted(claimed, "first attempt failed")
    previous_ledger.write(tmp_path)
    abort_full_producer(
        reservation,
        tmp_path,
        terminal_ledger_fingerprint=previous_ledger.fingerprint,
    )
    changed_source = "sha256:" + "9" * 64
    link = CompletionRepairLink(
        completion_cycle_id=previous.completion_cycle_id,
        previous_epoch_id=previous.epoch_id,
        previous_attempt_index=0,
        repair_group_id="repair-group",
        failed_owner_ids=("model",),
        repair_receipt_fingerprint="sha256:" + "8" * 64,
        changed_input_fingerprints={
            "source_observation_fingerprint": changed_source,
        },
    )
    repaired = CompletionEpochPlan.for_repair(
        claimed,
        source_observation_fingerprint=changed_source,
        release_tree_fingerprint=previous.release_tree_fingerprint,
        toolchain_environment_fingerprint=previous.toolchain_environment_fingerprint,
        model_authority_fingerprint=previous.model_authority_fingerprint,
        test_inventory_fingerprint=previous.test_inventory_fingerprint,
        repair_link=link,
    )
    repaired_claimed, repaired_reservation = reserve_full_producer(
        repaired,
        tmp_path,
        producer_id="producer-b",
    )
    assert repaired_claimed.attempt_index == 1
    assert repaired_reservation.status == RESERVATION_ACTIVE
    with pytest.raises(CompletionCycleReservationError) as third:
        reserve_full_producer(repaired, tmp_path, producer_id="producer-c")
    assert third.value.code == "completion_cycle_reservation_active"


def test_corrupt_persistent_reservation_is_not_a_cache_miss(tmp_path):
    plan = make_plan()
    _claimed, reservation = reserve_full_producer(plan, tmp_path, producer_id="producer-a")
    path = CompletionCycleReservation.path_for_epoch_id(plan.epoch_id, tmp_path)
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(CompletionCycleReservationError) as blocked:
        reserve_full_producer(plan, tmp_path, producer_id="producer-b")
    assert blocked.value.code == "completion_cycle_reservation_store_invalid"


def test_unrelated_historical_reservation_schema_does_not_block_new_work_cycle(tmp_path):
    historical = make_plan(completion_work_id="historical-work")
    reserve_full_producer(historical, tmp_path, producer_id="historical-producer")
    historical_path = CompletionCycleReservation.path_for_epoch_id(
        historical.epoch_id,
        tmp_path,
    )
    payload = json.loads(historical_path.read_text(encoding="utf-8"))
    # Simulate a durable pre-identity-fields record.  Its cycle id is still
    # usable, so it can be proven unrelated without treating it as current
    # evidence for the new work item.
    for field_name in ("maintenance_unit_id", "completion_work_id", "claim_scope"):
        payload.pop(field_name, None)
    historical_path.write_text(json.dumps(payload), encoding="utf-8")

    current = make_plan(completion_work_id="current-work")
    claimed, reservation = reserve_full_producer(
        current,
        tmp_path,
        producer_id="current-producer",
    )

    assert claimed.epoch_id == current.epoch_id
    assert reservation.status == RESERVATION_ACTIVE


def test_settled_persistent_reservation_is_idempotent_for_same_owner(tmp_path):
    plan = make_plan()
    claimed, reservation = reserve_full_producer(plan, tmp_path, producer_id="producer-a")
    terminal = CompletionEpochTerminalLedger.terminal_pass(
        claimed,
        verified_child_action_ids=("model", "tests"),
    )
    terminal.write(tmp_path)
    settled = settle_full_producer(
        reservation,
        tmp_path,
        terminal_ledger_fingerprint=terminal.fingerprint,
    )
    again = settle_full_producer(
        reservation,
        tmp_path,
        terminal_ledger_fingerprint=terminal.fingerprint,
    )
    assert again == settled
    assert again.status == RESERVATION_SETTLED
