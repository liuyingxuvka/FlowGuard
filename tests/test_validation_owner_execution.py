from dataclasses import replace
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

from flowguard.evidence_receipts import fingerprint_value
from flowguard.process_supervision import SupervisedCommandResult, run_supervised
from flowguard.validation_owner_execution import (
    ValidationOwnerResultIdentityRequirement,
    execute_validation_owner_command,
    publish_supervised_validation_owner_result,
)
import flowguard.validation_ownership as validation_ownership
from flowguard.validation_ownership import (
    ValidationOwnerContract,
    build_owner_current,
    record_validation_owner_nonpass,
)
from flowguard.validation_results import ValidationChildResult


def _owner(tmp_path: Path, *, command: tuple[str, ...], timeout: float = 5.0):
    source = tmp_path / "subject.txt"
    source.write_text("current\n", encoding="utf-8")
    contract = ValidationOwnerContract(
        owner_id="supervised-owner",
        command=command,
        input_patterns=("subject.txt",),
        obligation_ids=("obligation:supervised",),
        projected_inputs=(("subject", fingerprint_value("current")),),
        timeout_seconds=timeout,
    )
    current = build_owner_current(
        tmp_path,
        contract,
        all_contracts=(contract,),
    )
    return contract, current


def _execute(tmp_path: Path, result: SupervisedCommandResult | None = None):
    contract, current = _owner(
        tmp_path,
        command=(sys.executable, "-c", "print('owner-pass')"),
    )
    receipt_root = tmp_path / ".flowguard" / "evidence" / "validation-owners"
    call = lambda: execute_validation_owner_command(
        current,
        tmp_path,
        receipt_root,
        all_contracts=(contract,),
        child_id="child:supervised-owner",
        evidence_context={"subject": "current"},
        summary="real supervised owner",
        claim_boundary="One exact supervised owner command.",
    )
    if result is None:
        return call()
    with mock.patch(
        "flowguard.validation_owner_execution.run_supervised",
        return_value=result,
    ):
        return call()


def _terminal(
    *,
    exit_code=0,
    timed_out=False,
    cancelled=False,
    interrupted=False,
    cleanup_confirmed=True,
):
    return SupervisedCommandResult(
        command=(sys.executable, "-c", "pass"),
        cwd="<WORKSPACE>",
        episode_token="episode:test",
        started_at_epoch=1.0,
        finished_at_epoch=2.0,
        exit_code=exit_code,
        stdout="",
        stderr="",
        terminal_reason=(
            "timeout"
            if timed_out
            else "cancelled"
            if cancelled
            else "keyboard_interrupt"
            if interrupted
            else "process_exit"
            if cleanup_confirmed
            else "cleanup_unconfirmed"
        ),
        timed_out=timed_out,
        cancelled=cancelled,
        interrupted=interrupted,
        termination_stage="none",
        cleanup_confirmed=cleanup_confirmed,
        descendant_process_ids=(),
    )


def _identity_requirement() -> ValidationOwnerResultIdentityRequirement:
    return ValidationOwnerResultIdentityRequirement(
        projection_id=(
            "flowguard.self_maintenance_review.architecture_reduction_identity"
        ),
        source_path=("architecture_reduction_review",),
        fingerprint_fields=(
            "review_fingerprint",
            "projection_fingerprint",
        ),
        content_fingerprint_field="projection_fingerprint",
    )


def _identity_payload(*, review_fingerprint: str | None = None):
    reduction = {
        "projection_kind": "reduction",
        "review_fingerprint": review_fingerprint or "sha256:" + "a" * 64,
    }
    reduction["projection_fingerprint"] = fingerprint_value(reduction)
    return {"architecture_reduction_review": reduction}


def _publish_identity_payload(tmp_path: Path, payload):
    payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    command = (sys.executable, "-c", f"print({payload_text!r})")
    contract, current = _owner(tmp_path, command=command)
    supervised = run_supervised(command, cwd=tmp_path, timeout_seconds=5)
    receipt_root = tmp_path / "receipts"
    result = publish_supervised_validation_owner_result(
        current,
        supervised,
        tmp_path,
        receipt_root,
        all_contracts=(contract,),
        child_id="self_maintenance_review",
        evidence_context={
            "validation_child": {
                "payload": {
                    "payload_sha256": fingerprint_value(payload),
                    "payload_keys": sorted(payload),
                }
            }
        },
        summary="self-maintenance identity fixture",
        claim_boundary="Exact self-maintenance identity fixture.",
        result_identity_requirement=_identity_requirement(),
    )
    return result, receipt_root


def test_real_short_command_publishes_exact_current_owner_receipt(tmp_path):
    result = _execute(tmp_path)

    assert result.ok
    assert result.supervised.ok
    assert result.receipt is not None
    assert result.verification is not None and result.verification.ok
    assert result.receipt.metadata["publication_kind"] == "supervised_producer"


def test_required_result_identities_are_projected_into_owner_proof(tmp_path):
    payload = _identity_payload()
    result, receipt_root = _publish_identity_payload(tmp_path, payload)

    assert result.ok
    assert result.receipt is not None
    proof_path = receipt_root / result.receipt.metadata["proof_relpath"]
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    identity = proof["child"]["payload"]["result_identity_projection"]
    reduction = payload["architecture_reduction_review"]
    assert identity == {
        "schema_version": "flowguard.validation_owner_result_identity.v1",
        "projection_id": (
            "flowguard.self_maintenance_review.architecture_reduction_identity"
        ),
        "source_path": ["architecture_reduction_review"],
        "review_fingerprint": reduction["review_fingerprint"],
        "projection_fingerprint": reduction["projection_fingerprint"],
    }


@pytest.mark.parametrize(
    ("payload", "blocker"),
    (
        (
            {"architecture_reduction_review": {}},
            (
                "validation_owner_result_identity_missing:"
                "architecture_reduction_review.review_fingerprint"
            ),
        ),
        (
            {
                "architecture_reduction_review": {
                    "review_fingerprint": "sha256:" + "a" * 64,
                }
            },
            (
                "validation_owner_result_identity_missing:"
                "architecture_reduction_review.projection_fingerprint"
            ),
        ),
        (
            _identity_payload(review_fingerprint="sha256:not-current"),
            (
                "validation_owner_result_identity_invalid:"
                "architecture_reduction_review.review_fingerprint"
            ),
        ),
        (
            {
                "architecture_reduction_review": {
                    "projection_kind": "reduction",
                    "review_fingerprint": "sha256:" + "a" * 64,
                    "projection_fingerprint": "sha256:" + "b" * 64,
                }
            },
            (
                "validation_owner_result_identity_mismatch:"
                "architecture_reduction_review.projection_fingerprint"
            ),
        ),
    ),
)
def test_required_result_identity_missing_invalid_or_mismatched_fails_closed(
    tmp_path,
    payload,
    blocker,
):
    result, receipt_root = _publish_identity_payload(tmp_path, payload)

    assert not result.ok
    assert result.blocker == blocker
    assert result.receipt is None
    assert not receipt_root.exists()


def test_public_generic_owner_receipt_saver_is_removed():
    assert not hasattr(validation_ownership, "save_owner_receipt")


def test_caller_constructed_green_result_cannot_publish_pass(tmp_path):
    contract, current = _owner(
        tmp_path,
        command=(sys.executable, "-c", "pass"),
    )
    result = publish_supervised_validation_owner_result(
        current,
        _terminal(),
        tmp_path,
        tmp_path / "receipts",
        all_contracts=(contract,),
        child_id="child:forged",
        evidence_context={},
        summary="caller asserted pass",
        claim_boundary="Caller assertion only.",
    )

    assert not result.ok
    assert result.receipt is None
    assert result.blocker == "supervised_result_not_producer_attested"


def test_nonpass_recorder_rejects_pass(tmp_path):
    contract, current = _owner(
        tmp_path,
        command=(sys.executable, "-c", "pass"),
    )
    with pytest.raises(ValueError, match="cannot publish a passing receipt"):
        record_validation_owner_nonpass(
            current,
            ValidationChildResult(
                child_id="child:caller",
                status="pass",
                summary="caller asserted pass",
            ),
            tmp_path,
            tmp_path / "receipts",
            all_contracts=(contract,),
            started_at="2026-08-04T08:00:00+00:00",
            finished_at="2026-08-04T08:00:01+00:00",
        )


def test_genuine_result_for_different_command_cannot_publish(tmp_path):
    expected = (sys.executable, "-c", "print('expected')")
    actual = (sys.executable, "-c", "print('actual')")
    contract, current = _owner(tmp_path, command=expected)
    supervised = run_supervised(actual, cwd=tmp_path, timeout_seconds=5)

    result = publish_supervised_validation_owner_result(
        current,
        supervised,
        tmp_path,
        tmp_path / "receipts",
        all_contracts=(contract,),
        child_id="child:wrong-command",
        evidence_context={},
        summary="wrong command",
        claim_boundary="Wrong command fixture.",
    )

    assert result.blocker == "supervised_command_contract_mismatch"
    assert result.receipt is None


def test_genuine_result_for_different_cwd_cannot_publish(tmp_path):
    command = (sys.executable, "-c", "pass")
    contract, current = _owner(tmp_path, command=command)
    other = tmp_path / "other"
    other.mkdir()
    supervised = run_supervised(command, cwd=other, timeout_seconds=5)

    result = publish_supervised_validation_owner_result(
        current,
        supervised,
        tmp_path,
        tmp_path / "receipts",
        all_contracts=(contract,),
        child_id="child:wrong-cwd",
        evidence_context={},
        summary="wrong cwd",
        claim_boundary="Wrong cwd fixture.",
    )

    assert result.blocker == "supervised_cwd_contract_mismatch"
    assert result.receipt is None


def test_final_currentness_drift_publishes_no_receipt_or_proof(tmp_path):
    command = (sys.executable, "-c", "pass")
    contract, current = _owner(tmp_path, command=command)
    supervised = run_supervised(command, cwd=tmp_path, timeout_seconds=5)
    changed = replace(current, owner_identity="sha256:" + "2" * 64)
    receipt_root = tmp_path / "receipts"

    with mock.patch(
        "flowguard.validation_owner_execution.build_owner_current",
        side_effect=(current, changed),
    ):
        result = publish_supervised_validation_owner_result(
            current,
            supervised,
            tmp_path,
            receipt_root,
            all_contracts=(contract,),
            child_id="child:publication-drift",
            evidence_context={},
            summary="publication drift",
            claim_boundary="Publication drift fixture.",
        )

    assert result.blocker == "validation_owner_inputs_changed_before_publication"
    assert result.receipt is None
    assert not receipt_root.exists()


def test_failed_command_does_not_publish_green_receipt(tmp_path):
    result = _execute(tmp_path, _terminal(exit_code=2))

    assert not result.ok
    assert result.receipt is None
    assert result.verification is None


def test_timeout_does_not_publish_green_receipt(tmp_path):
    result = _execute(tmp_path, _terminal(exit_code=None, timed_out=True))

    assert not result.ok
    assert result.receipt is None
    assert result.verification is None


def test_cleanup_unconfirmed_does_not_publish_green_receipt(tmp_path):
    result = _execute(
        tmp_path,
        _terminal(exit_code=0, cleanup_confirmed=False),
    )

    assert not result.ok
    assert result.receipt is None
    assert result.verification is None


@pytest.mark.parametrize(
    "terminal",
    (
        _terminal(exit_code=None, cancelled=True),
        _terminal(exit_code=None, interrupted=True),
    ),
)
def test_cancelled_or_interrupted_command_does_not_publish_receipt(
    tmp_path,
    terminal,
):
    result = _execute(tmp_path, terminal)

    assert not result.ok
    assert result.receipt is None
    assert result.verification is None


def test_inputs_changed_during_execution_do_not_publish_receipt(tmp_path):
    contract, current = _owner(
        tmp_path,
        command=(sys.executable, "-c", "pass"),
    )
    changed = replace(current, owner_identity="sha256:" + "1" * 64)
    with mock.patch(
        "flowguard.validation_owner_execution.build_owner_current",
        side_effect=(current, changed),
    ):
        result = execute_validation_owner_command(
            current,
            tmp_path,
            tmp_path / ".flowguard" / "evidence" / "validation-owners",
            all_contracts=(contract,),
            child_id="child:stale",
            evidence_context={"subject": "current"},
            summary="stale owner",
            claim_boundary="One owner command.",
        )

    assert not result.ok
    assert result.receipt is None
    assert result.blocker == "validation_owner_inputs_changed_during_execution"
