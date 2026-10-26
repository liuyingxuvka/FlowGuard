"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_read_field_status_names_writers_and_model():
    from pathlib import Path
    from flowguard.map.views import render_field
    from flowguard.map.mapfile import load_map,ignore_patterns
    from flowguard.map.inventory import build_inventory
    root=Path(__file__).resolve().parents[1];data=load_map(root)
    text=render_field(root,data,build_inventory(root,ignore_patterns(data),write_cache=False),'status')
    assert 'component_pointer' in text and 'cmd_confirm' in text and 'merge_target_map' in text


def test_json_key_written_and_read_across_components(tmp_path):
    from _fg_helpers import view__field_project as _field_project
    from flowguard.map.views import render_field
    data,inv=_field_project(tmp_path)
    text=render_field(tmp_path,data,inv,'record_code')
    assert 'code writes: writer.py:write' in text and 'code reads: reader.py:read' in text
    assert 'reader (state:' in text and 'writer (state:' in text
    assert 'rules: none (a field no rule names:' in text


def test_field_view_within_budget(tmp_path):
    from _fg_helpers import view__field_project as _field_project
    from flowguard.map.views import render_field
    data,inv=_field_project(tmp_path)
    assert len(render_field(tmp_path,data,inv,'status'))<=1500
    assert 'status_model State.status' in render_field(tmp_path,data,inv,'status')


def test_field_view_imports_no_model(tmp_path):
    from pathlib import Path
    from _fg_helpers import view__field_project as _field_project
    import sys
    from flowguard.map.views import render_field
    data,inv=_field_project(tmp_path)
    assert 'status_visible' in render_field(tmp_path,data,inv,'status')
    assert not (tmp_path/'model_imported.marker').exists()
    assert not any(getattr(module,'__file__',None) and Path(module.__file__).resolve().is_relative_to(tmp_path) for module in tuple(sys.modules.values()))
