"""Parent/model-consumer identity stays semantic across output directories."""
from __future__ import annotations

from flowguard.validation_ownership import (
    _canonical_owner_command,
    _normalize_model_receipt_result,
)


def test_output_directory_does_not_change_owner_command_identity(tmp_path):
    left = _canonical_owner_command(
        ("python", "-m", "owner", "--receipt-dir", str(tmp_path / "run-a")),
        workspace_root=tmp_path,
    )
    right = _canonical_owner_command(
        ("python", "-m", "owner", "--receipt-dir", str(tmp_path / "run-b")),
        workspace_root=tmp_path,
    )
    assert left == right


def test_model_consumer_identity_keeps_semantic_result_and_drops_paths():
    left = _normalize_model_receipt_result(
        {"status": "pass", "artifact_paths": ["run-a.json"], "model_fingerprint": "sha256:a"}
    )
    right = _normalize_model_receipt_result(
        {"status": "pass", "artifact_paths": ["run-b.json"], "model_fingerprint": "sha256:a"}
    )
    assert left == right
