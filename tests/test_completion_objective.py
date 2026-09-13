"""Focused tests for explicit, reviewed completion-objective identities."""

from __future__ import annotations

from pathlib import Path

import pytest

from flowguard.completion_objective import (
    CompletionObjectiveError,
    resolve_completion_objective,
)


def _write_change(root: Path, name: str = "demo-objective") -> Path:
    change = root / "openspec" / "changes" / name
    (change / "specs" / "demo").mkdir(parents=True)
    (change / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
    (change / "proposal.md").write_text("## Why\n\nA reviewed objective.\n", encoding="utf-8")
    (change / "design.md").write_text("## Context\n\nA bounded design.\n", encoding="utf-8")
    (change / "tasks.md").write_text("- [ ] 1.1 pending\n", encoding="utf-8")
    (change / "specs" / "demo" / "spec.md").write_text(
        "## ADDED Requirements\n\n### Requirement: Demo\n\nThe system SHALL prove it.\n\n"
        "#### Scenario: Pass\n- **WHEN** run\n- **THEN** pass\n",
        encoding="utf-8",
    )
    return change


def test_objective_is_deterministic_and_ignores_task_progress(tmp_path: Path):
    change = _write_change(tmp_path)
    first = resolve_completion_objective(tmp_path, change.name)
    (change / "tasks.md").write_text("- [x] 1.1 complete\n", encoding="utf-8")
    second = resolve_completion_objective(tmp_path, change.name)

    assert first == second
    assert first.artifact_count == 4
    assert first.fingerprint.startswith("sha256:")
    assert "tasks.md" not in first.artifact_paths


def test_objective_changes_when_reviewed_artifact_changes(tmp_path: Path):
    change = _write_change(tmp_path)
    first = resolve_completion_objective(tmp_path, change.name)
    (change / "proposal.md").write_text("## Why\n\nA different objective.\n", encoding="utf-8")
    second = resolve_completion_objective(tmp_path, change.name)

    assert second.fingerprint != first.fingerprint


@pytest.mark.parametrize(
    ("name", "code"),
    (
        ("missing-objective", "completion_objective_unknown"),
        ("../escape", "completion_objective_unsafe_name"),
    ),
)
def test_invalid_objective_is_typed_and_read_only(tmp_path: Path, name: str, code: str):
    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    with pytest.raises(CompletionObjectiveError) as error:
        resolve_completion_objective(tmp_path, name)
    assert error.value.code == code


def test_unregistered_artifact_blocks(tmp_path: Path):
    change = _write_change(tmp_path)
    (change / "notes.txt").write_text("not part of the objective\n", encoding="utf-8")

    with pytest.raises(CompletionObjectiveError) as error:
        resolve_completion_objective(tmp_path, change.name)
    assert error.value.code == "completion_objective_unregistered_artifact"


def test_missing_spec_blocks(tmp_path: Path):
    change = _write_change(tmp_path)
    for path in (change / "specs").rglob("*.md"):
        path.unlink()

    with pytest.raises(CompletionObjectiveError) as error:
        resolve_completion_objective(tmp_path, change.name)
    assert error.value.code == "completion_objective_missing_specs"


@pytest.mark.flowguard_capability("path_escape.posix_symlink")
def test_symlinked_objective_artifact_blocks_when_platform_allows_symlink(tmp_path: Path):
    change = _write_change(tmp_path)
    target = change / "proposal.md"
    backup = change / "proposal.real.md"
    target.rename(backup)
    try:
        target.symlink_to(backup)
    except OSError as exc:
        target.unlink(missing_ok=True)
        backup.rename(target)
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("symlink capability is unavailable on this runner")
        raise

    with pytest.raises(CompletionObjectiveError) as error:
        resolve_completion_objective(tmp_path, change.name)
    assert error.value.code == "completion_objective_reparse_point"
