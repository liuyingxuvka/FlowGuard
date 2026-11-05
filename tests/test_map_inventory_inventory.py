"""Tests grouped by their model or native component."""
from __future__ import annotations
from _pure_helpers import _INJECTED_SERVICE, _INJECTED_CLI, injected_project as _injected_project, write as map_write, write as flowguard_map_contracts421_write
import json
import pytest
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
import pytest, os, json

def test_import_literals_survive_inventory_cache(tmp_path):
    import json
    import os
    from flowguard.map.inventory import CACHE_SCHEMA, build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    flowguard_map_contracts421_write(tmp_path, 'a.py', 'TARGET = __import__("pkg")\n')
    os.utime(tmp_path / 'a.py', (1, 1))
    first = build_inventory(tmp_path, DEFAULT_IGNORE)
    cached = json.loads((tmp_path / '.flowguard/cache/inventory.json').read_text())
    assert cached['schema'] == CACHE_SCHEMA == 'flowguard.map.inventory_cache.v5'
    assert cached['files']['a.py']['import_literals'] == ['pkg']
    second = build_inventory(tmp_path, DEFAULT_IGNORE)
    assert first.py['a.py'].import_literals == second.py['a.py'].import_literals == {'pkg'}

def test_module_resolver_keeps_package_then_script_then_root_precedence():
    from flowguard.map.inventory import resolve_module, resolve_import
    files = {'scripts/runner.py', 'scripts/helper.py', 'library/helper.py', 'other/helper.py', 'library/pkg/__init__.py'}
    assert resolve_module('helper', 'scripts/runner.py', {'helper': 'package/helper.py'}, files, ('library',)) == 'package/helper.py'
    assert resolve_module('helper', 'scripts/runner.py', {}, files, ('library',)) == 'scripts/helper.py'
    assert resolve_module('helper', 'scripts/runner.py', {}, files | {'scripts/__init__.py'}, ('library', 'other')) == 'library/helper.py'
    assert resolve_module('pkg', 'runner.py', {}, files, ('library',)) == 'library/pkg/__init__.py'
    assert resolve_import('helper:_private', {}, importer='scripts/runner.py', py_paths=files) == 'scripts/helper.py'

def test_type_checking_imports_are_not_dependencies(project):
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    inv = build_inventory(project, DEFAULT_IGNORE)
    assert 'shop/api.py' not in inv.file_deps.get('shop/orders.py', set())
    assert 'shop/storage.py' in inv.file_deps['shop/orders.py']
    assert 'web/client.js' in inv.file_deps['web/app.js']

def test_inventory_cache_never_trusts_a_parse_of_a_just_written_file(project):
    import os
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    import os
    path = project / 'shop/storage.py'
    path.write_text('def save(x):\n    return x\n', encoding='utf-8')
    first = build_inventory(project, DEFAULT_IGNORE)
    assert 'save' in first.py['shop/storage.py'].symbols
    st = path.stat()
    path.write_text('def keep(x):\n    return x\n', encoding='utf-8')
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    second = build_inventory(project, DEFAULT_IGNORE)
    assert 'keep' in second.py['shop/storage.py'].symbols

def test_parse_cache_written_by_other_parser_code_is_ignored(project):
    import os, json
    import json
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    import os
    import time
    path = project / 'shop/storage.py'
    old = time.time_ns() - 10000000000
    os.utime(path, ns=(old, old))
    build_inventory(project, DEFAULT_IGNORE)
    cache = project / '.flowguard/cache/inventory.json'
    data = json.loads(cache.read_text(encoding='utf-8'))
    data['files']['shop/storage.py']['symbols'] = ['stale_symbol']
    data['parser'] = 'written-by-an-older-flowguard'
    cache.write_text(json.dumps(data), encoding='utf-8')
    assert 'save' in build_inventory(project, DEFAULT_IGNORE).py['shop/storage.py'].symbols

@pytest.mark.parametrize('expression', ['pkg.B', "getattr(pkg, 'B')", 'hasattr(pkg, name)', 'pkg.__all__'])
def test_lazy_facade_module_attribute_and_reflection_reach_exports(tmp_path, expression):
    import pytest
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    map_write(tmp_path, 'pkg/__init__.py', "_TABLE = {'pkg.a': ('A',), 'pkg.b': ('B',)}\ndef __getattr__(name):\n    pass\n")
    map_write(tmp_path, 'pkg/a.py', 'A = 1\n')
    map_write(tmp_path, 'pkg/b.py', 'B = 2\n')
    map_write(tmp_path, 'tests/test_reflect.py', f"import pkg\nname = 'B'\nvalue = {expression}\n")
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    assert 'pkg/b.py' in inv.file_deps['tests/test_reflect.py']

def test_script_directory_imports_resolve_to_sibling_files(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.inventory import build_inventory
    map_write(tmp_path, 'scripts/run.py', 'from helper import value\nimport json\n')
    map_write(tmp_path, 'scripts/helper.py', 'value = 1\n')
    map_write(tmp_path, 'pkg/__init__.py', '')
    map_write(tmp_path, 'pkg/a.py', 'import helper\n')
    map_write(tmp_path, 'pkg/helper.py', 'value = 2\n')
    inv = build_inventory(tmp_path, [])
    assert inv.file_deps.get('scripts/run.py') == {'scripts/helper.py'}
    assert 'pkg/helper.py' not in inv.file_deps.get('pkg/a.py', set())

def test_inventory_cache_recovers_bodies_after_a_body_free_read(tmp_path):
    import os
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    import os
    import time
    map_write(tmp_path, 'pkg/a.py', 'def f(a):\n' + '    a = a + 1\n' * 10 + '    return a\n')
    past = time.time() - 60
    os.utime(tmp_path / 'pkg/a.py', (past, past))
    assert build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False).py['pkg/a.py'].bodies == []
    assert build_inventory(tmp_path, DEFAULT_IGNORE).py['pkg/a.py'].bodies

def test_function_digests_separate_nested_and_module_changes():
    from flowguard.map.inventory import function_digests
    source = 'VALUE=1\nclass C:\n    field=1\n    def method(self):\n        def inner(): return 1\n        return inner()\n'
    before = function_digests(source)
    nested = function_digests(source.replace('inner(): return 1', 'inner(): return 2'))
    assert before['functions']['C.method'] == nested['functions']['C.method']
    assert before['functions']['C.method.inner'] != nested['functions']['C.method.inner']
    assert before['classes'] == nested['classes']
    assert function_digests(source.replace('field=1', 'field=2'))['classes'] != before['classes']
    assert function_digests(source.replace('VALUE=1', 'VALUE=2'))['bindings'] != before['bindings']


def test_renamed_local_variables_match_duplicate_bodies_but_global_calls_do_not(tmp_path):
    original='def total(items):\n    result = 0\n    for item in items:\n        if item > 0:\n            result += item * 2\n        else:\n            result -= item\n    result *= 2\n    return transform(result)\n'
    renamed=original.replace('total','sum_values').replace('items','values').replace('item','value').replace('result','answer')
    map_write(tmp_path,'a.py',original)
    map_write(tmp_path,'b.py',renamed)
    map_write(tmp_path,'c.py',renamed.replace('transform','different_operation'))
    inv=build_inventory(tmp_path,DEFAULT_IGNORE)
    assert len(inv.py['a.py'].bodies)==len(inv.py['b.py'].bodies)==len(inv.py['c.py'].bodies)==1
    assert inv.py['a.py'].bodies[0][1]==inv.py['b.py'].bodies[0][1]
    assert inv.py['a.py'].bodies[0][1]!=inv.py['c.py'].bodies[0][1]

def test_write_into_an_injected_object_is_a_foreign_state_write(tmp_path):
    from flowguard.map.discover import discover_inventory
    service = _INJECTED_SERVICE + '\n    def clear(self):\n        self.store.notes = {}\n'
    _injected_project(tmp_path, service=service, cli=_INJECTED_CLI)
    raw = discover_inventory(tmp_path, build_inventory(tmp_path, DEFAULT_IGNORE), write_cache=False)
    assert any((item['source'] == 'notes/service.py#NoteService.clear' and item['class'] == 'NoteStore' and (item['attr'] == 'notes') for item in raw['foreign_writes'])), raw['foreign_writes']

@pytest.mark.parametrize('guard', ['TYPE_CHECKING', 't.TYPE_CHECKING'])
def test_import_sites_skip_type_checking_and_sort_by_line(tmp_path, guard):
    map_write(tmp_path, 'a.py', 'from typing import TYPE_CHECKING\nif ' + guard + ':\n    from b import X\nelse:\n    from b import Y\n\ndef late():\n    pass\n    from b import Z\n    pass\n    from b import W\n')
    map_write(tmp_path, 'b.py', 'X = Y = Z = W = 1\n')
    info = build_inventory(tmp_path, DEFAULT_IGNORE).py['a.py']
    assert {name: line for name, line in info.import_lines.items() if name.startswith('b:')} == {'b:Y': 5, 'b:Z': 9, 'b:W': 11}
    assert info.imports >= {'b:Y', 'b:Z', 'b:W'} and 'b:X' not in info.imports
