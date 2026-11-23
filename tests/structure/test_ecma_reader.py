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


def test_a_module_constant_array_of_literals_is_a_literal_assignment_and_other_arrays_stay_unknown(tmp_path):
    # Planning Tool's `export const PROBABILITY_STEPS = [0, 5, 50, 75, 90, 100] as const` (T4): through `as const`,
    # `satisfies` and parentheses, negative numbers and a trailing comma too; never a made-up value for a hole, a
    # spread, a name, a nested array, a destructuring or a function's own array.
    with closing(project(tmp_path, {'a.ts': '''export const PROBABILITY_STEPS = [0, 5, 50, 75, 90, 100] as const;
const NAMES = ['a', "b", ] satisfies readonly string[];
const OFFSETS = ([-1, 2.5, /* none */ -0.5]);
const HOLE = [1, , 2];
const SPREAD = [...NAMES, 'c'];
const NAMED = [1, PROBABILITY_STEPS];
const NESTED = [[1]];
const EMPTY = [];
const [first, second] = [1, 2];
export function f() { const LOCAL = [1, 2]; return LOCAL; }
'''})) as graph:
        rows = {row['target']: (row['literal'], row['value']) for row in graph.assignments(include_unknown=True)
                if row['form'] == 'declarator'}
    assert rows == {'PROBABILITY_STEPS': (True, [0, 5, 50, 75, 90, 100]), 'NAMES': (True, ['a', 'b']),
                    'OFFSETS': (True, [-1, 2.5, -0.5]), 'HOLE': (False, None), 'SPREAD': (False, None),
                    'NAMED': (False, None), 'NESTED': (False, None), 'EMPTY': (False, None),
                    '[first, second]': (False, None), 'LOCAL': (False, None)}


ALWAYS_CALLED = [
    ('await helper(tx);', 0), ('await svc.helper(tx);', 0), ('return helper(tx);', 0), ('if (helper(tx)) {}', 0),
    ('const x = helper(tx) ? 1 : 2;', 0), ('helper(tx) && s;', 0), ('for (const i of helper(tx)) {}', 0),
    ('do {\n  helper(tx);\n} while (s);', 0), ("if (!s) throw new Error('no');\nhelper(tx);", 0),
    ('function later() { return 1; }\nhelper(tx);', 0),
    ('await prisma.$transaction(async (tx) => {\n  await helper(tx);\n});', 1),
    ('await prisma.$transaction((tx) => helper(tx));', 1), ('items.forEach((item) => helper(item));', 1),
    ('if (s) {\n  helper(tx);\n}', None), ('if (s) helper(tx);', None), ('if (s) {} else {\n  helper(tx);\n}', None),
    ('const x = s ? helper(tx) : null;', None), ('s && helper(tx);', None), ('const x = s ?? helper(tx);', None),
    ('x ||= helper(tx);', None), ('svc?.helper(tx);', None), ('helper?.(tx);', None), ('a?.b(helper(tx));', None),
    ('for (const item of items) {\n  helper(item);\n}', None), ('for (let i = 0; i < n; i++) {\n  helper(i);\n}', None),
    ('while (s) {\n  helper(tx);\n}', None), ('try {\n  helper(tx);\n} catch (error) {}', None),
    ('try {} finally {\n  helper(tx);\n}', None), ('switch (s) {\n  case 1:\n    helper(tx);\n}', None),
    ('if (!s) return;\nhelper(tx);', None),
    ('await prisma.$transaction(async (tx) => {\n  if (!s) return;\n  await helper(tx);\n});', None),
    ('function later() {\n  helper(tx);\n}\nlater();', None), ('const later = () => helper(tx);\nlater();', None),
    ('helperX(tx);', None),
    # 5.1 review (FM open 3): a continue or break before the call in a do-while body, a labelled block that breaks to
    # its label, a destructuring or parameter default, an optional access and a kind the query does not know (a throw,
    # JSX, a class's static block) leave the call on some paths only
    ('do {\n  if (s) continue;\n  helper(tx);\n} while (s);', None), ('do {\n  if (s) break;\n  helper(tx);\n} while (s);', None),
    ('do {\n  for (const i of items) { if (i) continue; }\n  helper(tx);\n} while (s);', 0),
    ('do {\n  switch (s) { case 1: break; }\n  helper(tx);\n} while (s);', 0),
    ('block: {\n  if (s) break block;\n  helper(tx);\n}', None), ('block: {\n  helper(tx);\n  if (s) break block;\n}', None),
    ('block: {\n  helper(tx);\n}', 0), ('block: {\n  if (s) break block;\n}\nhelper(tx);', 0),
    ('outer: for (const i of items) {\n  for (const j of items) { if (j) continue outer; }\n}\nhelper(tx);', 0),
    ('const { a = helper(tx) } = s;', None), ('const [b = helper(tx)] = items;', None), ('({ a = helper(tx) } = s);', None),
    ('await prisma.$transaction(async (tx2 = helper(tx)) => tx2);', None), ('s?.[helper(tx)];', None),
    ('x?.(helper(tx));', None), ('helper(tx)?.x;', 0), ('x[helper(tx)] = 1;', 0), ('throw helper(tx);', None),
    ('class Inner { static { helper(tx); } }', None),
]


def test_a_call_on_every_path_crosses_no_branch_or_named_function_and_counts_its_callbacks():
    """PEMEL17-18 for JS/TS: the fewest anonymous callbacks a call of `helper` crosses where it runs whenever the
    function returns (Planning Tool's `prisma.$transaction(async (tx) => ...)` is one), or None."""
    from flowguard.structure.readers.common import parse
    from flowguard.structure.readers.ecma import call_on_every_path
    for body, crossed in ALWAYS_CALLED:
        text = ('export async function f(tx: any, s: any, items: any[], x: any, a: any, n: number, svc: any) {\n'
                + ''.join(f'  {line}\n' for line in body.splitlines()) + '}\n')
        source, tree = parse(text.encode(), 'typescript')
        assert not tree.root_node.has_error, body
        assert call_on_every_path(source, tree, (1, text.count('\n')), 'helper') == crossed, body
    # only the calls on the lines of the map's call edges, when it has them
    source, tree = parse(b'export function g(s: any) {\n  if (s) helper(1);\n  helper(2);\n}\n', 'typescript')
    assert [call_on_every_path(source, tree, (1, 4), 'helper', lines) for lines in (None, {2}, {3})] == [0, None, 0]
    # a callback on the function's own line is still a callback
    source, tree = parse(b'export const f = (items: any[]) => items.forEach((item) => helper(item));\n', 'typescript')
    assert call_on_every_path(source, tree, (1, 1), 'helper') == 1
