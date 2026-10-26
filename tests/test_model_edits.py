"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_map_check_names_model_edited_outside_target(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.check import run_check
    from flowguard.map.common import content_digest
    from flowguard.map.inventory import build_inventory
    directory = tmp_path / ".flowguard/models"
    directory.mkdir(parents=True)
    path = directory / "one.py"
    path.write_text('MODEL_ID = "one"\n')
    data = {"schema": "flowguard.map.v1", "components": [], "model_digests": {".flowguard/models/one.py": content_digest(path)}}
    inv = build_inventory(tmp_path, [])
    def guards(strict=False):
        return [f for f in run_check(tmp_path, data, inv, strict=strict) if f.code == "model_edited_outside_target"]
    assert guards() == []
    from flowguard.map.mapfile import fingerprint
    (tmp_path / "app.py").write_text("def run(): return 1\n")
    pointer = fingerprint(tmp_path, ["app.py"])
    path.write_text(path.read_text() + "# modified\n")
    assert fingerprint(tmp_path, ["app.py"]) == pointer  # the model digest, not the code pointer, changes

    assert len(guards()) == 1 and guards()[0].level == "warn"
    assert len(guards(True)) == 1 and guards(True)[0].level == "error"
    del data["model_digests"]
    assert guards() == []
