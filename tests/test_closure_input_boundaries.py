"""Finite regressions for output/source separation at closure boundaries."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import flowguard.validation_ownership as ownership
from flowguard.execution_profiles import (
    ValidationExecutionPolicy,
    ValidationExecutionPolicyError,
)
from flowguard.source_identity import (
    functional_source_fingerprint,
    source_file_fingerprint,
)
from flowguard.validation_ownership import ValidationOwnerContract, build_owner_current


def test_new_source_observation_rehashes_same_size_restored_times(tmp_path: Path):
    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")
    before_stat = source.stat()
    before = ownership._fingerprint_manifest_paths(tmp_path, ("source.py",))
    source.write_text("value = 2\n", encoding="utf-8")
    os.utime(source, ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns))
    after = ownership._fingerprint_manifest_paths(tmp_path, ("source.py",))
    assert source.stat().st_size == before_stat.st_size
    assert source.stat().st_mtime_ns == before_stat.st_mtime_ns
    assert after != before
    assert after[0]["sha256"] == source_file_fingerprint(source)


def test_generated_authority_categories_do_not_enter_generic_source(tmp_path: Path):
    relatives = tuple(
        ".flowguard/models/authority/" + category + "/" + "a" * 64 + ".json"
        for category in ("boundary-contracts", "rollback-contracts")
    )
    for relative in relatives:
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("{}\n", encoding="utf-8")
        assert ownership._is_evidence_output(relative)
    assert ownership._fingerprint_manifest_paths(tmp_path, relatives) == ()
    with patch.object(ownership, "_git_candidate_paths", return_value=None):
        assert ownership.resolve_input_manifest(tmp_path, (".flowguard/**/*",)) == ()


def test_unknown_authority_category_is_not_silently_output(tmp_path: Path):
    relative = ".flowguard/models/authority/unknown/source.py"
    source = tmp_path / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    assert not ownership._is_evidence_output(relative)
    with patch.object(ownership, "_git_candidate_paths", return_value=None):
        without_git = ownership.resolve_input_manifest(tmp_path, (".flowguard/**/*",))
    subprocess.run(("git", "init", "-q", str(tmp_path)), check=True)
    subprocess.run(("git", "-C", str(tmp_path), "add", relative), check=True)
    with_git = ownership.resolve_input_manifest(tmp_path, (".flowguard/**/*",))
    assert tuple(row["path"] for row in without_git) == (relative,), without_git
    assert with_git == without_git, (with_git, without_git)


def test_validation_manifest_includes_model_selector_sources():
    observed = (
        {"path": "examples/bounded_system_composition/benchmark.py", "sha256": "sha256:" + "a" * 64},
        {"path": "README.zh-CN.md", "sha256": "sha256:" + "b" * 64},
        {"path": "tests/test_example.py", "sha256": "sha256:" + "c" * 64},
    )

    manifest = ownership._validation_input_manifest_from_observation(observed)

    assert tuple(row["path"] for row in manifest) == (
        "README.zh-CN.md",
        "examples/bounded_system_composition/benchmark.py",
        "tests/test_example.py",
    )


def test_supervisor_resource_policy_change_preserves_functional_owner_identity(tmp_path: Path):
    source = tmp_path / "source.txt"
    source.write_text("current\n", encoding="utf-8")
    base = ValidationOwnerContract(
        owner_id="owner",
        command=("python", "-c", "pass"),
        input_patterns=("source.txt",),
        obligation_ids=("obligation:owner",),
        resource_keys=("resource:slow",),
    )
    changed_supervision = ValidationOwnerContract(
        owner_id="owner",
        command=base.command,
        input_patterns=base.input_patterns,
        obligation_ids=base.obligation_ids,
        resource_keys=("resource:fast",),
        termination_policy="terminate_grace_force_kill_confirm_zero_descendants",
    )
    first = build_owner_current(tmp_path, base, all_contracts=(base,))
    second = build_owner_current(
        tmp_path,
        changed_supervision,
        all_contracts=(changed_supervision,),
    )
    assert first.contract_hash == second.contract_hash
    assert first.owner_identity == second.owner_identity


def test_declared_resource_argv_change_preserves_functional_owner_identity(
    tmp_path: Path,
):
    source = tmp_path / "source.txt"
    source.write_text("current\n", encoding="utf-8")
    first_contract = ValidationOwnerContract(
        owner_id="owner",
        command=("python", "-m", "child", "--run-timeout", "900"),
        input_patterns=("source.txt",),
        obligation_ids=("obligation:owner",),
        resource_argv_options=("--run-timeout",),
    )
    second_contract = ValidationOwnerContract(
        owner_id="owner",
        command=("python", "-m", "child", "--run-timeout", "6000"),
        input_patterns=("source.txt",),
        obligation_ids=("obligation:owner",),
        resource_argv_options=("--run-timeout",),
    )

    first = build_owner_current(
        tmp_path,
        first_contract,
        all_contracts=(first_contract,),
    )
    second = build_owner_current(
        tmp_path,
        second_contract,
        all_contracts=(second_contract,),
    )

    assert first.command == second.command
    assert first.contract_hash == second.contract_hash
    assert first.owner_identity == second.owner_identity


def test_product_visible_timeout_change_remains_functional_input(tmp_path: Path):
    source = tmp_path / "source.txt"
    source.write_text("current\n", encoding="utf-8")
    first_contract = ValidationOwnerContract(
        owner_id="owner",
        command=("python", "-m", "product", "--timeout", "2"),
        input_patterns=("source.txt",),
        obligation_ids=("obligation:product-timeout",),
    )
    second_contract = ValidationOwnerContract(
        owner_id="owner",
        command=("python", "-m", "product", "--timeout", "5"),
        input_patterns=("source.txt",),
        obligation_ids=("obligation:product-timeout",),
    )

    first = build_owner_current(
        tmp_path,
        first_contract,
        all_contracts=(first_contract,),
    )
    second = build_owner_current(
        tmp_path,
        second_contract,
        all_contracts=(second_contract,),
    )

    assert first.command != second.command
    assert first.contract_hash != second.contract_hash
    assert first.owner_identity != second.owner_identity


def test_execution_policy_is_strict_and_budget_only_manifest_changes_are_semantic_noops(
    tmp_path: Path,
):
    project = tmp_path / ".flowguard" / "project.toml"
    project.parent.mkdir(parents=True)
    project.write_text(
        """
[flowguard]
schema_version = "1.0"
[flowguard_execution]
schema = "flowguard.resource_policy.v1"
invocation_timeout_seconds = 7200
observation_timeout_seconds = 120
collection_timeout_seconds = 240
pytest_shard_timeout_seconds = 2400
[flowguard_execution.owner_timeout_seconds]
pytest = 6000
""".strip()
        + "\n",
        encoding="utf-8",
    )
    policy = ValidationExecutionPolicy.from_project(tmp_path)
    assert policy.owner_timeout("pytest") == 6000.0
    first = functional_source_fingerprint(tmp_path, ".flowguard/project.toml")
    project.write_text(
        project.read_text(encoding="utf-8").replace("pytest = 6000", "pytest = 9000"),
        encoding="utf-8",
    )
    assert functional_source_fingerprint(tmp_path, ".flowguard/project.toml") == first
    with pytest.raises(ValidationExecutionPolicyError):
        ValidationExecutionPolicy.from_mapping(
            {"unknown": 1}
        )
    with pytest.raises(ValidationExecutionPolicyError):
        ValidationExecutionPolicy.from_mapping(
            {"invocation_timeout_seconds": float("inf")}
        )
