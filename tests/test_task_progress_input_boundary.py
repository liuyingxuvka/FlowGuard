"""Task-progress normalization keeps completion identity finite and semantic."""
from __future__ import annotations

from pathlib import Path

from flowguard.completion_objective import resolve_completion_objective
from flowguard.validation_ownership import validation_task_body_fingerprint


def _task_path(tmp_path: Path) -> Path:
    path = tmp_path / "openspec" / "changes" / "demo" / "tasks.md"
    path.parent.mkdir(parents=True)
    return path


def test_checkbox_only_progress_and_newlines_do_not_change_task_body_identity(tmp_path: Path):
    path = _task_path(tmp_path)
    path.write_bytes(b"- [ ] 1.1 pending\r\n- [x] 1.2 done\r\n")
    first = validation_task_body_fingerprint(path)
    path.write_bytes(b"- [X] 1.1 pending\n- [ ] 1.2 done\n")
    assert validation_task_body_fingerprint(path) == first


def test_task_meaning_changes_change_identity(tmp_path: Path):
    path = _task_path(tmp_path)
    path.write_text("- [ ] 1.1 pending\n", encoding="utf-8")
    first = validation_task_body_fingerprint(path)
    for replacement in (
        "- [ ] 1.2 pending\n",
        "- [ ] 1.1 changed wording\n",
        "- [ ] 1.1 pending\n- [ ] 1.2 added\n",
        "- [ ] 1.1 pending\n\n- [ ] 1.2 reordered\n",
        "- [ ] 1.1 pending\n  - depends on 2.0\n",
    ):
        path.write_text(replacement, encoding="utf-8")
        assert validation_task_body_fingerprint(path) != first


def test_fenced_code_checkbox_is_semantic_content(tmp_path: Path):
    path = _task_path(tmp_path)
    path.write_text("```text\n- [x] literal code\n```\n- [ ] task\n", encoding="utf-8")
    first = validation_task_body_fingerprint(path)
    path.write_text("```text\n- [ ] literal code\n```\n- [x] task\n", encoding="utf-8")
    assert validation_task_body_fingerprint(path) != first


def test_objective_cycle_identity_still_ignores_task_progress(tmp_path: Path):
    change = tmp_path / "openspec" / "changes" / "demo"
    (change / "specs" / "demo").mkdir(parents=True)
    (change / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
    (change / "proposal.md").write_text("proposal\n", encoding="utf-8")
    (change / "design.md").write_text("design\n", encoding="utf-8")
    task = change / "tasks.md"
    task.write_text("- [ ] 1.1 pending\n", encoding="utf-8")
    (change / "specs" / "demo" / "spec.md").write_text("spec\n", encoding="utf-8")
    first = resolve_completion_objective(tmp_path, "demo")
    task.write_text("- [x] 1.1 pending\n", encoding="utf-8")
    second = resolve_completion_objective(tmp_path, "demo")
    assert second == first
