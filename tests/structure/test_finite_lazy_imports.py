"""Source-closed scalar facade lookups, with actual WorldGuard source and refusals."""
from contextlib import closing
from pathlib import Path

import pytest
from flowguard.map.inventory import parse_python

ACTUAL = Path(__file__).with_name('fixtures') / 'worldguard_lazy_init.py'
BASE = '''from importlib import import_module as im
EXPORTS = {'Thing': 'pkg.owner', 'Other': 'pkg.other'}
def __getattr__(name):
    module_name = EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    return im(module_name)
'''


def info(tmp_path, source):
    return parse_python(tmp_path, 'pkg/__init__.py', 'pkg', data=source.encode())


def test_actual_worldguard_literal_exports_bound_the_import(tmp_path):
    parsed = info(tmp_path, ACTUAL.read_text())
    assert len(parsed.lazy_exports) == 15
    assert set(parsed.literal_dynamic_imports) == {
        'worldguard.contracts', 'worldguard.kernel', 'worldguard.mesh',
        'worldguard.qualification', 'worldguard.reports', 'worldguard.status'}
    assert parsed.unknown_dynamic_imports == []


@pytest.mark.parametrize('source', [BASE, BASE.replace('.get(name)', '.get(name, None)')])
def test_single_scalar_lookup_with_a_raising_none_guard_is_finite(tmp_path, source):
    parsed = info(tmp_path, source)
    assert set(parsed.literal_dynamic_imports) == {'pkg.owner', 'pkg.other'}
    assert parsed.unknown_dynamic_imports == []


@pytest.mark.parametrize('source', [
    BASE.replace("'pkg.other'", 'runtime_value'),
    BASE.replace("'pkg.other'", "('pkg.other', 'Other')"),
    BASE.replace("'pkg.other'", "'.relative'"),
    BASE.replace('def __getattr__', "EXPORTS['Thing'] = runtime_value\ndef __getattr__"),
    BASE.replace('def __getattr__', 'EXPORTS.update(runtime_table())\ndef __getattr__'),
    BASE.replace('def __getattr__', "del EXPORTS['Thing']\ndef __getattr__"),
    BASE.replace('def __getattr__', 'EXPORTS = runtime_table()\ndef __getattr__'),
    BASE.replace('def __getattr__', 'escape = EXPORTS\ndef __getattr__'),
    BASE.replace('def __getattr__', 'getter = EXPORTS.get\ndef __getattr__'),
    BASE + '\ndef expose():\n    return EXPORTS\n',
    BASE.replace('def __getattr__(name):', 'def __getattr__(name, EXPORTS):'),
    BASE.replace('def __getattr__(name):', 'def __getattr__(name, module_name):'),
    BASE.replace('    return im', '    module_name = runtime_value\n    return im'),
    BASE.replace('    return im', '    from external import module_name\n    return im'),
    BASE.replace('    return im', '    if flag:\n        module_name = runtime_value\n    return im'),
    BASE.replace('    return im', '    def rebind():\n        nonlocal module_name\n        module_name = runtime_value\n    return im'),
    BASE.replace('    if module_name is None:\n        raise AttributeError(name)\n', ''),
    BASE.replace('raise AttributeError(name)', 'pass'),
    BASE.replace('.get(name)', '.get(name, runtime_value)'),
    BASE.replace('def __getattr__', 'namespace = globals()\ndef __getattr__'),
    BASE.replace('def __getattr__', "globals()['EXPORTS'] = runtime_table()\ndef __getattr__"),
    BASE.replace('def __getattr__', "setattr(module, 'EXPORTS', runtime_table())\ndef __getattr__"),
    BASE.replace('def __getattr__', "exec(code)\ndef __getattr__"),
    BASE.replace('def __getattr__', 'from builtins import exec as execute\nexecute("EXPORTS[\'Thing\'] = \'pkg.evil\'")\ndef __getattr__'),
    BASE.replace('def __getattr__', "import builtins\nnamespace = builtins.globals()\nnamespace['EXPORTS']['Thing'] = 'pkg.evil'\ndef __getattr__"),
    BASE.replace('def __getattr__', "from builtins import globals as namespace\nnamespace()['EXPORTS']['Thing'] = 'pkg.evil'\ndef __getattr__"),
    BASE.replace('def __getattr__', "import sys\nsys.modules[__name__].EXPORTS['Thing'] = 'pkg.evil'\ndef __getattr__"),
    BASE.replace('def __getattr__', "from ownmodule import EXPORTS as alias\nalias['Thing'] = 'pkg.evil'\ndef __getattr__"),
    BASE.replace('def __getattr__', "alias = getattr(module, 'EXPORTS')\nalias['Thing'] = 'pkg.evil'\ndef __getattr__"),
    BASE.replace('def __getattr__(name):', 'def __getattr__(name):\n    global module_name'),
    BASE.replace('def __getattr__', "namespace = globals\nnamespace()['EXPORTS']['Thing'] = 'pkg.evil'\ndef __getattr__"),
    BASE.replace('def __getattr__', "setter = setattr\nsetter(module, 'EXPORTS', runtime_table())\ndef __getattr__"),
])
def test_mutable_escaped_rebound_or_unbounded_sources_remain_unknown(tmp_path, source):
    parsed = info(tmp_path, source)
    assert parsed.literal_dynamic_imports == {}
    assert parsed.unknown_dynamic_imports


def test_export_cache_cannot_replace_table_or_importer(tmp_path):
    source = ACTUAL.read_text().replace("'GuardContract': 'worldguard.contracts'", "'_import_module': 'worldguard.contracts'")
    parsed = info(tmp_path, source)
    assert parsed.literal_dynamic_imports == {}
    assert parsed.unknown_dynamic_imports


def test_finite_source_values_become_real_map_dependencies(repo):
    repo.write({'pkg/__init__.py': BASE, 'pkg/owner.py': 'Thing = 1\n', 'pkg/other.py': 'Other = 2\n'})
    with closing(repo.build()) as graph:
        edges = [edge for edge in graph.imports() if edge['file'] == 'pkg/__init__.py' and edge['kind'] == 'imports-dynamic']
        assert {graph.node(edge['dst'])['file'] for edge in edges} == {'pkg/owner.py', 'pkg/other.py'}
        assert all(edge['prov'] == 'resolved' for edge in edges)
    # Changing the table to a runtime update invalidates the existing warm map.
    repo.write({'pkg/__init__.py': BASE.replace('def __getattr__', 'EXPORTS.update(runtime_table())\ndef __getattr__')})
    with closing(repo.build()) as graph:
        edges = [edge for edge in graph.imports() if edge['file'] == 'pkg/__init__.py' and edge['kind'] == 'imports-dynamic']
        assert len(edges) == 1 and edges[0]['prov'] == 'unknown'


@pytest.mark.parametrize('change', [
    lambda source: source.replace('set(globals())', 'globals()'),
    lambda source: source + '\nset = runtime_callable\n',
    lambda source: source.replace('def __dir__():', 'def __dir__():\n    from external import set'),
    lambda source: source.replace('def __dir__():', 'def __dir__(globals):'),
])
def test_namespace_key_enumeration_must_not_escape_or_be_shadowed(tmp_path, change):
    parsed = info(tmp_path, change(ACTUAL.read_text()))
    assert parsed.literal_dynamic_imports == {}
    assert parsed.unknown_dynamic_imports
