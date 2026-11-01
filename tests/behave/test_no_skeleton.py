"""Source-only fallback controls: no import or construction of the application."""

import json

import pytest

from flowguard.behave import skeleton


def test_cli_fallback_retains_all_real_entries_without_running_them(tmp_path):
    commands = [f"c{index}" for index in range(14)]
    source = (
        'import argparse\nraise AssertionError("application must not be imported")\n'
        'def main():\n p = argparse.ArgumentParser()\n verbs = p.add_subparsers()\n'
        + ''.join(f' verbs.add_parser("{name}")\n' for name in commands)
        + 'if __name__ == "__main__": main()\n'
    )
    (tmp_path / "cli.py").write_text(source)
    with pytest.raises(skeleton.NoSkeleton) as caught:
        skeleton.derive(tmp_path)
    facts = caught.value.facts
    assert facts["world_kind"] == "TempProject"
    assert {row["name"] for row in facts["entries"] if row["kind"] == "cli_command"} == set(commands)
    assert facts["input_files"] == ["cli.py"]
    assert facts["source_functions"] == ["cli.py#main"]
    assert facts["corrections"] == []
    text = skeleton.render_fallback(facts)
    assert "world kind needed: TempProject" in text
    assert f"{len(facts['entries']) - 8} more entries retained" in text
    assert "no runnable WORLD declaration is generated" in text
    assert "WORLD =" not in text and "from flowguard import" not in text
    json.dumps(facts)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["cli.py"]


def test_function_fallback_reuses_supplied_static_facts(tmp_path, monkeypatch):
    (tmp_path / "pipeline.py").write_text(
        'raise AssertionError("application must not be imported")\n'
        'def convert(value): return value * 2\n'
    )
    calls = {"inventory": 0, "discovery": 0}
    build, discover = skeleton.build_inventory, skeleton.discover_inventory

    def inventory(*args, **kwargs):
        calls["inventory"] += 1
        return build(*args, **kwargs)

    def discovery(*args, **kwargs):
        calls["discovery"] += 1
        return discover(*args, **kwargs)

    monkeypatch.setattr(skeleton, "build_inventory", inventory)
    monkeypatch.setattr(skeleton, "discover_inventory", discovery)
    with pytest.raises(skeleton.NoSkeleton) as caught:
        skeleton.derive(tmp_path)
    facts = caught.value.facts
    assert calls == {"inventory": 1, "discovery": 1}
    assert facts["world_kind"] == "Calls"
    assert facts["source_functions"] == ["pipeline.py#convert"]
    assert facts["entries"] == [{"path": "pipeline.py", "symbol": "convert", "kind": "function", "name": "convert", "line": 2}]
    assert "purity has not been judged" in skeleton.render_fallback(facts)
    assert str(caught.value) == facts["reason"]
    json.dumps(facts)
    assert not (tmp_path / ".flowguard").exists()


def test_ambiguous_roots_offer_a_real_pin_but_invalid_input_is_still_an_error(tmp_path):
    path = tmp_path / "example.py"
    path.write_text(
        'raise AssertionError("application must not be imported")\n'
        'class A:\n def __init__(self): self.count = 0\n def go(self): self.count += 1\n'
        'class B:\n def __init__(self): self.count = 0\n def go(self): self.count += 1\n'
    )
    with pytest.raises(skeleton.NoSkeleton) as caught:
        skeleton.derive(tmp_path)
    facts = caught.value.facts
    assert facts["world_kind"] == "MACHINE"
    assert len(facts["corrections"]) == 2
    assert "choose one; not written" in skeleton.render_fallback(facts)
    assert not (tmp_path / ".flowguard").exists()
    directory = tmp_path / ".flowguard"
    directory.mkdir()
    correction = directory / "skeleton.py"
    correction.write_text(facts["corrections"][0] + "\n")
    assert skeleton.derive(tmp_path)["system"] == "example:A"
    for invalid, code in [('value = 1\n', 'config_in_skeleton'),
                          ('pin("system", "missing:Root", why="not here")\n', 'pin_not_buildable')]:
        correction.write_text(invalid)
        with pytest.raises(skeleton.SkeletonError, match=code) as invalid_input:
            skeleton.derive(tmp_path)
        assert not isinstance(invalid_input.value, skeleton.NoSkeleton)
    correction.write_text(facts["corrections"][0] + "\n")
    path.write_text('def broken(:\n')
    with pytest.raises(skeleton.SkeletonError, match="source_not_parseable") as malformed:
        skeleton.derive(tmp_path)
    assert not isinstance(malformed.value, skeleton.NoSkeleton)
