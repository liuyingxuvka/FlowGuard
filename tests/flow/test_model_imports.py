"""A fresh model import must leave its caller's real module identities intact."""
import importlib
from pathlib import Path
import sys

import pytest

from flowguard.flow.model import load_model


def test_loading_with_the_engine_source_root_restores_actual_api_and_collected_modules(tmp_path):
    from flowguard.map import common, requests
    import flowguard

    root = Path(__file__).resolve().parents[2]
    path = tmp_path / 'model.py'
    path.write_text("from flowguard.flow import Model\nm=Model('caller')\nm.field('done', (False,True), False)\nm.terminal('done', (False,True))\nMODEL=m\n")
    before = {name: module for name, module in sys.modules.items()
              if getattr(module, '__file__', None)
              and Path(module.__file__).resolve().is_relative_to(root)}
    error = common.MapError
    loaded = load_model(path, root)
    assert loaded.model.id == 'model'
    assert importlib.import_module('flowguard.map.common') is common
    assert importlib.import_module('flowguard.map.requests') is requests
    assert flowguard.map.common is common and common.MapError is error
    assert all(sys.modules.get(name) is module for name, module in before.items())


@pytest.mark.parametrize('other_root', [False, True])
def test_loading_source_reads_fresh_bytes_and_restores_the_callers_package(project, monkeypatch, other_root):
    caller = project.root.parent / 'caller' if other_root else project.root
    folder = caller / 'same_name'
    folder.mkdir(parents=True)
    (folder / '__init__.py').write_text('')
    source = folder / 'config.py'
    source.write_text('limit = 1\n')
    monkeypatch.syspath_prepend(str(caller))
    config = importlib.import_module('same_name.config')
    package = importlib.import_module('same_name')
    try:
        project.file('same_name/__init__.py', '')
        project.file('same_name/config.py', 'limit = 2\n')
        path = project.flow('fresh', "from same_name.config import limit\nfrom flowguard.flow import Model\nm=Model('fresh')\nm.field('limit', (1,2), limit)\nMODEL=m\n")
        loaded = load_model(path, project.root)
        assert loaded.model.fields[0].init == 2
        assert 'same_name/config.py' in loaded.reads
        assert importlib.import_module('same_name.config') is config
        assert importlib.import_module('same_name') is package
        assert package.config is config and config.limit == 1
    finally:
        for name in ('same_name.config', 'same_name'):
            sys.modules.pop(name, None)
