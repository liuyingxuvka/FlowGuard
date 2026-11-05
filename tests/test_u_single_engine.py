"""The forced upgrade leaves one executable model engine and one change route."""
import importlib.util
from pathlib import Path

import pytest

from flowguard.flow.project import ProjectError, model_files, require_current_format


@pytest.mark.parametrize("name", ["core", "explorer", "kit", "workflow", "scenario", "behave", "map.mapfile", "map.target"])
def test_retired_engines_and_target_route_are_absent(name):
    assert importlib.util.find_spec("flowguard." + name) is None


@pytest.mark.parametrize("legacy", ["map.json", "models/old.py", "target/PLAN.txt"])
def test_checks_require_explicit_migration_of_old_model_artifacts(tmp_path, legacy):
    old = tmp_path / ".flowguard" / legacy
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text("old format must never be executed")
    with pytest.raises(ProjectError, match="upgrade"):
        require_current_format(tmp_path)


def test_empty_old_directory_does_not_create_a_second_model_format(tmp_path):
    (tmp_path / ".flowguard/models").mkdir(parents=True)
    assert model_files(tmp_path) == []
