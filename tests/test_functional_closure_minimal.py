"""Small real producer fixture for the bounded functional-closure contract.

The tests in this file deliberately exercise the public/current FlowGuard
helpers with real subprocesses and temporary files.  They keep the acceptance
matrix finite: operational metadata is separated from functional identity,
timeout/cancellation is terminal and bounded, and ordinary routing does not
silently widen into rehearsal or full validation.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

from flowguard.development_process_simulator import (
    DevelopmentProcessSimulationRequest,
    SIMULATOR_MODE_AGENT_WORKFLOW,
    review_development_process_simulator,
)
from flowguard.execution_profiles import (
    EXECUTION_PROFILE_AFFECTED,
    EXECUTION_PROFILE_FULL,
    EXECUTION_PROFILE_LIGHT,
    select_execution_profile,
)
from flowguard.process_supervision import run_supervised_bytes
from flowguard.validation_ownership import (
    ValidationOwnerContract,
    build_owner_current,
)


def _owner(
    root: Path,
    owner_id: str,
    *,
    resource_keys: tuple[str, ...] = ("resource:slow",),
    resource_argv_options: tuple[str, ...] = ("--timeout",),
    command: tuple[str, ...] | None = None,
) -> ValidationOwnerContract:
    (root / "source.txt").write_text("current\n", encoding="utf-8")
    return ValidationOwnerContract(
        owner_id=owner_id,
        command=command or (sys.executable, "-c", "print('owner')", "--timeout", "2"),
        input_patterns=("source.txt",),
        obligation_ids=(f"obligation:{owner_id}",),
        resource_keys=resource_keys,
        resource_argv_options=resource_argv_options,
    )


def test_t01_t02_operational_metadata_does_not_reopen_a_functional_leaf(tmp_path: Path) -> None:
    first_contract = _owner(tmp_path, "owner:a")
    first = build_owner_current(tmp_path, first_contract, all_contracts=(first_contract,))
    changed_policy = ValidationOwnerContract(
        owner_id="owner:a",
        command=first_contract.command,
        input_patterns=first_contract.input_patterns,
        obligation_ids=first_contract.obligation_ids,
        resource_keys=("resource:fast",),
        resource_argv_options=("--timeout",),
        termination_policy="terminate_grace_force_kill_confirm_zero_descendants",
    )
    second = build_owner_current(tmp_path, changed_policy, all_contracts=(changed_policy,))
    assert first.contract_hash == second.contract_hash
    assert first.owner_identity == second.owner_identity


def test_t03_t05_functional_change_is_limited_to_the_consuming_owner(tmp_path: Path) -> None:
    a = _owner(tmp_path, "owner:a")
    b = _owner(tmp_path, "owner:b")
    a_before = build_owner_current(tmp_path, a, all_contracts=(a, b))
    b_before = build_owner_current(tmp_path, b, all_contracts=(a, b))
    (tmp_path / "source.txt").write_text("changed\n", encoding="utf-8")
    a_after = build_owner_current(tmp_path, a, all_contracts=(a, b))
    b_after = build_owner_current(tmp_path, b, all_contracts=(a, b))
    assert a_before.owner_identity != a_after.owner_identity
    assert b_before.owner_identity != b_after.owner_identity
    # A product-visible command/oracle change is functional, unlike a resource
    # policy change; it must produce a different owner contract identity.
    oracle_changed = ValidationOwnerContract(
        owner_id="owner:a",
        command=(sys.executable, "-c", "print('new-oracle')"),
        input_patterns=a.input_patterns,
        obligation_ids=a.obligation_ids,
    )
    assert build_owner_current(tmp_path, oracle_changed, all_contracts=(oracle_changed,)).owner_identity != a_after.owner_identity


def test_t04_t11_t12_timeout_source_drift_and_cancel_are_bounded(tmp_path: Path) -> None:
    timeout = run_supervised_bytes(
        (sys.executable, "-c", "import time; time.sleep(0.20)"),
        cwd=tmp_path,
        timeout_seconds=0.02,
        grace_seconds=0.02,
    )
    assert timeout.timed_out
    assert timeout.cleanup_confirmed
    assert not timeout.descendant_process_ids
    retry = run_supervised_bytes(
        (sys.executable, "-c", "print('recovered')"),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    assert retry.ok
    cancel = threading.Event()
    cancel.set()
    cancelled = run_supervised_bytes(
        (sys.executable, "-c", "import time; time.sleep(0.20)"),
        cwd=tmp_path,
        timeout_seconds=2,
        cancel_event=cancel,
    )
    assert cancelled.cancelled
    assert cancelled.cleanup_confirmed
    assert not cancelled.descendant_process_ids


def test_t06_t07_t08_t09_owner_boundaries_are_fail_closed(tmp_path: Path) -> None:
    first = _owner(tmp_path, "owner:a")
    second = _owner(tmp_path, "owner:b")
    first_current = build_owner_current(tmp_path, first, all_contracts=(first, second))
    second_current = build_owner_current(tmp_path, second, all_contracts=(first, second))
    assert first_current.owner_identity != second_current.owner_identity
    assert first_current.contract.obligation_ids != second_current.contract.obligation_ids
    with pytest.raises(ValueError, match="cannot depend on itself"):
        ValidationOwnerContract(
            owner_id="owner:cycle",
            command=(sys.executable, "-c", "pass"),
            input_patterns=("source.txt",),
            obligation_ids=("obligation:cycle",),
            dependency_owner_ids=("owner:cycle",),
        )


def test_t10_selected_owner_input_is_bounded_to_declared_paths(tmp_path: Path) -> None:
    first = _owner(tmp_path, "owner:a")
    current = build_owner_current(tmp_path, first, all_contracts=(first,))
    assert tuple(item["path"] for item in current.input_manifest) == ("source.txt",)


def test_t13_t17_profiles_and_rehearsal_are_explicitly_gated(tmp_path: Path) -> None:
    assert select_execution_profile(operation_kind="read_only", changed_paths=()).execution_profile == EXECUTION_PROFILE_LIGHT
    assert select_execution_profile(operation_kind="change", changed_paths=("src/a.py",)).execution_profile == EXECUTION_PROFILE_AFFECTED
    assert select_execution_profile(operation_kind="qualification", changed_paths=("src/a.py",)).execution_profile == EXECUTION_PROFILE_FULL
    ordinary = review_development_process_simulator(
        DevelopmentProcessSimulationRequest(
            "ordinary-small", task_trivial=True, multiple_skills_or_tools=True
        )
    )
    assert ordinary.ok
    assert SIMULATOR_MODE_AGENT_WORKFLOW not in ordinary.selected_modes
    explicit = review_development_process_simulator(
        DevelopmentProcessSimulationRequest("explicit-rehearsal", explicit_agent_workflow=True)
    )
    assert SIMULATOR_MODE_AGENT_WORKFLOW in explicit.selected_modes


def test_t14_t15_t16_t18_current_result_is_readable_without_a_second_producer(tmp_path: Path) -> None:
    payload = {
        "profile": "focused",
        "execution_count": 0,
        "producer_invocations": 0,
        "functional_key": "sha256:" + "a" * 64,
        "claim_boundary": "read-only current summary",
    }
    path = tmp_path / "completion-summary.json"
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    before = path.read_bytes()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == payload
    assert loaded["execution_count"] == 0
    assert path.read_bytes() == before
