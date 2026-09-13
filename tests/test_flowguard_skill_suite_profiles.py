from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from flowguard.skill_contracts import ContractCompileReport
from flowguard.skill_suite import (
    FLOWGUARD_AUTHOR_REQUIRED_MEMBER_FILES,
    SkillSuiteMemberReport,
    SkillSuiteReport,
)
from flowguard.validation_results import ValidationChildResult
from scripts import check_flowguard_skill_suite as suite


def test_conflicting_light_operation_blocks_before_any_producer(tmp_path: Path) -> None:
    with patch.object(suite, "run_light_suite") as run_light, patch("builtins.print") as printer:
        exit_code = suite.main(
            [
                "--root",
                str(tmp_path),
                "--scope",
                "light",
                "--operation-kind",
                "change",
                "--json",
            ]
        )

    assert exit_code != 0
    run_light.assert_not_called()
    terminal = json.loads(printer.call_args.args[0])
    assert terminal["scope"] == "light"
    assert terminal["status"] == "blocked"
    assert any(
        "read_only_profile_write_intent_conflict" in blocker
        for blocker in terminal["blockers"]
    )


def test_conflicting_full_operation_blocks_before_full_owner(tmp_path: Path) -> None:
    with patch.object(suite, "run_full_validation") as run_full, patch("builtins.print") as printer:
        exit_code = suite.main(
            [
                "--root",
                str(tmp_path),
                "--scope",
                "full",
                "--operation-kind",
                "read_only",
                "--json",
            ]
        )

    assert exit_code != 0
    run_full.assert_not_called()
    terminal = json.loads(printer.call_args.args[0])
    assert terminal["scope"] == "full"
    assert terminal["status"] == "blocked"
    assert any(
        "full_profile_read_only_intent_conflict" in item
        for item in (*terminal["blockers"], *terminal["failures"])
    )


def test_affected_terminal_projection_keeps_affected_scope() -> None:
    payload = {
        "scope": "affected",
        "status": "pass",
        "ok": True,
        "passed_members": 1,
        "total_members": 1,
        "members": [],
        "blockers": [],
        "skipped_checks": [],
        "claim_boundary": "affected only",
    }
    output = StringIO()
    with redirect_stdout(output):
        suite._print_light(payload, as_json=True)
    terminal = json.loads(output.getvalue())
    assert terminal["scope"] == "affected"
    assert terminal["claim_boundary"] == "affected only"


def test_light_terminal_projection_keeps_light_scope() -> None:
    payload = {
        "scope": "light",
        "status": "pass",
        "ok": True,
        "passed_members": 1,
        "total_members": 1,
        "members": [],
        "blockers": [],
        "skipped_checks": [],
        "claim_boundary": "light only",
    }
    output = StringIO()
    with redirect_stdout(output):
        suite._print_light(payload, as_json=True)
    terminal = json.loads(output.getvalue())
    assert terminal["scope"] == "light"


def _light_index_fixture(tmp_path: Path) -> tuple[SkillSuiteReport, ContractCompileReport]:
    root = tmp_path
    skill = root / ".agents" / "skills" / "target"
    for relative in FLOWGUARD_AUTHOR_REQUIRED_MEMBER_FILES:
        path = skill / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture:{relative}\n", encoding="utf-8")
    suite_map = root / ".skillguard" / "flowguard-suite" / "suite-map.json"
    suite_map.parent.mkdir(parents=True, exist_ok=True)
    suite_map.write_text(
        json.dumps(
            {
                "schema_version": "skillguard.suite_map.v2",
                "suite_name": "flowguard-agent-skill-suite",
                "included_skills": [
                    {
                        "name": "target",
                        "path": ".agents/skills/target",
                        "role": "public_satellite",
                        "owner": "target",
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / ".flowguard" / "work" / "flowguard").mkdir(parents=True)
    member = SkillSuiteMemberReport(
        skill_id="target",
        role="public_satellite",
        owner="target",
        declared_path=".agents/skills/target",
        repository_role="skill_maintainer_source",
        discovered=True,
        control_root_present=True,
        required_files={relative: True for relative in FLOWGUARD_AUTHOR_REQUIRED_MEMBER_FILES},
        source_hash="SOURCE",
    )
    inventory = SkillSuiteReport(
        root=str(root.resolve()),
        schema_version="skillguard.suite_map.v2",
        suite_name="flowguard-agent-skill-suite",
        inventory_hash="INVENTORY",
        semantic_hash="SEMANTIC",
        declared_member_ids=("target",),
        discovered_member_ids=("target",),
        members=(member,),
        findings=(),
    )
    compiler = ContractCompileReport(
        root=str(root.resolve()),
        mode="check",
        member_ids=("target",),
        contract_hashes={"target": "CONTRACT"},
        route_registry_hash="ROUTES",
    )
    return inventory, compiler


def test_light_reuses_finite_suite_index_without_a_second_validation(
    tmp_path: Path,
) -> None:
    inventory, compiler = _light_index_fixture(tmp_path)
    with (
        patch.object(suite, "validate_skill_suite", return_value=inventory) as validate,
        patch.object(suite, "compile_skill_suite", return_value=compiler) as compile_suite,
    ):
        first = suite.run_light_suite(tmp_path, allow_cache_write=True)
        second = suite.run_light_suite(tmp_path, allow_cache_write=True)

    assert first["ok"] is True
    assert first["light_suite_index"]["cache_status"] == "miss_written"
    assert second["ok"] is True
    assert second["light_suite_index"]["cache_status"] == "hit"
    assert validate.call_count == 1
    assert compile_suite.call_count == 1
    assert second["cost_metrics"]["rglob_passes"] == 0
    assert second["cost_metrics"]["operation_count"] <= second["cost_metrics"]["operation_budget"]


def test_routine_light_does_not_write_cache_without_explicit_author_permission(
    tmp_path: Path,
) -> None:
    inventory, compiler = _light_index_fixture(tmp_path)
    with (
        patch.object(suite, "validate_skill_suite", return_value=inventory),
        patch.object(suite, "compile_skill_suite", return_value=compiler),
    ):
        result = suite.run_light_suite(tmp_path)
    assert result["ok"] is True
    assert result["light_suite_index"]["cache_status"] == "miss_not_written"
    assert not (
        tmp_path / ".flowguard" / "work" / "flowguard" / "light-suite-index.json"
    ).exists()


def test_light_index_invalidates_on_member_content_even_when_shape_is_unchanged(
    tmp_path: Path,
) -> None:
    inventory, compiler = _light_index_fixture(tmp_path)
    with (
        patch.object(suite, "validate_skill_suite", return_value=inventory) as validate,
        patch.object(suite, "compile_skill_suite", return_value=compiler) as compile_suite,
    ):
        suite.run_light_suite(tmp_path, allow_cache_write=True)
        (tmp_path / ".agents" / "skills" / "target" / "SKILL.md").write_text(
            "changed content with the same declared shape\n",
            encoding="utf-8",
        )
        second = suite.run_light_suite(tmp_path, allow_cache_write=True)

    assert second["light_suite_index"]["cache_status"] == "miss_written"
    assert validate.call_count == 2
    assert compile_suite.call_count == 2


def test_light_budget_blocks_before_any_recursive_refresh(tmp_path: Path) -> None:
    (tmp_path / ".flowguard").mkdir()
    with (
        patch.object(suite, "validate_skill_suite") as validate,
        patch.object(suite, "compile_skill_suite") as compile_suite,
        patch.object(Path, "rglob", side_effect=AssertionError("light must not recurse")),
    ):
        result = suite.run_light_suite(tmp_path, operation_budget=0)

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert any(
        blocker.startswith("light_suite_operation_budget_exceeded:")
        for blocker in result["blockers"]
    )
    validate.assert_not_called()
    compile_suite.assert_not_called()


def test_light_result_compacts_streams_and_preserves_failed_producer(tmp_path: Path) -> None:
    digest = "sha256:" + "a" * 64
    payload = {
        "artifact_type": "flowguard_skill_suite_certification",
        "ok": False,
        "status": "blocked",
        "scope": "light",
        "requested_members": ["member_a"],
        "passed_members": 0,
        "total_members": 1,
        "inventory_hash": digest,
        "semantic_hash": digest,
        "compiler_version": "compiler-current",
        "inventory": {"inventory_hash": digest, "members": ["member_a"]},
        "compiler": {"compiler_version": "compiler-current", "routes": []},
        "members": [
            {
                "skill_id": "member_a",
                "ok": False,
                "light_ok": False,
                "contract_ok": False,
                "depth_ok": False,
                "depth_classification": "unavailable",
                "results": {
                    "light": {
                        "exit_code": 1,
                        "command": ["python", "-m", "check"],
                        "payload": {"decision": "blocked", "reason": "producer"},
                        "stdout": "same stdout\n",
                        "stderr": "producer failed\n",
                    },
                    "depth": {
                        "exit_code": 1,
                        "command": ["python", "-m", "check"],
                        "payload": {"decision": "blocked", "reason": "producer"},
                        "stdout": "same stdout\n",
                        "stderr": "producer failed\n",
                    },
                },
            }
        ],
        "blockers": ["producer failed"],
        "skipped_checks": [],
        "residual_risk": [],
        "claim_boundary": "light only",
        "execution_profile": "light",
        "modeling_mode": "read_only_audit",
        "selection_reason": "explicit execution profile=light",
        "closed_obligations": [],
        "not_run_obligations": [],
        "escalation_triggers": [],
        "execution_profile_decision": {
            "execution_profile": "light",
            "modeling_mode": "read_only_audit",
            "claim_boundary": "Light only",
            "selection_reason": "explicit execution profile=light",
            "closed_obligations": [],
            "not_run_obligations": [],
            "escalation_triggers": [],
            "admitted": True,
            "status": "pass",
            "ok": True,
        },
        "execution_profile_claim_boundary": "Light only",
        "execution_profile_admitted": True,
        "execution_profile_status": "pass",
        "execution_profile_ok": True,
    }

    run_dir = tmp_path / "light-run"
    _run_id, result_path, _result_sha = suite._write_light_result(payload, str(run_dir))
    result = json.loads(Path(result_path).read_text(encoding="utf-8"))

    # A valid profile must not overwrite the failed producer status.
    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["members"][0]["skill_id"] == "member_a"
    assert "results" not in result["members"][0]
    assert result["members"][0]["artifact_ref"].startswith("details/member-")
    assert result["inventory"]["detail_ref"].startswith("details/inventory-")
    assert result["compiler"]["detail_ref"].startswith("details/compiler-")

    member_detail_path = run_dir / result["members"][0]["artifact_ref"]
    member_detail = json.loads(member_detail_path.read_text(encoding="utf-8"))
    stdout_descriptor = member_detail["results"][0]["stdout"]
    stderr_descriptor = member_detail["results"][0]["stderr"]
    assert suite.verify_text_object(run_dir, stdout_descriptor)
    assert suite.verify_text_object(run_dir, stderr_descriptor)
    # Repeated stdout is content-addressed once, not copied per command.
    stdout_objects = list((run_dir / "objects" / "sha256").glob("*.txt.gz"))
    assert len(stdout_objects) == 2

    stdout_path = run_dir / stdout_descriptor["object_path"]
    stdout_path.write_bytes(b"tampered")
    assert not suite.verify_text_object(run_dir, stdout_descriptor)


def test_pytest_junit_projection_preserves_node_ids_and_skip_reasons(tmp_path: Path) -> None:
    report = tmp_path / "pytest-junit.xml"
    report.write_text(
        """<testsuite tests="4" failures="1" errors="0" skipped="1">
  <testcase classname="tests.demo" name="test_pass" />
  <testcase classname="tests.demo" name="test_skip">
    <skipped type="pytest.skip" message="requires optional service">requires optional service</skipped>
  </testcase>
  <testcase classname="tests.demo" name="test_xfail">
    <skipped type="pytest.xfail" message="known boundary">known boundary</skipped>
  </testcase>
  <testcase classname="tests.demo" name="test_fail">
    <failure type="AssertionError" message="fixture failure">fixture failure</failure>
  </testcase>
</testsuite>""",
        encoding="utf-8",
    )

    projection = suite._pytest_junit_projection(report)
    assert projection is not None
    assert projection["selected"] == 4
    assert projection["passed"] == 1
    assert projection["failed"] == 1
    assert projection["errors"] == 0
    assert projection["skipped"] == 1
    assert projection["xfailed"] == 1
    assert projection["xpassed"] == 0
    assert projection["skip_details"] == [
        {
            "node_id": "tests.demo::test_skip",
            "reason": "requires optional service",
            "required": True,
            "impact": "pytest node was not executed",
            "owner_id": "pytest",
            "claim_boundary": "Pytest child evidence only; broad closure requires zero required skips.",
        }
    ]

    child = ValidationChildResult(
        "pytest",
        "partial",
        "pytest had a required skip",
        payload={"pytest_execution": projection},
    )
    skipped = suite._pytest_skipped_checks((child,))
    assert len(skipped) == 1
    assert skipped[0].check_id == "pytest:tests.demo::test_skip"
    assert skipped[0].reason == "requires optional service"
    assert skipped[0].required is True


def test_required_pytest_skip_is_partial_and_optional_skip_remains_visible() -> None:
    required = suite.CommandOutcome(
        ("python", "-m", "pytest"),
        0,
        payload={
            "status": "pass",
            "ok": True,
            "pytest_execution": {
                "skip_details": [
                    {"node_id": "tests.demo::test_skip", "reason": "fixture"}
                ]
            },
        },
    )
    assert suite._status_from_outcome(required) == "partial"

    optional = suite.CommandOutcome(
        ("python", "-m", "pytest"),
        0,
        payload={
            "status": "pass",
            "ok": True,
            "pytest_execution": {
                "skip_details": [
                    {
                        "node_id": "tests.demo::test_optional",
                        "reason": "exact TestMesh owner",
                        "required": False,
                    }
                ]
            },
        },
    )
    assert suite._status_from_outcome(optional) == "pass"


def test_pytest_capability_block_is_not_misclassified_as_test_failure() -> None:
    """A blocked host capability must stay typed blocked at the parent edge."""

    blocked = suite.CommandOutcome(
        ("python", "scripts/run_flowguard_pytest_shards.py"),
        70,
        payload={
            "status": "blocked",
            "ok": False,
            "capability_partition": {
                "planned_count": 10,
                "runnable_count": 9,
                "not_run_count": 1,
            },
            "pytest_execution": {
                "selected": 9,
                "passed": 9,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
            },
        },
    )

    assert suite._status_from_outcome(blocked) == "blocked"


def test_pytest_junit_projection_preserves_explicit_optional_skip(tmp_path: Path) -> None:
    report = tmp_path / "pytest-optional.xml"
    report.write_text(
        """<testsuite tests="1" skipped="1">
  <testcase classname="tests.demo" name="test_optional">
    <skipped optional="true" message="service not configured" />
  </testcase>
</testsuite>""",
        encoding="utf-8",
    )

    projection = suite._pytest_junit_projection(report)
    assert projection is not None
    assert projection["skip_details"] == [
        {
            "node_id": "tests.demo::test_optional",
            "reason": "service not configured",
            "required": False,
            "impact": "pytest node was not executed",
            "owner_id": "pytest",
            "claim_boundary": "Pytest child evidence only; broad closure requires zero required skips.",
        }
    ]
