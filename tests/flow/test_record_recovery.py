"""Record recovery advice works for the project's actual storage mode."""
import pytest

from flowguard.flow.project import ConflictsUnreadable, read_conflicts


@pytest.mark.parametrize("git_mode", ["none", "untracked", "tracked"])
def test_damaged_record_recovery_uses_an_available_source(project, git_mode):
    project.file(".gitignore", ".flowguard/cache/\n")
    if git_mode == "untracked":
        project.commit()
    record = project.file(".flowguard/conflicts.json", '{"conflicts": []}\n')
    original = record.read_bytes()
    if git_mode == "tracked":
        project.commit()
    record.write_text("{}")
    with pytest.raises(ConflictsUnreadable) as caught:
        read_conflicts(project.root)
    message = str(caught.value)
    if git_mode == "tracked":
        assert "git checkout -- .flowguard/conflicts.json" in message
        project.git("checkout", "--", ".flowguard/conflicts.json")
        assert record.read_bytes() == original
    else:
        assert "git checkout" not in message
        assert "restore .flowguard/conflicts.json from your project backup" in message
        assert record.read_text() == "{}"
