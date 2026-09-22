"""Light entry is a bounded read; cache writes are explicit author work."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from flowguard.skill_contracts import ContractCompileReport
from flowguard.skill_suite import (
    FLOWGUARD_AUTHOR_REQUIRED_MEMBER_FILES,
    SkillSuiteMemberReport,
    SkillSuiteReport,
)
from flowguard.model_authority_store import read_selected_model_closure
from flowguard.__main__ import _bounded_read_page
from scripts import check_flowguard_skill_suite as suite


def _fixture(root: Path) -> tuple[SkillSuiteReport, ContractCompileReport]:
    skill = root / ".agents" / "skills" / "target"
    for relative in FLOWGUARD_AUTHOR_REQUIRED_MEMBER_FILES:
        path = skill / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture:{relative}\n", encoding="utf-8")
    (root / ".skillguard" / "flowguard-suite").mkdir(parents=True)
    (root / ".skillguard" / "flowguard-suite" / "suite-map.json").write_text(
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
        ),
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


def test_light_miss_is_read_only_and_starts_no_producer(tmp_path: Path):
    inventory, compiler = _fixture(tmp_path)
    with (
        patch.object(suite, "validate_skill_suite", return_value=inventory) as validate,
        patch.object(suite, "compile_skill_suite", return_value=compiler) as compile_suite,
    ):
        result = suite.run_light_suite(tmp_path)
    assert result["ok"] is True
    assert result["light_suite_index"]["cache_status"] == "miss_not_written"
    assert validate.call_count == 1
    assert compile_suite.call_count == 1
    assert not (tmp_path / ".flowguard" / "work" / "flowguard" / "light-suite-index.json").exists()


def test_light_hit_reuses_cache_without_refresh_or_write(tmp_path: Path):
    inventory, compiler = _fixture(tmp_path)
    with patch.object(suite, "validate_skill_suite", return_value=inventory), patch.object(
        suite, "compile_skill_suite", return_value=compiler
    ):
        suite.run_light_suite(tmp_path, allow_cache_write=True)
    with patch.object(suite, "validate_skill_suite") as validate, patch.object(
        suite, "compile_skill_suite"
    ) as compile_suite:
        result = suite.run_light_suite(tmp_path)
    assert result["ok"] is True
    assert result["light_suite_index"]["cache_status"] == "hit"
    validate.assert_not_called()
    compile_suite.assert_not_called()


def test_corrupt_light_cache_is_not_authority_and_default_run_does_not_repair_it(tmp_path: Path):
    inventory, compiler = _fixture(tmp_path)
    with patch.object(suite, "validate_skill_suite", return_value=inventory), patch.object(
        suite, "compile_skill_suite", return_value=compiler
    ):
        suite.run_light_suite(tmp_path, allow_cache_write=True)
    cache = tmp_path / ".flowguard" / "work" / "flowguard" / "light-suite-index.json"
    cache.write_text("{corrupt\n", encoding="utf-8")
    with patch.object(suite, "validate_skill_suite", return_value=inventory), patch.object(
        suite, "compile_skill_suite", return_value=compiler
    ):
        result = suite.run_light_suite(tmp_path)
    assert result["ok"] is True
    assert result["light_suite_index"]["cache_status"] == "miss_not_written"
    assert cache.read_text(encoding="utf-8") == "{corrupt\n"


def test_light_budget_blocks_without_escalating_to_affected_or_full(tmp_path: Path):
    (tmp_path / ".flowguard").mkdir()
    with patch.object(suite, "validate_skill_suite") as validate, patch.object(
        suite, "compile_skill_suite"
    ) as compile_suite:
        result = suite.run_light_suite(tmp_path, operation_budget=0)
    assert result["status"] == "blocked"
    assert any(
        blocker.startswith("light_suite_operation_budget_exceeded:")
        for blocker in result["blockers"]
    )
    validate.assert_not_called()
    compile_suite.assert_not_called()


def test_selected_model_closure_is_read_only_and_deduplicates_shared_input(tmp_path: Path):
    def write(relative: str, payload: bytes) -> Path:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def sha(path: Path) -> str:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    shared = write(".flowguard/inputs/shared.json", b"{}\n")
    alpha_model = write(".flowguard/models/alpha.py", b"alpha\n")
    alpha_runner = write(".flowguard/runners/alpha.py", b"run-alpha\n")
    beta_model = write(".flowguard/models/beta.py", b"beta\n")
    beta_runner = write(".flowguard/runners/beta.py", b"run-beta\n")

    def instance(model_id: str, model_path: Path, runner_path: Path):
        return SimpleNamespace(
            logical_model_id=model_id,
            model_kind="state_machine",
            model_path=model_path.relative_to(tmp_path).as_posix(),
            model_sha256=sha(model_path),
            runner_path=runner_path.relative_to(tmp_path).as_posix(),
            runner_sha256=sha(runner_path),
            fingerprint=f"sha256:{model_id}",
            purpose_closure_fingerprint=f"sha256:purpose-{model_id}",
            inputs=(
                SimpleNamespace(
                    path=shared.relative_to(tmp_path).as_posix(),
                    sha256=sha(shared),
                ),
            ),
        )

    alpha = instance("alpha", alpha_model, alpha_runner)
    beta = instance("beta", beta_model, beta_runner)
    result = read_selected_model_closure(
        tmp_path,
        selected_model_ids=("alpha", "beta"),
        snapshot=SimpleNamespace(
            fingerprint="sha256:snapshot",
            subject_revision="revision:test",
            unresolved_gap_ids=(),
            model_instances=(alpha, beta),
            relations=(),
        ),
    )

    assert result.authority_integrity == "pass"
    assert result.selected_source_currentness == "current"
    assert result.execution_evidence_status == "not_run"
    serialized = result.to_dict()
    assert "selected_currentness" not in serialized
    assert "execution_status" not in serialized
    assert "as_of_map" not in serialized
    assert serialized["selected_source_currentness"] == "current"
    assert serialized["execution_evidence_status"] == "not_run"
    assert serialized["as_of"] == dict(result.as_of)
    assert dict(result.read_counts)[shared.relative_to(tmp_path).as_posix()] == 1
    assert result.producer_count == 0
    assert result.write_count == 0


def test_bounded_read_page_paginates_large_input_inventory_without_duplicates():
    base_payload = {
        "operation": "read",
        "status": "pass",
        "target_id": "flowguard",
        "requested_model_ids": ["alpha"],
        "selected_model_ids": ["alpha"],
        "as_of": {"authority_head_fingerprint": "sha256:" + "a" * 64},
        "authority_integrity": "pass",
        "selected_source_currentness": "current",
        "execution_evidence_status": "not_run",
        "required_count": 0,
        "run_count": 0,
        "reused_count": 0,
        "producer_count": 0,
        "write_count": 0,
        "stale_obligations": [],
        "blockers": [],
        "claim_boundary": "bounded selected projection read",
    }
    input_paths = [
        f".flowguard/inputs/{index:03d}-{'x' * 80}.json"
        for index in range(120)
    ]
    compact_map = {
        "models": [
            {
                "model_id": "alpha",
                "model_path": ".flowguard/models/alpha.py",
                "runner_path": ".flowguard/runners/alpha.py",
                "input_paths": input_paths,
            }
        ],
        "intents": [],
        "relations": [],
        "boundary_nodes": [],
    }
    head_fingerprint = "sha256:" + "b" * 64
    cursor = None
    seen: list[str] = []
    pages = 0
    while True:
        page = _bounded_read_page(
            base_payload,
            compact_map,
            head_fingerprint=head_fingerprint,
            scope=("alpha",),
            cursor=cursor,
        )
        encoded = json.dumps(
            page, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        assert len(encoded) + 1 <= 8192
        rows = page["map"]["models"]
        assert len(rows) == 1
        seen.extend(rows[0]["input_paths"])
        pages += 1
        next_cursor = page["next_cursor"]
        if next_cursor is None:
            break
        assert next_cursor != cursor
        cursor = next_cursor
        assert pages < 120

    assert pages > 1
    assert seen == input_paths
    assert len(seen) == len(set(seen)) == 120

    with pytest.raises(ValueError, match="another authority head"):
        _bounded_read_page(
            base_payload,
            compact_map,
            head_fingerprint="sha256:" + "c" * 64,
            scope=("alpha",),
            cursor=cursor,
        )
