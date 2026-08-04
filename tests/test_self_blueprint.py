from __future__ import annotations

from dataclasses import dataclass

import pytest

from flowguard.self_blueprint import (
    FlowGuardSelfBlueprintError,
    _exact_owner_for_path,
    _flowguard_delegated_assertion_helpers,
    _intent_target_matches,
    _native_evidence_artifacts,
)


@dataclass(frozen=True)
class _TestNode:
    path: str
    node_id: str
    calls: tuple[str, ...]


@dataclass(frozen=True)
class _TestInventory:
    nodes: tuple[_TestNode, ...]


def test_unknown_source_path_cannot_fall_back_to_the_root_model():
    entries = {"authoritative_model_system": {}}

    with pytest.raises(FlowGuardSelfBlueprintError, match="no exact declared model owner"):
        _exact_owner_for_path(
            "flowguard/unknown_component.py",
            entries=entries,
            overrides={},
        )


def test_intent_target_matching_is_exact_not_substring_based():
    assert _intent_target_matches(
        "model-obligation:pay", {"pay", "transition:pay:accepted"}
    )
    assert _intent_target_matches(
        "model-obligation:pay", {"model:pay"}
    )
    assert _intent_target_matches(
        "model-obligation:pay", {"model_instance:model:pay"}
    )
    assert not _intent_target_matches(
        "model-obligation:pay", {"payment", "transition:payment:accepted"}
    )
    assert not _intent_target_matches(
        "model-obligation:pay", {"model:payment"}
    )


def test_exact_module_owner_and_native_checker_identity_are_preserved():
    entries = {
        "work_context": {
            "runner": ["{python}", ".flowguard/work_context/run_checks.py"],
            "purpose_closure": {
                "evidence_check_ids": ["check:model-regression:work_context"],
                "runner_sha256": "sha256:" + "1" * 64,
            },
        }
    }

    assert _exact_owner_for_path(
        "flowguard/work_context.py",
        entries=entries,
        overrides={},
    ) == "work_context"
    artifact = _native_evidence_artifacts(entries)[0]
    assert artifact.evidence_id == "check:model-regression:work_context"
    assert artifact.artifact_path == ".flowguard/work_context/run_checks.py"
    assert artifact.artifact_fingerprint == "sha256:" + "1" * 64


def test_self_helper_discovery_follows_imported_assertion_helpers(tmp_path):
    test_path = tmp_path / "tests" / "test_gate.py"
    helper_path = tmp_path / "flowguard" / "pytest_adapter.py"
    test_path.parent.mkdir(parents=True)
    helper_path.parent.mkdir(parents=True)
    test_path.write_text(
        "from flowguard.pytest_adapter import assert_no_regression\n\n"
        "def test_gate():\n    assert_no_regression(object())\n",
        encoding="utf-8",
    )
    helper_path.write_text(
        "def assert_report_ok(report):\n"
        "    if not report:\n        raise AssertionError('failed')\n\n"
        "def assert_no_regression(report):\n    assert_report_ok(report)\n",
        encoding="utf-8",
    )
    inventory = _TestInventory(
        (
            _TestNode(
                "tests/test_gate.py",
                "tests/test_gate.py::test_gate",
                ("assert_no_regression",),
            ),
        )
    )

    helpers = _flowguard_delegated_assertion_helpers(tmp_path, inventory)
    by_id = {row.helper_id: row for row in helpers}

    assert by_id["assert_no_regression"].callee_member_ids == ("assert_report_ok",)
    assert by_id["assert_report_ok"].terminal_member_fingerprints
