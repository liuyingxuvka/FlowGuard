from pathlib import Path

from flowguard.structure.readers.cfamily import extract


def read(source, extension='cpp'):
    return extract(Path('.'), 'sample.' + extension, source.encode('utf-8'), 'sample', False)


def test_c_declarations_includes_calls_and_real_field_writes():
    f = read('#include "policy.h"\nstruct Item { int status; };\n'
             'int allow(int days) { return days <= LIMIT; }\n'
             'int run(struct Item *item) { item->status = 2; return allow(item->status); }\n', 'c')
    assert f['parse_error'] == ''
    assert {(n['qual'], n['kind']) for n in f['nodes']} == {('Item', 'class'), ('allow', 'function'), ('run', 'function')}
    assert f['dependencies'][0]['module'] == 'policy.h' and f['dependencies'][0]['relative']
    call = next(c for c in f['syntax_calls'] if c['text'] == 'allow')
    assert call['node'] == 'sample:run' and call['line'] == 4 and call['reason'] == ''
    write = next(a for a in f['assignments'] if a['target'] == 'item->status')
    assert (write['field'], write['value'], write['literal']) == ('status', 2, True)
    assert ('field', 'status', 4, 'run') in f['keys']


def test_cpp_macro_and_function_pointer_are_not_proved_direct_calls():
    f = read('#define APPLY(fn,x) fn(x)\nint known(int x) { return x; }\n'
             'int run(int (*callback)(int), int x) { return APPLY(known,x) + callback(x); }')
    calls = {c['text']: c for c in f['syntax_calls']}
    assert 'macro' in calls['APPLY']['reason']
    assert 'binding' in calls['callback']['reason']
    assert all(c['resolved'] is None for c in calls.values())


def test_cpp_namespace_overloads_and_methods_keep_distinct_nodes():
    f = read('namespace N { struct Calc { int run(int x) { return x; } '
             'double run(double x) { return x; } }; int twice(int x) { return x+x; } }')
    names = [n['qual'] for n in f['nodes']]
    assert len(names) == len(set(names))
    assert len([n for n in f['nodes'] if n['kind'] == 'method' and n['cls'] == 'N.Calc']) == 2
    assert 'N.twice' in names


def test_cpp_bom_crlf_unicode_and_rename_fingerprint():
    f = read('\ufeff// café\r\nint café(int x) { return x + 1; }\r\n')
    n = next(n for n in f['nodes'] if n['kind'] == 'function')
    assert f['parse_error'] == '' and (n['line'], n['column']) == (2, 1)
    renamed = read('int renamed(int x) { return x + 1; }')['nodes'][0]
    assert n['fp'] == renamed['fp']
    changed = read('int renamed(int x) { return x + 2; }')['nodes'][0]
    assert changed['fp'] != renamed['fp']


def test_cpp_parse_failure_and_dynamic_members_remain_visible():
    f = read('int run(Service *service) { return service->execute(); }')
    assert f['syntax_calls'][0]['text'] == 'service->execute'
    assert f['syntax_calls'][0]['reason'] and f['syntax_calls'][0]['resolved'] is None
    broken = read('int run( {')
    assert 'syntax error' in broken['parse_error']


def test_c_header_prototypes_and_cpp_conditional_bindings():
    f = read('int declared(int x);\nint (*callback)(int);\n', 'h')
    assert [n['qual'] for n in f['nodes']] == ['declared']
    assert f['nodes'][0]['raw']['declaration_only']
    f = read('#if FEATURE\nint optional(int x) {return x;}\n#endif\n'
             'int run() {return optional(2);}')
    assert next(n for n in f['nodes'] if n['qual'] == 'optional')['raw']['requires_build_context']
    assert 'conditional' in f['syntax_calls'][0]['reason']
    assert read('namespace N { int run() {return 1;} }', 'C')['parse_error'] == ''


def test_same_map_keeps_headers_calls_field_changes_and_overloads(tmp_path):
    from flowguard.structure import build
    (tmp_path / 'policy.h').write_text('#define LIMIT 3\n')
    source = tmp_path / 'main.cpp'
    source.write_text('#include "policy.h"\nstruct Item { int status; };\n'
                      'int allow(int x) { return x <= LIMIT; }\n'
                      'int run(Item *p) { p->status = 2; return allow(p->status); }\n')
    graph = build(tmp_path, store_path=tmp_path / 'map.sqlite', workers=1)
    try:
        call = next(c for c in graph.calls() if c['text'] == 'allow')
        assert call['resolved'] == 'cpp/main.cpp:allow'
        assert graph.con.execute("SELECT prov FROM edge WHERE kind='imports-include'").fetchone()[0] == 'resolved'
        old = graph.node('cpp/main.cpp:run')['fp']
        source.write_text(source.read_text().replace('status = 2', 'status = 3'))
        graph.refresh()
        assert graph.node('cpp/main.cpp:run')['fp'] != old
        writes = list(graph.assignments())
        assert any(a['field'] == 'status' and a['value'] == 3 for a in writes)
        source.write_text('int pick(int x){return x;} double pick(double x){return x;} '
                          'int run(){return pick(1);}')
        graph.refresh()
        call = next(c for c in graph.calls() if c['text'] == 'pick')
        assert call['resolved'] is None and call['reason']
        assert len([n for n in graph.functions().values() if n['qual'].startswith('pick')]) == 2
    finally:
        graph.close()
