"""Original-source decoding for a demonstrated C++ grammar ambiguity."""
from pathlib import Path
import hashlib

import pytest

from flowguard.structure import build
from flowguard.structure.readers.cfamily import extract


FIXTURE = Path(__file__).parents[1] / 'fixtures/structure/gtest-filepath.cc.txt'
SOURCE = '''struct Target {
 bool flag() const { return true; }
 const Target& other() const { return *this; }
 void run() {
  int count = 0;
  const Target& path(flag() ? *this : other());
 }
};
'''


def read(source):
    return extract(Path('.'), 'sample.cpp', source.encode('utf-8'), 'cpp/sample.cpp', False)


def test_unchanged_real_google_test_source_has_two_verified_initializers():
    source = FIXTURE.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(source)).encode() + b'\0' + source).hexdigest()
    assert blob == '902d8c7f64b7c44d7bdfc2d6fa9420f5b796eac5'
    facts = extract(FIXTURE.parent, 'gtest-filepath.cc', source, 'cpp/gtest-filepath.cc', False)
    assert facts['parse_error'] == ''
    assert len(facts['nodes']) == 19
    assert [(r['line'], r['end_line']) for r in facts['syntax_recoveries']] == [(270, 271), (273, 273)]
    calls = [c for c in facts['syntax_calls'] if c['line'] in (270, 271)]
    assert [(c['text'], c['line']) for c in calls] == [('IsRootDirectory', 270), ('RemoveTrailingPathSeparator', 271)]
    assert all(c['node'].endswith(':testing.internal.FilePath.DirectoryExists') for c in calls)
    writes = [a for a in facts['assignments'] if a['target'] == 'path']
    assert [a['line'] for a in writes] == [270, 273]
    assert all(a['value'] is None and not a['literal'] for a in writes)
    assert not any(n['qual'].rsplit('.', 1)[-1] == 'path' for n in facts['nodes'])


@pytest.mark.parametrize('initializer', ['flag() ? *this : other()', '*this', '(flag() ? *this : other())'])
def test_reference_initializers_use_the_original_expression_and_coordinates(initializer):
    source = SOURCE.replace('flag() ? *this : other()', initializer)
    facts = read('\ufeff' + source.replace('\n', '\r\n'))
    assert facts['parse_error'] == ''
    write = next(a for a in facts['assignments'] if a['target'] == 'path')
    assert (write['line'], write['column']) == (6, 17)
    assert write['end_column'] == source.splitlines()[5].rindex(')') + 2
    if 'flag()' in initializer:
        call = next(c for c in facts['syntax_calls'] if c['text'] == 'flag')
        line = source.splitlines()[5]
        assert (call['line'], call['column']) == (6, line.index('flag()') + 1)
        assert call['node'] == 'cpp/sample.cpp:Target.run'


def test_unicode_ranges_keep_character_columns_without_rewriting_source():
    source = SOURCE.replace('Target', 'Café').replace('path(', 'cheminé(')
    facts = read('\ufeff' + source.replace('\n', '\r\n'))
    assert facts['parse_error'] == ''
    line = source.splitlines()[5]
    write = next(a for a in facts['assignments'] if a['target'] == 'cheminé')
    call = next(c for c in facts['syntax_calls'] if c['text'] == 'flag')
    assert (write['line'], write['column']) == (6, line.index('cheminé') + 1)
    assert (call['line'], call['column']) == (6, line.index('flag()') + 1)
    assert call['node'] == 'cpp/sample.cpp:Café.run'


@pytest.mark.parametrize('bad', [
    'const Target& path(flag() ? *this : );',
    'const Target& path(flag() ? *this other());',
    'const Target& path(flag() ? *this : other();',
    'const Target& path(flag() ? *this : other())',
    'const Target& path(flag() ? *this : other()) extra;',
])
def test_missing_operands_punctuation_and_uncovered_tokens_remain_errors(bad):
    facts = read(SOURCE.replace('const Target& path(flag() ? *this : other());', bad))
    assert facts['parse_error']


def test_recovering_one_declaration_does_not_hide_another_error():
    facts = read(SOURCE.replace('int count = 0;', 'int count = 0; broken( ;'))
    assert facts['parse_error']


def test_unsupported_inner_expression_keeps_the_real_parse_boundary():
    # This pinned grammar also misreads an assignment/comma expression in its
    # own right. Reference-initializer decoding must not conceal that boundary.
    facts = read(SOURCE.replace('*this : other()', '(count = 2, *this) : other()'))
    assert facts['parse_error']


def test_real_function_declarations_are_not_reclassified_as_initializers():
    facts = read('struct Target {};\nint genuine(int value);\nconst Target& reference(const Target& other);\n')
    assert facts['parse_error'] == '' and not facts['syntax_recoveries']
    assert any(n['qual'] == 'genuine' and n['raw']['declaration_only'] for n in facts['nodes'])
    assert not any(a['target'] in {'genuine', 'reference'} for a in facts['assignments'])


def test_reference_return_prototype_with_default_condition_is_indexed():
    # Independent review found this real declaration missing without a parse
    # error. A functions-absence rule must be able to see the declaration.
    facts = read('struct T {};\nT left, right;\nbool flag = true;\n'
                 'const T& choose(const T& value = (flag ? left : right));\n'
                 'int plain(int value = 1);\n')
    assert not facts['parse_error'] and not facts['syntax_recoveries']
    choose = next(n for n in facts['nodes'] if n['qual'] == 'choose')
    assert choose['line'] == 4 and choose['raw']['declaration_only']
    assert any(n['qual'] == 'plain' for n in facts['nodes'])
    assert not any(a['target'] == 'choose' for a in facts['assignments'])


def test_reference_return_definitions_use_the_same_declarator_name_owner():
    facts = read('struct T { const T& self() const { return *this; } };\n'
                 'const T& identity(const T& value) { return value; }\n')
    assert not facts['parse_error']
    functions = {n['qual']: n for n in facts['nodes'] if n['kind'] in {'function','method'}}
    assert set(functions) == {'T.self', 'identity'}
    assert all(not n['raw']['declaration_only'] for n in functions.values())


@pytest.mark.parametrize('language,extension', [('c','c'), ('cpp','cpp')])
def test_pointer_returns_are_functions_but_pointer_variables_are_not(language, extension):
    source = b'typedef struct Item Item;\nItem* create(void);\nItem (*callback)(int);\n'
    facts = extract(Path('.'), 'sample.'+extension, source, language+'/sample.'+extension, False)
    assert not facts['parse_error']
    assert [n['qual'] for n in facts['nodes'] if n['kind'] == 'function'] == ['create']
    assert next(n for n in facts['nodes'] if n['qual'] == 'create')['raw']['declaration_only']


def test_declarator_binding_order_distinguishes_factory_from_callback_variables():
    facts = read('struct T {};\nT (plain)(int);\nT (*factory(int))(double);\n'
                 'T (*callback)(double);\nT (&reference_callback)(double);\n')
    assert not facts['parse_error']
    assert {n['qual'] for n in facts['nodes'] if n['kind']=='function'} == {'plain', 'factory'}
    assert all(n['raw']['declaration_only'] for n in facts['nodes'] if n['kind']=='function')


def test_prior_value_disambiguates_a_reference_initializer_from_a_function():
    facts = read('struct T {}; T object; T& alias(object);')
    assert not facts['parse_error']
    assert not any(n['qual'] == 'alias' for n in facts['nodes'])
    assert any(a['target'] == 'alias' and not a['literal'] for a in facts['assignments'])
    typed = read('struct T {}; T& choose(T);')
    assert not typed['parse_error']
    assert any(n['qual'] == 'choose' and n['raw']['declaration_only'] for n in typed['nodes'])


def test_unknown_declaration_binding_is_not_false_function_or_complete_absence(tmp_path):
    source = '#include "types.hpp"\nT& maybe(External);\n'
    facts = read(source)
    assert facts['parse_error'] == ''
    assert not any(n['qual'] == 'maybe' for n in facts['nodes'])
    assert facts['binding_unknowns'][0]['name'] == 'maybe'
    (tmp_path/'source.cpp').write_text(source)
    graph = build(tmp_path, store_path=tmp_path/'cache.sqlite', workers=1)
    try:
        graph.functions()
        coverage = graph.query_coverage()
        assert not coverage['complete']
        assert any('source declaration binding unknown' in issue['reason'] for issue in coverage['issues'])
        graph.reset_query_coverage()
        list(graph.imports(declarations=True))
        assert graph.query_coverage()['complete']
    finally:
        graph.close()


def test_common_map_keeps_macro_uncertainty_and_tracks_real_changes(tmp_path):
    source = '#define CHOOSE(x) (x)\n' + SOURCE.replace('flag() ? *this', 'CHOOSE(flag()) ? *this')
    source = source.replace('int count = 0;', 'int count = 0; Target& selected = *this;')
    path = tmp_path / 'sample.cpp'
    path.write_text(source)
    graph = build(tmp_path, store_path=tmp_path/'cache.sqlite', workers=1)
    try:
        marker = graph.capabilities()['languages']['cpp']['parser']['syntax_recovery']
        assert 'original ranges' in marker
        assert graph.query_coverage()['complete']
        macro = next(c for c in graph.calls() if c['text'] == 'CHOOSE')
        assert macro['resolved'] is None and 'macro' in macro['reason']
        original = graph.node('cpp/sample.cpp:Target.run')
        path.write_text(source.replace('void run()', 'void renamed()'))
        graph.refresh()
        assert graph.node(original['id']) is None
        renamed = graph.node('cpp/sample.cpp:Target.renamed')
        assert renamed['fp'] == original['fp']
        path.write_text(path.read_text().replace('*this : other()', '(selected = *this) : other()'))
        graph.refresh()
        current = graph.node(renamed['id'])
        assert current['fp'] != renamed['fp']
        write = next(a for a in graph.assignments(include_unknown=True) if a['target'] == 'selected' and a['line'] == 7)
        assert write['value'] is None and not write['literal']
        assert write['node'] == current['id']
        assert current['id'] in graph.impact(['sample.cpp'])['dirty']
    finally:
        graph.close()
