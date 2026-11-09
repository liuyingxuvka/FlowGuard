"""An empty fixed query cannot certify sources its reader does not implement."""
from contextlib import closing
import pytest
from flowguard.map.common import MapError
from flowguard.structure import build


def setup(tmp_path, files):
    for name, source in files.items():
        (tmp_path/name).write_text(source,encoding='utf-8')
    return build(tmp_path,tmp_path/'map.sqlite',workers=1)


def test_foreign_try_catch_is_unavailable_not_a_proven_empty_handler_list(tmp_path):
    # C# catch clauses are still outside the reader (TypeScript's are read since round 20).
    with closing(setup(tmp_path,{'Code.cs':'class C { int Read(){ try { Work(); } catch (System.Exception error) { return 0; } return 1; } }\n'})) as graph:
        assert graph.handlers()==[]
        coverage=graph.query_coverage()
        assert not coverage['complete']
        assert coverage['issues'][0]['query']=='handlers'
        assert coverage['issues'][0]['files']==['Code.cs']
        assert graph.capabilities()['languages']['csharp']['queries']['handlers'] is False


def test_typescript_catch_is_a_read_handler_with_complete_coverage(tmp_path):
    with closing(setup(tmp_path,{'code.ts':'function read(){try { work(); } catch(error) { return 0; }}\n'})) as graph:
        rows=graph.handlers()
        assert [(row['kind'],row['type'],row['non_raising']) for row in rows]==[('catch','any',True)]
        assert graph.query_coverage()['complete']
        assert graph.capabilities()['languages']['typescript']['queries']['handlers'] is True


def test_explicit_python_scope_does_not_block_on_unrelated_foreign_reader(tmp_path):
    with closing(setup(tmp_path,{
        'code.ts':'function read(){try { work(); } catch(error) { return 0; }}\n',
        'code.py':'def read():\n    try: work()\n    except ValueError: return 0\n',
    })) as graph:
        assert len(graph.handlers(language='python'))==1
        assert graph.query_coverage()==dict(queried=['handlers'],complete=True,issues=[])


def test_call_queries_and_include_reads_record_their_real_coverage(tmp_path):
    with closing(setup(tmp_path,{'code.ts':'function run(row:any){return row.active;}\n'})) as graph:
        graph.calls()
        assert graph.query_coverage()['complete']
        graph.calls(include_reads=True)
        coverage=graph.query_coverage()
        assert coverage['queried']==['calls','symbol_reads']
        assert not coverage['complete']
        assert coverage['issues'][0]['query']=='symbol_reads'


def test_functions_and_keys_do_not_erase_failed_or_unsupported_sources(tmp_path):
    with closing(setup(tmp_path,{'bad.ts':'function broken( {\n','outside.rs':'fn run() {}\n'})) as graph:
        graph.functions()
        graph.keys()
        coverage=graph.query_coverage()
        assert not coverage['complete']
        assert set(coverage['queried'])=={'keys','nodes'}
        assert any('parse failed' in row['reason'] and row['files']==['bad.ts'] for row in coverage['issues'])
        assert any(row['language']=='unsupported' and row['files']==['outside.rs'] for row in coverage['issues'])


def test_file_scope_tracks_unsupported_source_without_polluting_other_predicates(tmp_path):
    with closing(setup(tmp_path,{'outside.rs':'fn run() {}\n','code.py':'def run(): return 1\n'})) as graph:
        assert graph.nodes(file='outside.rs')==[]
        assert graph.query_coverage()['issues'][0]['files']==['outside.rs']
        graph.reset_query_coverage()
        graph.functions(language='python')
        assert graph.query_coverage()==dict(queried=['nodes'],complete=True,issues=[])


def test_unknown_language_filter_cannot_certify_an_empty_result(tmp_path):
    with closing(setup(tmp_path,{'Outside.java':'class Outside {}\n'})) as graph:
        with pytest.raises(MapError,match='no source reader for language java'):
            graph.functions(language='java')


def test_python_function_filter_keeps_missing_imports_visible_elsewhere(tmp_path):
    (tmp_path / 'pkg').mkdir()
    (tmp_path / 'pkg/__init__.py').write_text('')
    with closing(setup(tmp_path, {
        'main.py': 'from pkg import absent\ndef decide(value): return value > 0\n',
        'other.ts': 'export function foreign(value:number){return value > 0;}\n',
    })) as graph:
        missing = graph.nodes(kind='missing')
        assert len(missing) == 1 and missing[0]['file'] is None
        actual = graph.functions(language='python')
        assert {row['qual'] for row in actual.values()} == {'decide'}
        assert all(row['file'] == 'main.py' for row in actual.values())
        assert graph.nodes(kind='missing') == missing
        assert any(edge['dst'] == missing[0]['id'] for edge in graph.imports(language='python'))
