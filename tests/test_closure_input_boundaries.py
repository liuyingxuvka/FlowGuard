"""Finite regressions for output/source separation at closure boundaries."""
from __future__ import annotations

import os
import json
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


def test_immutable_read_authority_outputs_are_not_source_or_release_excluded(tmp_path: Path):
    from flowguard.runtime_artifacts import is_release_excluded_path

    categories = ("read-projection-indexes", "read-model-shards", "path-quality-details")
    outputs = tuple(".flowguard/models/authority/" + item + "/" + "a" * 64 + ".json" for item in categories)
    maintained = ".flowguard/models/authority/read-model-shards/maintained.py"
    malformed = ".flowguard/models/authority/read-model-shards/not-content-addressed.json"
    for relative in (*outputs, maintained, malformed):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    assert all(ownership._is_evidence_output(item) for item in outputs)
    assert all(not is_release_excluded_path(item) for item in outputs)
    assert not ownership._is_evidence_output(maintained)
    assert not ownership._is_evidence_output(malformed)
    with patch.object(ownership, "_git_candidate_paths", return_value=None):
        without_git = ownership.validation_input_manifest(tmp_path)
    subprocess.run(("git", "init", "-q", str(tmp_path)), check=True)
    subprocess.run(("git", "-C", str(tmp_path), "add", ".flowguard"), check=True)
    with_git = ownership.validation_input_manifest(tmp_path)
    assert with_git == without_git
    assert {item["path"] for item in with_git} == {maintained, malformed}


def _current_release_authority_fixture(root: Path, *, candidate_sha=None):
    from flowguard.model_authority_store import (
        activate_model_revision_set, bootstrap_model_authority, _load_bound_read_projection,
    )
    from tests.test_model_authority_store import SHA_A, SHA_B, SHA_D, snapshot, revision

    manifest = root / ".flowguard/project.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('[flowguard]\nadopted_package_version = "0.68.15"\n', encoding="utf-8")
    base = snapshot("git:" + "a" * 40, SHA_A, "output-base")
    head = bootstrap_model_authority(root, base, bootstrap_evidence_fingerprint=SHA_D)
    candidate = snapshot("git:" + "b" * 40, candidate_sha or SHA_B, "output-current")
    accepted = revision(root, head, base, candidate)
    with patch("flowguard.model_system_inventory.build_manifest_model_system_snapshot", return_value=candidate):
        current, _receipt = activate_model_revision_set(root, candidate, accepted)
    projection = _load_bound_read_projection(root, current)
    required = {
        ".flowguard/models/authority/read-projection-indexes/" + projection["index_fingerprint"][7:] + ".json",
        *(".flowguard/models/authority/read-model-shards/" + item["shard_fingerprint"][7:] + ".json" for item in projection["index"]["models"].values()),
        *(".flowguard/models/authority/path-quality-details/" + item.detail_evidence_fingerprint[7:] + ".json" for item in accepted.path_quality_results),
    }
    return required


def test_release_closure_retains_only_current_bound_read_authority(tmp_path: Path):
    required = _current_release_authority_fixture(tmp_path)
    unrelated = ".flowguard/models/authority/read-model-shards/" + "f" * 64 + ".json"
    (tmp_path / unrelated).write_text("{}\n", encoding="utf-8")
    paths = ownership.model_authority_release_paths(tmp_path)
    assert len(paths) == len(set(paths))
    assert required <= set(paths)
    assert unrelated not in paths
    assert not required & {item["path"] for item in ownership.validation_input_manifest(tmp_path)}


def test_release_closure_rejects_missing_tampered_and_foreign_bound_objects(tmp_path: Path):
    required = _current_release_authority_fixture(tmp_path)
    for relative in sorted(required):
        path = tmp_path / relative
        original = path.read_bytes()
        path.unlink()
        with pytest.raises((ValueError, OSError)):
            ownership.model_authority_release_paths(tmp_path)
        path.write_bytes(original)
        payload = json.loads(original)
        payload["foreign_owner"] = "model:foreign"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            ownership.model_authority_release_paths(tmp_path)
        path.write_bytes(original)
    assert required <= set(ownership.model_authority_release_paths(tmp_path))
    from flowguard.model_authority_store import load_current_model_authority_state
    from tests.test_model_authority_store import SHA_C

    # Both observations are real authenticated states. A pointer switch between
    # manifest discovery and the typed read must not combine their two closures.
    current = load_current_model_authority_state(tmp_path, reverify_current_sources=False)
    successor_root = tmp_path / "independent-authority"
    _current_release_authority_fixture(successor_root, candidate_sha=SHA_C)
    foreign = load_current_model_authority_state(successor_root, reverify_current_sources=False)
    assert foreign.head.fingerprint != current.head.fingerprint
    with patch("flowguard.model_authority_store.load_current_model_authority_state", return_value=foreign):
        with pytest.raises(ValueError, match="authority changed during closure observation"):
            ownership.model_authority_release_paths(tmp_path)
    with patch("flowguard.model_authority_store.load_current_model_authority_state", return_value=current):
        assert required <= set(ownership.model_authority_release_paths(tmp_path))


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
