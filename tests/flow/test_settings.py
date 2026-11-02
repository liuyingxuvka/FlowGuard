"""FG-811 settings: read from the code's configuration, never silently other values."""
from __future__ import annotations

import pytest

from flowguard.flow.checks import WARNING, check_model, reach_line
from flowguard.flow.model import ModelError, load_model

from conftest import DATA, Project

KIT = DATA / "kit"


def load(project, name):
    return load_model(project.root / ".flowguard" / "flow" / f"{name}.py", project.root)


def test_config_reads_the_dataclass_default(project):
    project.kit().flow_from(KIT / "workshop.py")
    loaded = load(project, "workshop")
    model = loaded.model
    assert model.settings == {"maintain_every": 4}
    info = model.setting_info["maintain_every"]
    assert (info.origin, info.where, info.source) == ("code", "counter/config.py: Config.maintain_every", "R9")
    assert "counter/config.py" in loaded.reads
    line = reach_line(check_model(loaded).reach)
    assert line == ("workshop: complete, 171 states (tools explored up to renaming); "
                    "settings maintain_every=4 (counter/config.py: Config.maintain_every)")


def test_changing_the_code_changes_the_model(project):
    project.kit().flow_from(KIT / "workshop.py")
    cfg = project.root / "counter" / "config.py"
    cfg.write_text(cfg.read_text().replace("maintain_every: int = 4", "maintain_every: int = 3"))
    assert load(project, "workshop").model.settings["maintain_every"] == 3


MODEL = '''
from flowguard.flow import Model, need
m = Model("m"{extra})
S = m.settings
{setting}
m.field("count", range(0, 6), 0)

@m.action()
def up(s):
    need(s["count"] < S["limit"], "full")
    s["count"] += 1
MODEL = m
'''


def write(project, setting, extra=""):
    project.kit()
    project.flow("m", MODEL.format(setting=setting, extra=extra))
    return project


def test_a_literal_for_a_setting_the_code_has_is_a_model_error(project):
    write(project, 'm.setting("max_on_loan", 2)', extra=', config="counter.config:Config"')
    with pytest.raises(ModelError, match="read it from the code: drop the value") as err:
        load(project, "m")
    assert (err.value.file, err.value.line) == (".flowguard/flow/m.py", 4)


def test_a_new_setting_the_code_lacks_is_labelled_model_only(project):
    write(project, 'm.setting("limit", 3, source="R12")', extra=', config="counter.config:Config"')
    report = check_model(load(project, "m"))
    assert report.reach["settings"] == [{"name": "limit", "value": "3", "origin": "model only", "where": None,
                                         "source": "R12"}]
    assert "settings limit=3 (model only)" in reach_line(report.reach)


@pytest.mark.parametrize("config, text", [
    ("counter.nothing:Config", "cannot import 'counter.nothing'"),
    ("counter.config:Missing", "has no 'Missing'"),
])
def test_a_missing_config_object_is_a_model_error(project, config, text):
    write(project, 'm.setting("limit")', extra=f', config="{config}"')
    with pytest.raises(ModelError, match=text):
        load(project, "m")


def test_a_missing_config_attribute_is_a_model_error(project):
    write(project, 'm.setting("limit")', extra=', config="counter.config:Config"')
    with pytest.raises(ModelError, match="has no attribute 'limit'"):
        load(project, "m")


def test_a_setting_without_value_needs_a_config(project):
    write(project, 'm.setting("limit")')
    with pytest.raises(ModelError, match="has no value"):
        load(project, "m")


def test_literal_settings_in_a_project_model_are_a_warning(project):
    write(project, 'm.setting("limit", 3)', extra=', covers=["counter/core.py:Counter"]')
    report = check_model(load(project, "m"))
    [w] = [f for f in report.findings if f.kind == "SETTINGS"]
    assert w.cls == WARNING and w.subject == "settings are not imported from the code"
    free = write(Project(project.root.parent / "free"), 'm.setting("limit", 3)')
    assert not [f for f in check_model(load(free, "m")).findings if f.kind == "SETTINGS"]   # no covers


def test_vary_replaces_the_tried_values(project, tmp_path):
    write(project, 'm.setting("limit", 3, vary=[5])')
    missing = {f.subject: f.detail["explained"] for f in check_model(load(project, "m")).findings
               if "explained" in f.detail}            # (count = 3, where the model halts, is a STUCK end)
    assert missing["value count = 4"] == ["limit=5"]
    assert missing["value count = 5"] == ["limit=5"]
    other = write(Project(tmp_path / "default"), 'm.setting("limit", 3)')
    missing = {f.subject: f.detail["explained"] for f in check_model(load(other, "m")).findings
               if "explained" in f.detail}
    assert missing["value count = 4"] == ["limit=4", "limit=6"]       # 0, 1, 2, v-1, v+1, 2v


def test_settings_are_read_when_actions_run(project):
    write(project, 'm.setting("limit", 3)')
    loaded = load(project, "m")
    loaded.model.settings["limit"] = 5                    # what the explanation does in place
    assert len(check_model(loaded, explain=False).graph.states) == 6


def test_an_unreached_reach_rule_is_explained_too(project):
    write(project, 'm.setting("limit", 3, vary=[5], source="R9")\nm.reach("full", lambda s: s["count"] == 5, source="R3")')
    report = check_model(load(project, "m"))
    [f] = [f for f in report.findings if f.subject == "reach 'full'"]
    assert f.cls == "conflict" and f.detail["explained"] == ["limit=5"]
    assert f.sources == ("R3", "R9")                      # the rule and the setting the explanation names
