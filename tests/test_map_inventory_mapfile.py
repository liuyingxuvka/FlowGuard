"""Tests grouped by their model or native component."""
from __future__ import annotations

import pytest, os, json
from pathlib import Path
from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path

@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_model_contract_parsed_once_per_check(tmp_path, monkeypatch, newline):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write, map__release_project as _release_project
    import ast
    from flowguard.map import mapfile
    from flowguard.map.check import run_check
    data, comp = _release_project(tmp_path)
    model = tmp_path / ".flowguard/models/one.py"
    write(tmp_path, str(model.relative_to(tmp_path)), "MODEL_ID='one'\nPARENT='app'\ndef build_explorer(): pass\n")
    model.write_bytes(model.read_text().replace("\n", newline).encode())
    comp["models"] = [".flowguard/models/one.py"]
    from flowguard.map.common import normalize_newlines
    raw, calls, original = model.read_bytes(), [], ast.parse
    def counted(source, *args, **kwargs):
        if normalize_newlines(source.encode("utf-8") if isinstance(source, str) else source) == normalize_newlines(raw):
            calls.append(True)
        return original(source, *args, **kwargs)
    monkeypatch.setattr(ast, "parse", counted)
    run_check(tmp_path, data, build_inventory(tmp_path, mapfile.ignore_patterns(data)))
    assert len(calls) == 1
    first = mapfile.read_model_contract(model)
    first["functions"].clear()
    assert mapfile.read_model_contract(model)["functions"] == ["build_explorer"]
    assert len(calls) == 1
