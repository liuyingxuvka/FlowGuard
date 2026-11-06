"""Literal source truths for the shared graph, not compiler/execution claims."""
from contextlib import closing
import json
from pathlib import Path
import subprocess
import sys

from flowguard.structure import build


def project(tmp_path, files):
    for name, content in files.items():
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8')
    return build(tmp_path,tmp_path/'graph.sqlite',workers=1)


def test_typescript_import_alias_reexport_and_path_config(tmp_path):
    with closing(project(tmp_path, {
        'tsconfig.json':json.dumps({'compilerOptions':{'baseUrl':'.','paths':{'@/*':['src/*']}}}),
        'src/owner.ts':'export function inc(x:number){ return x+1; }\n',
        'src/public.ts':'export {inc as grow} from "./owner.js";\n',
        'app.ts':'import {grow as bump} from "@/public";\nexport const run=(x:number)=>bump(x);\n',
    })) as graph:
        call=graph.calls()[0]
        assert call['text']=='bump' and call['line']==2
        assert call['resolved']=='typescript/src/owner.ts:inc'
        assert graph.node('typescript/app.ts:run')['kind']=='function'
        assert graph.imports(declarations=True)[0]['module']=='@/public'
        assert graph.capabilities()['languages']['typescript']['files']==3
        assert graph.capabilities()['languages']['typescript']['native_home'] is False


def test_javascript_dynamic_and_shadow_do_not_borrow_named_function(tmp_path):
    with closing(project(tmp_path,{'a.js':'''function apply(x){return x;}
function dynamic(registry,key,x){const target=registry[key];return target(x);}
function shadow(apply,x){return apply(x);}
function run(x){return apply(x);}
'''})) as graph:
        calls={row['scope']:row for row in graph.calls()}
        assert calls['dynamic']['resolved'] is None and calls['dynamic']['reason']
        assert calls['shadow']['resolved'] is None and calls['shadow']['reason']
        assert calls['run']['resolved']=='javascript/a.js:apply'
        computed=[row for row in graph.calls(include_reads=True) if row.get('text')=='registry[key]']
        assert computed and computed[0]['reason']
        assert any(row['prov']=='unknown' for row in graph.edges('javascript/a.js:dynamic'))


def test_unicode_newlines_positions_and_definite_field_changes(tmp_path):
    source='// 中文\nexport function 检查(row){row.active=true;return row.active;}\n'
    path=tmp_path/'状态.js';path.write_bytes(b'\xef\xbb\xbf'+source.replace('\n','\r\n').encode())
    with closing(build(tmp_path,tmp_path/'graph.sqlite',workers=1)) as graph:
        node=graph.node('javascript/状态.js:检查')
        assert (node['line'],node['column'],node['end_line'])==(2,8,2)
        writes=graph.assignments()
        assert writes[0]['field']=='active' and writes[0]['value'] is True
        assert any(row['value']=='active' for row in graph.keys())
        before=node['fp']
    path.write_text(source.replace('=true','=false'),encoding='utf-8')
    with closing(build(tmp_path,tmp_path/'graph.sqlite',workers=1)) as graph:
        assert graph.node('javascript/状态.js:检查')['fp']!=before
        assert graph.assignments()[0]['value'] is False
        assert 'javascript/状态.js:检查' in graph.impact(['状态.js'])['dirty']


def test_config_only_change_relinks_alias_and_warm_build_reuses_files(tmp_path):
    cfg=tmp_path/'tsconfig.json'
    with closing(project(tmp_path,{
        'tsconfig.json':json.dumps({'compilerOptions':{'paths':{'@/*':['one/*']}}}),
        'one/owner.ts':'export function owner(){return 1;}\n',
        'two/owner.ts':'export function owner(){return 2;}\n',
        'app.ts':'import {owner} from "@/owner";function run(){return owner();}\n',
    })) as graph:
        assert graph.calls()[0]['resolved']=='typescript/one/owner.ts:owner'
    with closing(build(tmp_path,tmp_path/'graph.sqlite',workers=1)) as graph:
        assert graph.stats['parsed']==0 and graph.stats['changed'] is False
    cfg.write_text(json.dumps({'compilerOptions':{'paths':{'@/*':['two/*']}}}))
    with closing(build(tmp_path,tmp_path/'graph.sqlite',workers=1)) as graph:
        assert graph.stats['changed'] and graph.stats['parsed']==3
        assert graph.calls()[0]['resolved']=='typescript/two/owner.ts:owner'


def test_tsx_component_reference_and_overload_uncertainty(tmp_path):
    with closing(project(tmp_path,{'a.tsx':'''function pick(x:string):string;
function pick(x:number):number;
function pick(x:unknown){return x;}
export function Card(){return <button/>;}
export const Page=()=> <Card/>;
function run(){return pick(1);}
'''})) as graph:
        calls=graph.calls()
        jsx=next(row for row in calls if row.get('kind')=='jsx-element')
        assert jsx['text']=='Card' and jsx['resolved'] is None and jsx['reason']
        overloaded=next(row for row in calls if row['text']=='pick')
        assert overloaded['resolved'] is None and overloaded['reason']
        assert len([row for row in graph.functions().values() if row['qual'].split('@')[0]=='pick'])==3


def test_python_only_does_not_import_any_foreign_grammar(tmp_path):
    (tmp_path/'a.py').write_text('def run():return 1\n')
    command='''import sys
from flowguard.structure import build
with_map=build(sys.argv[1],sys.argv[2],workers=1)
assert with_map.node('a:run')['language']=='python'
assert not any(name.startswith('tree_sitter') for name in sys.modules),list(sys.modules)
with_map.close()
'''
    run=subprocess.run([sys.executable,'-c',command,str(tmp_path),str(tmp_path/'graph.sqlite')],capture_output=True,text=True)
    assert run.returncode==0,run.stdout+run.stderr


def test_enclosing_shadow_namespace_alias_and_reassignment_are_not_borrowed(tmp_path):
    with closing(project(tmp_path,{
        'owner.ts':'export function inc(x:number){return x+1;}\n',
        'app.ts':'''import * as ops from './owner';
function target(){return 1;}
function outer(target:Function){function inner(){return target();}return inner();}
function good(){return ops.inc(1);}
function shadow(ops:any){return ops.inc(1);}
function changing(){target=()=>2;}
function run(){return target();}
'''})) as graph:
        rows=graph.calls()
        nested=next(row for row in rows if row['scope']=='outer.inner')
        assert nested['resolved'] is None and nested['reason']
        assert next(row for row in rows if row['scope']=='good')['resolved']=='typescript/owner.ts:inc'
        shadow=next(row for row in rows if row['scope']=='shadow')
        assert shadow['resolved'] is None and shadow['reason']
        changed=next(row for row in rows if row['scope']=='run')
        assert changed['resolved'] is None and changed['reason']


def test_new_missing_dependency_then_rename_and_git_fingerprint_are_visible(tmp_path):
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=tmp_path,text=True).strip()
    git('init','-q');git('config','user.email','fixture@example.invalid');git('config','user.name','Fixture')
    with closing(project(tmp_path,{'app.ts':'import {inc} from "./owner";function run(){return inc(1);}\n'})) as graph:
        assert graph.calls()[0]['resolved'] is None
    (tmp_path/'owner.ts').write_text('export function inc(x:number){return x+1;}\n')
    with closing(build(tmp_path,tmp_path/'graph.sqlite',workers=1)) as graph:
        assert graph.stats['parsed']==1
        assert graph.calls()[0]['resolved']=='typescript/owner.ts:inc'
        original=graph.node('typescript/owner.ts:inc')['fp']
    git('add','app.ts','owner.ts');git('commit','-qm','original')
    rev=git('rev-parse','HEAD')
    (tmp_path/'owner.ts').write_text('export function grown(x:number){return x+1;}\n')
    with closing(build(tmp_path,tmp_path/'graph.sqlite',workers=1)) as graph:
        assert graph.node('typescript/owner.ts:grown')['fp']==original
        assert graph.calls()[0]['resolved'] is None
        assert graph.fingerprint_at(rev,'typescript/owner.ts:inc')[0]==original
        assert 'typescript/owner.ts:inc' in graph.impact(['owner.ts'],since=rev)['removed']
        assert any(row['new']=='typescript/owner.ts:grown' for row in graph.moved(['typescript/owner.ts:inc']))


def test_imported_overloads_do_not_resolve_to_the_first_signature(tmp_path):
    with closing(project(tmp_path,{
        'owner.ts':'export function pick(x:string):string;\nexport function pick(x:number):number;\nexport function pick(x:unknown){return x;}\n',
        'app.ts':'import {pick} from "./owner";function run(){return pick(1);}\n',
    })) as graph:
        call=graph.calls()[0]
        assert call['resolved'] is None and call['reason']
