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


def _archive(change: Path, day: str = "2026-09-28") -> Path:
    archive = change.parent / "archive"
    archive.mkdir(exist_ok=True)
    return change.rename(archive / f"{day}-{change.name}")


def test_archive_keeps_original_identity_and_task_progress(tmp_path: Path):
    change = _write_change(tmp_path)
    before = resolve_completion_objective(tmp_path, change.name)
    archived = _archive(change)
    (archived / "tasks.md").write_text("- [x] done\n", encoding="utf-8")
    assert resolve_completion_objective(tmp_path, change.name) == before
    (archived / "design.md").write_text("Changed reviewed behavior\n", encoding="utf-8")
    assert resolve_completion_objective(tmp_path, change.name).fingerprint != before.fingerprint


@pytest.mark.parametrize("duplicate_active", [True, False])
def test_duplicate_archive_identity_is_rejected(tmp_path: Path, duplicate_active: bool):
    change = _write_change(tmp_path)
    _archive(change)
    second = _write_change(tmp_path)
    if not duplicate_active:
        _archive(second, "2026-09-29")
    expected = "completion_objective_duplicate_identity" if duplicate_active else "completion_objective_ambiguous_archive"
    with pytest.raises(CompletionObjectiveError) as error:
        resolve_completion_objective(tmp_path, change.name)
    assert error.value.code == expected


@pytest.mark.parametrize("name", [
    "2026-09-28-other-demo-objective", "2026-09-28-demo-objective-extra",
    "2026-02-30-demo-objective", "demo-objective", "2026-9-28-demo-objective",
])
def test_archive_requires_exact_name_and_real_date(tmp_path: Path, name: str):
    archive = tmp_path / "openspec" / "changes" / "archive"
    (archive / name).mkdir(parents=True)
    with pytest.raises(CompletionObjectiveError) as error:
        resolve_completion_objective(tmp_path, "demo-objective")
    assert error.value.code == "completion_objective_unknown"


@pytest.mark.parametrize("reparse_archive", [True, False])
def test_archive_and_candidate_reparse_points_are_rejected(tmp_path: Path, monkeypatch, reparse_archive: bool):
    from flowguard import completion_objective as module
    archived = _archive(_write_change(tmp_path))
    forbidden = archived.parent if reparse_archive else archived
    original = module._is_reparse_point
    monkeypatch.setattr(module, "_is_reparse_point", lambda path: path == forbidden or original(path))
    with pytest.raises(CompletionObjectiveError) as error:
        resolve_completion_objective(tmp_path, "demo-objective")
    assert error.value.code == ("completion_objective_invalid_archive" if reparse_archive else "completion_objective_invalid_root")


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
