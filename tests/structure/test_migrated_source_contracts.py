"""Source/Git contracts retained when the old inventory/discovery products retire.

These use the public generated map, not a compatibility inventory or discovery cache.
"""
from contextlib import closing
import os
from pathlib import Path
import shlex
import shutil
import sys

import pytest

from _pure_helpers import (_INJECTED_CLI, _INJECTED_SERVICE, _INJECTED_STORE,
                           git, write)
from flowguard.map.common import MapError, content_digest, git_common_directory
from flowguard.map.inventory import list_files, parse_python, resolve_module
from flowguard.structure import build


def ident(graph, file, qual):
    matches = [node['id'] for node in graph.nodes(file=file) if node['qual'] == qual]
    assert len(matches) == 1, (file, qual, matches)
    return matches[0]


def resolved_calls(graph, file, qual):
    return {(node['file'], node['qual'])
            for edge in graph.edges(ident(graph, file, qual), kind='calls')
            if edge['prov'] == 'resolved' and (node := graph.node(edge['dst']))}


def imports_of(graph, file):
    return {node['file'] for edge in graph.imports()
            if edge['file'] == file and edge['kind'] in {'imports', 'imports-optional', 'imports-lazy', 'imports-dynamic'}
            and edge['prov'] == 'resolved' and (node := graph.node(edge['dst']))}


def test_retained_module_resolution_precedence():
    files = {'scripts/runner.py', 'scripts/helper.py', 'library/helper.py',
             'other/helper.py', 'library/pkg/__init__.py'}
    assert resolve_module('helper', 'scripts/runner.py', {'helper': 'package/helper.py'}, files,
                          ('library',)) == 'package/helper.py'
    assert resolve_module('helper', 'scripts/runner.py', {}, files,
                          ('library',)) == 'scripts/helper.py'
    assert resolve_module('helper', 'scripts/runner.py', {}, files | {'scripts/__init__.py'},
                          ('library', 'other')) == 'library/helper.py'
    assert resolve_module('pkg', 'runner.py', {}, files, ('library',)) == 'library/pkg/__init__.py'


@pytest.mark.parametrize('guard', ['TYPE_CHECKING', 't.TYPE_CHECKING'])
def test_retained_import_sites_skip_type_checking_and_keep_else_and_local_lines(tmp_path, guard):
    source = ('from typing import TYPE_CHECKING\nif ' + guard + ':\n    from b import X\n'
              'else:\n    from b import Y\n\ndef late():\n    pass\n    from b import Z\n'
              '    pass\n    from b import W\n')
    write(tmp_path, 'a.py', source)
    info = parse_python(tmp_path, 'a.py', 'a')
    assert {name: line for name, line in info.import_lines.items() if name.startswith('b:')} == {
        'b:Y': 5, 'b:Z': 9, 'b:W': 11}
    assert info.imports >= {'b:Y', 'b:Z', 'b:W'} and 'b:X' not in info.imports


def test_retained_python_runtime_and_parenthesized_imports(repo):
    repo.write({'shop/__init__.py': '', 'shop/api.py': 'def handle(): return 0\n',
                'shop/storage.py': 'def save(x): return x\n',
                'shop/orders.py': 'from typing import TYPE_CHECKING\nfrom shop import storage\n'
                                  'if TYPE_CHECKING:\n    from shop.api import handle\n'
                                  'def place_order(x): return storage.save(x)\n',
                'consumer.py': 'from shop.orders import (\n    place_order,\n)\n'
                               'def call(x): return place_order(x)\n'})
    with closing(repo.build()) as graph:
        assert 'shop/api.py' not in imports_of(graph, 'shop/orders.py')
        assert any(edge['file'] == 'shop/orders.py' and edge['kind'] == 'imports-typing'
                   and graph.node(edge['dst'])['file'] == 'shop/api.py' for edge in graph.imports())
        assert 'shop/storage.py' in imports_of(graph, 'shop/orders.py')
        assert 'shop/orders.py' in imports_of(graph, 'consumer.py')
        assert ('shop/orders.py', 'place_order') in resolved_calls(graph, 'consumer.py', 'call')


def test_retained_same_size_same_mtime_source_change_is_seen(repo):
    repo.write({'shop/storage.py': 'def save(x):\n    return x\n'})
    with closing(repo.build()) as graph:
        assert graph.node(ident(graph, 'shop/storage.py', 'save'))
    path = repo.path / 'shop/storage.py'
    before = path.stat()
    path.write_text('def keep(x):\n    return x\n', encoding='utf-8')
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size
    with closing(repo.build()) as graph:
        assert any(n['qual'] == 'keep' for n in graph.nodes(file='shop/storage.py'))
        assert not any(n['qual'] == 'save' for n in graph.nodes(file='shop/storage.py'))
        assert graph.stats['parsed'] == 1


def test_retained_non_ascii_file_names_and_function_fingerprints(repo):
    repo.write({'shop/工具.py': 'def 帮助():\n    return 1\n'})
    path = repo.path / 'shop/工具.py'
    before = content_digest(path)
    with closing(repo.build()) as graph:
        fingerprint = graph.node(ident(graph, 'shop/工具.py', '帮助'))['fp']
    path.write_text('def 帮助():\n    return 2\n', encoding='utf-8')
    assert content_digest(path) != before
    with closing(repo.build()) as graph:
        assert graph.node(ident(graph, 'shop/工具.py', '帮助'))['fp'] != fingerprint


def test_retained_nested_function_call_is_resolved(repo):
    repo.write({'runner.py': 'def outer():\n    def _private(): return 1\n'
                             '    def inner(): return _private()\n    return inner()\n'})
    with closing(repo.build()) as graph:
        assert ('runner.py', 'outer._private') in resolved_calls(graph, 'runner.py', 'outer.inner')


def test_retained_relative_import_in_enclosing_function_is_resolved(repo):
    repo.write({'pkg/__init__.py': '',
                'pkg/runner.py': 'def outer():\n    from .helper import _private\n'
                                 '    def inner(): return _private()\n    return inner()\n',
                'pkg/helper.py': 'def _private(): return 1\n'})
    with closing(repo.build()) as graph:
        assert ('pkg/helper.py', '_private') in resolved_calls(graph, 'pkg/runner.py', 'outer.inner')
        assert 'pkg/helper.py' in imports_of(graph, 'pkg/runner.py')


def test_retained_script_import_uses_its_sibling_but_a_package_does_not(repo):
    repo.write({'scripts/runner.py': 'from helper import _private\ndef run(): return _private()\n',
                'scripts/helper.py': 'def _private(): return 1\n',
                'pkg/__init__.py': '', 'pkg/a.py': 'import helper\n',
                'pkg/helper.py': 'value = 2\n'})
    with closing(repo.build()) as graph:
        assert ('scripts/helper.py', '_private') in resolved_calls(graph, 'scripts/runner.py', 'run')
        assert 'scripts/helper.py' in imports_of(graph, 'scripts/runner.py')
        assert 'pkg/helper.py' not in imports_of(graph, 'pkg/a.py')
        assert all(edge['kind'] == 'imports-unrooted' and edge['prov'] == 'guessed'
                   for edge in graph.imports() if edge['file'] == 'pkg/a.py'
                   and graph.node(edge['dst'])['file'] == 'pkg/helper.py')


def test_retained_explicit_import_root_is_required(tmp_path):
    root = tmp_path / 'repo'
    write(root, 'scripts/runner.py', 'from helper import _private\ndef run(): return _private()\n')
    write(root, 'library/helper.py', 'def _private(): return 1\n')
    with closing(build(root, tmp_path / 'with-root.sqlite', roots=[root / 'library'])) as graph:
        assert ('library/helper.py', '_private') in resolved_calls(graph, 'scripts/runner.py', 'run')
        assert 'library/helper.py' in imports_of(graph, 'scripts/runner.py')
    with closing(build(root, tmp_path / 'without-root.sqlite')) as graph:
        assert ('library/helper.py', '_private') not in resolved_calls(graph, 'scripts/runner.py', 'run')


def test_retained_constructor_attribute_calls_are_read_without_importing_project(repo):
    marker = repo.path / 'project-code-ran.txt'
    repo.write({'fg232_shelf/__init__.py': '',
                'fg232_shelf/members.py': 'class Members:\n    def may_borrow(self): return True\n    def shared(self): return True\n',
                'fg232_shelf/catalog.py': 'class Catalog:\n    def take(self): return True\n    def flush(self): return True\n    def shared(self): return True\n',
                'fg232_shelf/decoy.py': 'class Decoy:\n    def may_borrow(self): return False\n    def take(self): return False\n    def shared(self): return False\n',
                'fg232_shelf/outside.py': 'class Outside:\n    def flush(self): return False\n',
                'fg232_shelf/loans.py': f'from pathlib import Path\nPath({str(marker)!r}).write_text("imported")\n'
                    'from fg232_shelf.members import Members\nimport fg232_shelf.catalog as stock\n'
                    'class LoanService:\n    def __init__(self, catalog=None, dependency=None):\n'
                    '        self.members = Members()\n        self.catalog = catalog or stock.Catalog()\n'
                    '        self.unknown = dependency\n    def borrow(self):\n'
                    '        self.members.may_borrow()\n        return self.catalog.take()\n'
                    '    def flush(self): return self.unknown.flush()\n'
                    '    def ambiguous(self): return self.unknown.shared()\n'})
    with closing(repo.build()) as graph:
        assert resolved_calls(graph, 'fg232_shelf/loans.py', 'LoanService.borrow') == {
            ('fg232_shelf/members.py', 'Members.may_borrow'),
            ('fg232_shelf/catalog.py', 'Catalog.take')}
        assert graph.edges(ident(graph, 'fg232_shelf/loans.py', 'LoanService.flush'), kind='calls') == []
        assert graph.edges(ident(graph, 'fg232_shelf/loans.py', 'LoanService.ambiguous'), kind='calls') == []
    assert not marker.exists()
    assert not any(name == 'fg232_shelf' or name.startswith('fg232_shelf.') for name in sys.modules)


@pytest.mark.parametrize('variant', ['call-site', 'annotation'])
def test_retained_injected_collaborator_resolves_to_its_real_class(tmp_path, variant):
    root = tmp_path / variant
    write(root, 'notes/__init__.py', '')
    write(root, 'notes/store.py', _INJECTED_STORE)
    service = (_INJECTED_SERVICE if variant == 'call-site' else
               'from notes.store import NoteStore\n\n\n' + _INJECTED_SERVICE.replace(
                   'def __init__(self, store):', 'def __init__(self, store: NoteStore):'))
    write(root, 'notes/service.py', service)
    if variant == 'call-site':
        write(root, 'notes/cli.py', _INJECTED_CLI)
    with closing(build(root, tmp_path / (variant + '.sqlite'))) as graph:
        assert ('notes/store.py', 'NoteStore.save') in resolved_calls(graph, 'notes/service.py', 'NoteService.add')
    assert not any(name == 'notes' or name.startswith('notes.') for name in sys.modules)


@pytest.mark.skipif(os.name == 'nt', reason='a POSIX shell stands in for an actually failing git')
def test_retained_git_listing_failure_is_not_a_folder_walk(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    root.mkdir()
    git(root, 'init', '-q')
    write(root, '.gitignore', 'build/\n')
    write(root, 'a.py', 'x = 1\n')
    write(root, 'build/generated.py', 'y = 2\n')
    assert list_files(root) == ['.gitignore', 'a.py']
    real = shutil.which('git')
    directory = tmp_path / 'git-bin'
    directory.mkdir()
    script = directory / 'git'
    script.write_text('#!/bin/sh\nfor argument in "$@"; do\n'
                      '  if [ "$argument" = "ls-files" ]; then\n'
                      '    echo "fatal: simulated ls-files failure" >&2\n    exit 128\n  fi\ndone\n'
                      f'exec {shlex.quote(real)} "$@"\n', encoding='utf-8')
    script.chmod(0o755)
    monkeypatch.setenv('PATH', f'{directory}{os.pathsep}{os.environ["PATH"]}')
    with pytest.raises(MapError, match='simulated ls-files failure'):
        list_files(root)


def test_retained_folder_in_git_metadata_has_no_work_tree(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    git(root, 'init', '-q')
    cache = root / '.git/flowguard/cache/snapshot'
    write(cache, 'src/program.py', 'x = 1\n')
    assert git_common_directory(root) == (root / '.git').resolve()
    assert git_common_directory(cache) is None
    assert list_files(cache) == ['src/program.py']


def test_retained_two_injection_classes_are_not_silently_resolved_to_one(tmp_path):
    write(tmp_path, 'notes/__init__.py', '')
    write(tmp_path, 'notes/store.py', _INJECTED_STORE)
    write(tmp_path, 'notes/other.py', 'class OtherStore:\n    def save(self, note_id, text): pass\n')
    write(tmp_path, 'notes/service.py', _INJECTED_SERVICE)
    write(tmp_path, 'notes/cli.py', _INJECTED_CLI + '\nfrom notes.other import OtherStore\n'
          'def another():\n    service = NoteService(OtherStore())\n    service.add("b", "other")\n')
    with closing(build(tmp_path, tmp_path / 'map.sqlite')) as graph:
        actual = resolved_calls(graph, 'notes/service.py', 'NoteService.add')
        assert not actual & {('notes/store.py', 'NoteStore.save'), ('notes/other.py', 'OtherStore.save')}


def test_retained_an_unknown_injection_argument_is_not_a_resolved_class(tmp_path):
    write(tmp_path, 'notes/__init__.py', '')
    write(tmp_path, 'notes/store.py', _INJECTED_STORE)
    write(tmp_path, 'notes/service.py', _INJECTED_SERVICE)
    write(tmp_path, 'notes/cli.py', 'from notes.service import NoteService\n'
          'def main(factory):\n    service = NoteService(factory())\n    service.add("a", "text")\n')
    with closing(build(tmp_path, tmp_path / 'map.sqlite')) as graph:
        assert ('notes/store.py', 'NoteStore.save') not in resolved_calls(
            graph, 'notes/service.py', 'NoteService.add')


def test_retained_changing_the_constructor_call_relinks_the_injected_owner(tmp_path):
    write(tmp_path, 'notes/__init__.py', '')
    write(tmp_path, 'notes/store.py', _INJECTED_STORE)
    write(tmp_path, 'notes/other.py', 'class OtherStore:\n    def save(self, note_id, text): pass\n')
    write(tmp_path, 'notes/service.py', _INJECTED_SERVICE)
    write(tmp_path, 'notes/cli.py', _INJECTED_CLI)
    cache = tmp_path / 'map.sqlite'
    with closing(build(tmp_path, cache)) as graph:
        assert ('notes/store.py', 'NoteStore.save') in resolved_calls(
            graph, 'notes/service.py', 'NoteService.add')
    write(tmp_path, 'notes/cli.py', 'from notes.service import NoteService\nfrom notes.other import OtherStore\n'
          'def main():\n    service = NoteService(OtherStore())\n    service.add("a", "text")\n')
    with closing(build(tmp_path, cache)) as graph:
        actual = resolved_calls(graph, 'notes/service.py', 'NoteService.add')
        assert ('notes/store.py', 'NoteStore.save') not in actual
        assert ('notes/other.py', 'OtherStore.save') in actual


@pytest.mark.parametrize('expression', ['pkg.B', "getattr(pkg, 'B')", 'hasattr(pkg, name)', 'pkg.__all__'])
def test_retained_lazy_facade_reflection_keeps_its_real_dependencies(repo, expression):
    repo.write({'pkg/__init__.py': "_TABLE = {'pkg.a': ('A',), 'pkg.b': ('B',)}\n"
                                  'def __getattr__(name):\n    pass\n',
                'pkg/a.py': 'A = 1\n', 'pkg/b.py': 'B = 2\n',
                'tests/test_reflect.py': f"import pkg\nname = 'B'\nvalue = {expression}\n"})
    with closing(repo.build()) as graph:
        assert 'pkg/b.py' in imports_of(graph, 'tests/test_reflect.py')
        if expression in {'pkg.B', "getattr(pkg, 'B')"}:
            assert 'pkg/a.py' not in imports_of(graph, 'tests/test_reflect.py')


def test_retained_lazy_facade_does_not_turn_one_export_into_every_sibling(repo):
    repo.write({'pkg/__init__.py': 'import importlib\n'
                "_TABLE = {'pkg.a': ('A',), 'pkg.b': ('B',)}\n"
                'def __getattr__(name):\n    return importlib.import_module("pkg.a")\n',
                'pkg/a.py': 'A = 1\n', 'pkg/b.py': 'B = 2\n', 'consumer.py': 'from pkg import A\n'})
    with closing(repo.build()) as graph:
        assert 'pkg/a.py' in imports_of(graph, 'consumer.py')
        assert 'pkg/b.py' not in imports_of(graph, 'consumer.py')


def test_retained_literal_dynamic_import_is_a_source_dependency(repo):
    repo.write({'a.py': 'TARGET = __import__("pkg")\n', 'pkg.py': 'VALUE = 1\n'})
    with closing(repo.build()) as graph:
        assert 'pkg.py' in imports_of(graph, 'a.py')


def test_retained_fingerprints_separate_class_bindings_and_nested_function_changes(repo):
    source = ('VALUE=1\nclass C:\n    field=1\n    def method(self):\n'
              '        def inner(): return 1\n        return inner()\n')
    repo.write({'a.py': source})
    with closing(repo.build()) as graph:
        initial = {node['qual']: node['fp'] for node in graph.nodes(file='a.py')}
    repo.write({'a.py': source.replace('inner(): return 1', 'inner(): return 2')})
    with closing(repo.build()) as graph:
        nested = {node['qual']: node['fp'] for node in graph.nodes(file='a.py')}
        assert initial['C.method.inner'] != nested['C.method.inner']
        assert initial['C'] == nested['C']
    repo.write({'a.py': source.replace('field=1', 'field=2')})
    with closing(repo.build()) as graph:
        assert initial['C'] != graph.node(ident(graph, 'a.py', 'C'))['fp']
    repo.write({'a.py': source.replace('VALUE=1', 'VALUE=2')})
    with closing(repo.build()) as graph:
        assert initial[''] != graph.node(ident(graph, 'a.py', ''))['fp']


def test_retained_static_command_functions_preserve_names_and_lines(repo):
    repo.write({'commands.py': 'import click\n' + '\n'.join(
        f'@click.command()\ndef command_{i}(): pass\n' for i in range(5))})
    with closing(repo.build()) as graph:
        functions = graph.functions()
        actual = [node for node in functions.values() if node['file'] == 'commands.py']
        assert {node['qual'] for node in actual} == {f'command_{i}' for i in range(5)}
        assert all(isinstance(node['line'], int) and node['line'] > 0 for node in actual)


def test_literal_dynamic_import_aliases_are_kept_separate_from_unknown_names(tmp_path):
    source = ('import importlib as il\nfrom importlib import import_module as load\n'
              'one = __import__("alpha")\ntwo = il.import_module("beta")\n'
              'three = load("gamma")\nunknown = load(name)\n'
              'def local():\n    import importlib as inner\n    return inner.import_module("delta")\n'
              'def shadow(load):\n    return load("decoy")\n'
              'outside = inner.import_module("not_a_binding_here")\n')
    write(tmp_path, 'a.py', source)
    info = parse_python(tmp_path, 'a.py', 'a')
    assert info.literal_dynamic_imports == {'alpha': [3], 'beta': [4], 'gamma': [5], 'delta': [9]}
    assert info.unknown_dynamic_imports == [{'line': 6, 'call': 'importlib.import_module',
                                            'reason': 'module name is not an absolute string literal'}]


def test_import_reads_select_literal_members_and_exclude_typing_and_shadowed_names(tmp_path):
    source = ('import pkg as alias\nfirst = alias.B\nsecond = getattr(alias, "B")\n'
              'third = hasattr(alias, name)\nfourth = alias.__all__\n'
              'def shadow(alias):\n    return alias.A\n'
              'if TYPE_CHECKING:\n    extra = alias.A\n')
    write(tmp_path, 'a.py', source)
    info = parse_python(tmp_path, 'a.py', 'a')
    assert info.import_reads == {'pkg:B': [2, 3], 'pkg:*': [4, 5]}


def test_nonliteral_dynamic_import_is_not_guessed_from_an_expression(repo):
    repo.write({'a.py': 'from importlib import import_module as load\n'
                       'known = load("alpha")\nunknown = load("de" + "coy")\n',
                'alpha.py': 'VALUE = 1\n', 'decoy.py': 'VALUE = 2\n'})
    info = parse_python(repo.path, 'a.py', 'a')
    assert info.literal_dynamic_imports == {'alpha': [2]}
    assert info.unknown_dynamic_imports == [{'line': 3, 'call': 'importlib.import_module',
                                            'reason': 'module name is not an absolute string literal'}]
    with closing(repo.build()) as graph:
        assert 'alpha.py' in imports_of(graph, 'a.py')
        assert 'decoy.py' not in imports_of(graph, 'a.py')
        unknown = [edge for edge in graph.imports() if edge['file'] == 'a.py' and edge['prov'] == 'unknown']
        assert len(unknown) == 1
        assert unknown[0]['kind'] == 'imports-dynamic' and unknown[0]['line'] == 3
        assert graph.node(unknown[0]['dst']) is None


def test_literal_dynamic_keyword_name_and_relative_level_are_distinct(tmp_path):
    write(tmp_path, 'a.py', 'from importlib import import_module as load\n'
          'absolute = load(name="alpha")\nrelative = __import__("alpha", level=1)\n')
    info = parse_python(tmp_path, 'a.py', 'a')
    assert info.literal_dynamic_imports == {'alpha': [2]}
    assert info.unknown_dynamic_imports == [{'line': 3, 'call': '__import__',
                                           'reason': 'relative import level needs an explicit package context'}]


def test_retained_source_effects_and_http_keys_do_not_execute_or_trust_string_words(repo):
    repo.write({'save.py': 'def save(text):\n    with open("out.txt", "w") as handle:\n        handle.write(text)\n',
                'words.py': 'HELP = "run subprocess or open a socket"\n'
                            'def describe(): return "subprocess.run and requests.post"\n',
                'app.py': 'class App:\n    def route(self, path, methods=None):\n        pass\n'
                          'app = App()\n@app.route("/notes", methods=["POST"])\n'
                          'def create_note(): return 1\n'})
    with closing(repo.build()) as graph:
        assert graph.node(ident(graph, 'save.py', 'save'))['effects'] == 'fs_write'
        assert graph.node(ident(graph, 'words.py', 'describe'))['effects'] == ''
        assert {row['value'] for row in graph.keys(kind='route')} == {'POST /notes'}
    assert not (repo.path / 'out.txt').exists()


def test_call_argument_and_direct_or_facts_support_default_read_policies(repo):
    repo.write({'reader.py': 'def read(row, obj):\n'
                            '    a = row.get("a", 0)\n'
                            '    b = row.get("b") or []\n'
                            '    c = getattr(obj, "name", None)\n'
                            '    d = outer(row.get("d")) or []\n'
                            '    e = row.get("e", default=1)\n'})
    with closing(repo.build()) as graph:
        calls = list(graph.calls())
        assert [(r['line'], r['text'], r['positional_arg_count'], r['keyword_count'], r['boolop_or_nonfinal'])
                for r in calls] == [(2, 'row.get', 2, 0, False), (3, 'row.get', 1, 0, True),
                                    (4, 'getattr', 3, 0, False), (5, 'outer', 1, 0, True),
                                    (5, 'row.get', 1, 0, False), (6, 'row.get', 1, 1, False)]
