"""The first language readers share actual stored/queryable facts, not just suffixes."""
from contextlib import closing

from flowguard.structure import build


def test_one_map_keeps_seven_languages_and_same_names_separate(tmp_path):
    files={
        'same.py':'def same(n): return n+1\ndef run(): return same(1)\n',
        'same.js':'function same(n){return n+1;} function run(row){row.active=true;return same(1);}\n',
        'same.ts':'export function same(n:number){return n+1;} function run(row:any){row.active=true;return same(1);}\n',
        'view.tsx':'function same(n:number){return n+1;} function Card(){return <button/>;} function run(){same(1);return <Card/>;}\n',
        'main.c':'struct Row {int active;}; int same(int n){return n+1;} int run(struct Row *row){row->active=2;return same(1);}\n',
        'main.cpp':'namespace App {struct Row {int active;}; int same(int n){return n+1;} int run(Row *row){row->active=2;return same(1);}}\n',
        'Main.cs':'namespace App; class C {int active; static int Same(int n)=>n+1; int Run(){this.active=2;return Same(1);}}\n',
    }
    for name,source in files.items():
        (tmp_path/name).write_text(source,encoding='utf-8')
    with closing(build(tmp_path,tmp_path/'map.sqlite',workers=1)) as graph:
        caps=graph.capabilities()['languages']
        assert set(caps)=={'python','javascript','typescript','tsx','c','cpp','csharp'}
        assert all(row['files']==1 and row['errors']==0 for row in caps.values())
        assert caps['python']['native_home'] is True
        assert all(row['native_home'] is False for lang,row in caps.items() if lang!='python')
        ids={'same:same', 'javascript/same.js:same', 'typescript/same.ts:same',
             'tsx/view.tsx:same','c/main.c:same','cpp/main.cpp:App.same','csharp/Main.cs:App.C.Same'}
        assert ids <= set(graph.functions())
        calls=graph.calls()
        assert {row['resolved'] for row in calls if row['file']!='same.py' and row['text'] in ('same','Same')}==ids-{'same:same'}
        assert any(row['dst']=='same:same' and row['prov']=='resolved' for row in graph.edges('same:run'))
        component=next(row for row in calls if row.get('kind')=='jsx-element')
        assert component['text']=='Card' and component['resolved'] is None and component['reason']
        for language in ('javascript','typescript','c','cpp','csharp'):
            writes=graph.assignments(language=language)
            assert any(row['field']=='active' and row['literal'] for row in writes)
            assert any(row['value']=='active' for row in graph.keys(language=language))
        for ident in ids:
            node=graph.node(ident)
            assert node['fp'] and node['line']==1 and node['column']>=1
        assert graph.query_coverage()['complete']
    with closing(build(tmp_path,tmp_path/'map.sqlite',workers=1)) as graph:
        assert graph.stats['parsed']==0 and graph.stats['changed'] is False
        assert set(graph.capabilities()['languages'])==set(caps)


def test_csharp_full_candidates_resolve_only_real_unique_lexical_declarations(tmp_path):
    (tmp_path/'App.cs').write_text('namespace App; class C { static int Pick(int n)=>n; '
        'static int Pick(string n)=>0; static int Unique(int n)=>n; '
        'int Run(){ int Local(int n)=>n+1; return Local(1)+Local(Unique(1))+Pick(1); }}',encoding='utf-8')
    with closing(build(tmp_path,tmp_path/'map.sqlite',workers=1)) as graph:
        rows=graph.calls()
        calls={row['text']:row for row in rows}
        assert calls['Unique']['resolved']=='csharp/App.cs:App.C.Unique'
        local=[row for row in rows if row['text']=='Local']
        assert local[0]['resolved']=='csharp/App.cs:App.C.Run.Local'
        assert local[1]['resolved'] is None and local[1]['reason']
        assert calls['Pick']['resolved'] is None and calls['Pick']['reason']
        assert len([node for node in graph.functions().values() if node['qual'].startswith('App.C.Pick')])==2
