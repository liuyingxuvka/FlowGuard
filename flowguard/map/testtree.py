"""Read-only test functions, exact anchors and statically resolved project calls."""
from __future__ import annotations
import ast
from pathlib import Path
from .common import read_source
from .inventory import resolve_module


def _class_methods(syntax):
    classes={node.name:node for node in syntax.body if isinstance(node,ast.ClassDef)}
    def methods(name,seen=()):
        if name in seen or name not in classes:return {}
        cls=classes[name];result={}
        for base in cls.bases:
            parent=base.id if isinstance(base,ast.Name) else ''
            result.update(methods(parent,(*seen,name)))
        result.update({node.name:node for node in cls.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))})
        return result
    return {name:methods(name) for name in classes}


def test_functions(text):
    """Qualified test function names mapped to their syntax nodes; no imports or execution."""
    try: tree=ast.parse(text)
    except SyntaxError: return {}
    classes={n.name:n for n in tree.body if isinstance(n,ast.ClassDef)}
    def name(n):
        return n.id if isinstance(n,ast.Name) else n.attr if isinstance(n,ast.Attribute) else ""
    def eligible(cls, seen=()):
        if cls.name in seen: return False
        return cls.name.startswith("Test") or any(name(b) in ("TestCase","IsolatedAsyncioTestCase") or
            name(b) in classes and eligible(classes[name(b)],(*seen,cls.name)) for b in cls.bases)
    out={}
    inherited=_class_methods(tree)
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith("test"):
            out[n.name]=n
        elif isinstance(n,ast.ClassDef) and eligible(n):
            out.update({n.name+"."+name:method for name,method in inherited[n.name].items() if name.startswith("test")})
    return out


def resolve_test_anchor(path, symbol, *, functions=None):
    """Exact qualified test first, otherwise a unique qualified suffix; strip item parameters."""
    symbol=symbol.split("[",1)[0].replace("::",".")
    try: found=functions if functions is not None else test_functions(read_source(Path(path)))
    except OSError: return None
    if symbol in found: return symbol
    matches=[n for n in found if n.endswith("."+symbol)]
    return matches[0] if len(matches)==1 else None


def test_calls(path, text, inv):
    """Per-test direct project calls, including one same-file helper level and constructors."""
    try: tree=ast.parse(text)
    except SyntaxError: return {}
    def dotted(n):
        if isinstance(n,ast.Name): return n.id
        if isinstance(n,ast.Attribute):
            left=dotted(n.value)
            return left+"."+n.attr if left else ""
        return ""
    module_imports={}
    def imports(nodes, inherited):
        result=dict(inherited)
        for n in nodes:
            if isinstance(n,ast.Import):
                for a in n.names: result[a.asname or a.name.split('.')[0]]=(a.name if a.asname else a.name.split('.')[0],"")
            elif isinstance(n,ast.ImportFrom):
                module=n.module or ""
                if n.level:
                    parts=path.removesuffix('.py').split('/')[:-1]
                    module='.'.join(parts[:len(parts)-n.level+1]+([module] if module else []))
                for a in n.names: result[a.asname or a.name]=(module,a.name)
        return result
    module_imports=imports(tree.body,{})
    helpers={n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    functions=test_functions(text)
    # Methods may call one same-file helper through self or cls.
    for owner,methods in _class_methods(tree).items():
        helpers.update({owner+'.'+name:method for name,method in methods.items()})
    exports = {info.module: info.lazy_exports for info in inv.py.values() if info.lazy_exports}
    classes = {}
    def constructor(target, symbol):
        if target not in classes:
            classes[target] = set()
            try:
                syntax = ast.parse(read_source(inv.root / target))
            except (OSError, SyntaxError):
                return False
            def collect(nodes, prefix=""):
                for item in nodes:
                    if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        name = prefix + item.name
                        if isinstance(item, ast.ClassDef):
                            classes[target].add(name)
                        collect(item.body, name + ".")
            collect(syntax.body)
        return symbol in classes[target]
    def calls(node, env, owner, depth):
        result=set(); env=imports(ast.walk(node),env)
        instances={}
        for n in ast.walk(node):
            if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call):
                origin=dotted(n.value.func)
                for target in n.targets:
                    if isinstance(target,ast.Name): instances[target.id]=origin
        for n in ast.walk(node):
            if not isinstance(n,ast.Call): continue
            name=dotted(n.func); first,_,rest=name.partition('.')
            if first in instances:
                name=instances[first]+('.'+rest if rest else ''); first,_,rest=name.partition('.')
            helper=name
            if first in ('self','cls') and rest: helper=owner+'.'+rest
            if depth and helper in helpers:
                result.update(calls(helpers[helper],env,owner,0))
            if first not in env: continue
            module,symbol=env[first]
            if symbol and symbol in exports.get(module, {}):
                module = exports[module][symbol]
            elif not symbol and rest:
                exported, _, tail = rest.partition('.')
                if exported in exports.get(module, {}):
                    module, symbol, rest = exports[module][exported], exported, tail
            parts = [*module.split('.'), *([symbol] if symbol else []), *rest.split('.')]
            parts = [part for part in parts if part]
            for cut in range(len(parts)-1, 0, -1):
                target = resolve_module('.'.join(parts[:cut]), path, inv.mod_to_path, inv.py, inv.import_roots)
                qualified = '.'.join(parts[cut:])
                if target and qualified in inv.py[target].symbols:
                    result.add(target+':'+qualified)
                    members = {value for value in inv.py[target].symbols if value.startswith(qualified+'.')}
                    if members and constructor(target, qualified):
                        result.update(target+':'+value for value in members)
                    break
        return result
    return {name:calls(node,module_imports,name.rpartition('.')[0],1) for name,node in functions.items()}


def _node_function(nodeid):
    path, _, symbol = nodeid.partition('::')
    plain, marker, parameter = symbol.partition('[')
    return path, plain.replace('::','.'), '['+parameter if marker else ''


def _bindings(root, tree, functions):
    """Resolved binding identities, retaining case-specific selectors."""
    from collections import defaultdict
    from .common import parse_test_anchor
    result=defaultdict(set)
    for mid,node in tree.nodes.items():
        for anchors in node.contract.get('TESTED_BY',{}).values():
            for anchor in anchors:
                try:path,symbol,parameter=parse_test_anchor(anchor)
                except ValueError:continue
                if path not in functions:continue
                actual=resolve_test_anchor(root/path,symbol,functions=functions[path])
                if actual:result[(path,actual,parameter)].add(mid)
    return result


def _parents(data,tree):
    return {**{c['id']:c.get('parent') or 'system' for c in data['components']},
            **{mid:node.parent if node.parent_kind in ('model','component') else 'system' for mid,node in tree.nodes.items()}}


def _chain(node,parents):
    result=[]
    while node not in result:
        result.append(node)
        if node=='system':break
        node=parents.get(node,'system')
    return result


def common_position(nodes,parents):
    nodes=list(nodes)
    if not nodes:return 'system'
    return next((node for node in _chain(nodes[0],parents) if all(node in _chain(other,parents) for other in nodes[1:])), 'system')


def test_layout(root,data,inv,tree,nodeids):
    """One operation-local position calculation, shared by all test views and scheduling."""
    from collections import Counter,defaultdict
    from .mapfile import owner_index
    from .common import matches_any
    functions={};calls={}
    for path in sorted({*inv.tests,*(_node_function(node)[0] for node in nodeids)}):
        if not path.endswith('.py'):continue
        try:source=read_source(root/path)
        except OSError:continue
        functions[path]=test_functions(source)
        calls[path]=test_calls(path,source,inv)
    bindings=_bindings(root,tree,functions)
    parents=_parents(data,tree)
    owner,_=owner_index(data,inv)
    order={c['id']:index for index,c in enumerate(data['components'])}
    file_models=defaultdict(lambda:defaultdict(set))
    file_bound=defaultdict(Counter)
    for (path,name,param),models in bindings.items():
        for mid in models:file_models[path][mid].add(name)
    for path,models in file_models.items():
        for mid,names in models.items():
            home=tree.nodes[mid].home
            file_bound[path][home]=max(file_bound[path][home],len(names))
    positions={};bound={}
    for nodeid in nodeids:
        path,name,param=_node_function(nodeid)
        models=set(bindings.get((path,name,''),()))
        if param:models.update(bindings.get((path,name,param),()))
        else:
            models.update(mid for (p,n,case),mids in bindings.items() if (p,n)==(path,name) for mid in mids)
        bound[nodeid]=models
        if models:
            positions[nodeid]=common_position(sorted(models),parents);continue
        direct=Counter(owner[target.partition(':')[0]] for target in calls.get(path,{}).get(name,()) if target.partition(':')[0] in owner)
        imported=Counter(owner[target] for target in inv.file_deps.get(path,()) if target in owner)
        candidates=[c['id'] for c in data['components'] if matches_any(path,c.get('tests',()))]
        if direct:
            positions[nodeid]=min(direct,key=lambda cid:(-direct[cid],order[cid]));continue
        if not candidates:candidates=list(imported)
        positions[nodeid]=min(candidates,key=lambda cid:(-imported[cid],-file_bound[path][cid],order[cid])) if candidates else 'system'
    return dict(positions=positions,bound=bound,parents=parents,functions=functions,calls=calls)


def test_positions(root,data,inv,tree,nodeids):
    """Collected case -> lowest binding ancestor, otherwise the best source component."""
    return test_layout(root,data,inv,tree,nodeids)['positions']


def test_units(root,data,inv,tree,nodeids,weights,shard_count):
    """Split only overweight tree/file units; every function's cases stay indivisible."""
    from collections import defaultdict
    layout=test_layout(root,data,inv,tree,nodeids)
    parents=layout['parents'];positions=layout['positions']
    groups=defaultdict(list)
    for node in nodeids:
        path,_,_=_node_function(node);groups[(positions[node],path)].append(node)
    children=defaultdict(list)
    for node,parent in parents.items():children[parent].append(node)
    def descendants(node):
        return {other for other in parents if node in _chain(other,parents)}|{node}
    def under(node):
        scope=descendants(node)
        return tuple(item for item in nodeids if positions[item] in scope)
    units={node:under(node) for node in sorted(children['system']) if under(node)}
    units.update({path+'@system':tuple(items) for (node,path),items in groups.items() if node=='system'})
    def parts(label):
        if label in parents:
            result={child:under(child) for child in sorted(children[label]) if under(child)}
            result.update({path+'@'+label:tuple(items) for (node,path),items in groups.items() if node==label})
            return result
        if '::' in label:return {}
        if '@' not in label:return {}
        path,node=label.rsplit('@',1);by_function=defaultdict(list)
        for item in units[label]:
            _,name,_=_node_function(item);by_function[name].append(item)
        return {path+'::'+name.replace('.','::')+'@'+node:tuple(items) for name,items in sorted(by_function.items())}
    def weight(items):return sum(max(0.01,float(weights.get(item,0.01))) for item in items)
    share=weight(nodeids)/shard_count
    while True:
        candidates=[(label,parts(label)) for label,items in units.items() if weight(items)>share]
        candidates=[(label,split) for label,split in candidates if split and not (len(split)==1 and next(iter(split.values()))==units[label] and next(iter(split))==label)]
        if not candidates:break
        label,split=min(candidates,key=lambda pair:(-weight(units[pair[0]]),pair[0]))
        del units[label];units.update(split)
    return units


class TestIndex(dict):
    """A view's finite function inventory and transient tree positions; never stored."""
    def __init__(self,root,data,inv,tree,functions):
        super().__init__(functions)
        self.nodeids=tuple(path+'::'+name.replace('.','::') for path,names in functions.items() for name in sorted(names))
        self.layout=test_layout(root,data,inv,tree,self.nodeids)
        self.bound_functions={_node_function(node)[:2] for node,mids in self.layout['bound'].items() if mids}

    def component_facts(self,cid,limit=5):
        chosen=[node for node in self.nodeids if cid in _chain(self.layout['positions'][node],self.layout['parents'])]
        bound=sum(bool(self.layout['bound'][node]) for node in chosen)
        files=sorted({_node_function(node)[0] for node in chosen})
        listing=', '.join(files[:limit])+(f', +{len(files)-limit}' if len(files)>limit else '')
        return (f'{len(chosen)} functions here and below (bound {bound}, unbound {len(chosen)-bound}); files: '+(listing or '-'),),len(chosen)


TEST_FUNCTION_LIMITS=(40,60)
DURATION_SCHEMA='flowguard.test_durations.v1'


def duration_record(root):
    import json,math
    try:
        data=json.loads((root/'.flowguard/cache/test-durations.json').read_text())
        if data.get('schema')!=DURATION_SCHEMA or not isinstance(data.get('files'),dict) or not isinstance(data.get('seconds'),dict):return None
        if not all(isinstance(path,str) and isinstance(value,str) for path,value in data['files'].items()):return None
        if not all(isinstance(node,str) and isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0 for node,value in data['seconds'].items()):return None
        return data
    except (OSError,ValueError,TypeError,AttributeError):return None


def duration_weights(root,nodeids):
    """Use exact file digests; a renamed file may reuse its identical source's seconds."""
    from .common import content_digest
    record=duration_record(root)
    if record is None:return {}
    digests={}
    for node in nodeids:
        path,_,_= _node_function(node)
        if path not in digests:
            try:digests[path]=content_digest(root/path)
            except OSError:digests[path]=None
    found={}
    for node in nodeids:
        path,_,_=_node_function(node);digest=digests[path]
        if digest is None:continue
        if record['files'].get(path)==digest and node in record['seconds']:
            found[node]=max(0.01,float(record['seconds'][node]));continue
        # A changed existing file must not borrow another file's identically named test.
        if path in record['files']:continue
        tail=node.partition('::')[2]
        matches=[value for other,value in record['seconds'].items() if other.partition('::')[2]==tail and not (root/other.partition('::')[0]).exists() and record['files'].get(other.partition('::')[0])==digest]
        if matches:found[node]=max(0.01,sum(matches)/len(matches))
    return found


def test_file_findings(root,data,inv,tree):
    """Deterministic soft/hard file bounds plus optional, non-gating elapsed-time advice."""
    from collections import Counter,defaultdict
    from .common import Finding,content_digest
    functions={}
    for path in inv.tests:
        if path.endswith('.py'):
            try:functions[path]=test_functions(read_source(root/path))
            except OSError:pass
    bindings=_bindings(root,tree,functions)
    counts=defaultdict(lambda:defaultdict(set));bound=defaultdict(set)
    for (path,name,param),mids in bindings.items():
        bound[path].add(name)
        for mid in mids:
            top=tree.ancestors(mid);counts[path][top[-1] if top else mid].add(name)
    findings=[]
    for path,names in sorted(functions.items()):
        roots={mid:len(tests) for mid,tests in counts[path].items()}
        related=sorted(((mid,count) for mid,count in roots.items() if count>=3))
        hard=[(mid,count) for mid,count in related if count>=6]
        directory=str(Path(path).parent)
        if len(hard)>=2:
            details=', '.join(f'{mid} {count}' for mid,count in hard)
            findings.append(Finding('error','test_file_mixes_models',path,f'{path} binds {details} (hard limit: 6 in each of two unrelated subtrees); split it in a target: move each subtree\'s bound tests to {directory}/test_<T>.py (references/routes.md#Split a test file)'))
        else:
            for mid,count in related:
                if len(related)>=2 or len(names)>=20 and count/len(names)<0.25:
                    findings.append(Finding('warn','test_file_mixes_models',path,f"{path}: move {mid}'s {count} bound test(s) to {directory}/test_{mid}.py ({len(names)} test functions in the file; split before 6 per subtree)"))
        soft,hard_limit=TEST_FUNCTION_LIMITS
        if len(names)>soft:
            detail=', '.join(f'{mid} {count}' for mid,count in sorted(roots.items())) or '-'
            unbound=len(set(names)-bound[path])
            message=(f'{path}: {len(names)} test functions, over the hard limit {hard_limit}; split it in a target by model: {detail} bound; {unbound} unbound (references/routes.md#Split a test file)' if len(names)>hard_limit else
                     f'{path}: {len(names)} test functions (soft limit {soft}; split before {hard_limit}); split it by model: {detail} bound; {unbound} unbound (move each by the split rule of references/routes.md#Split a test file)')
            findings.append(Finding('error' if len(names)>hard_limit else 'warn','large_test_file',path,message))
    record=duration_record(root)
    if record:
        seconds=Counter()
        for node,value in record['seconds'].items():
            path=node.partition('::')[0]
            if path not in functions:continue
            try:valid=record['files'].get(path)==content_digest(root/path)
            except OSError:valid=False
            if valid:seconds[path]+=value
        limit=data.get('large_test_seconds',60)
        for path,total in sorted(seconds.items()):
            if total>limit:findings.append(Finding('info','large_test_file',path,f'{path}: {total:.1f}s (advice limit {limit:g}s); a split by model usually helps'))
    return findings


def test_file_not_split_findings(root,data,inv,before,after,moves):
    """A one-to-one model/test split moves both halves in the same target."""
    from collections import defaultdict
    from .common import Finding
    functions={}
    for path in inv.tests:
        try:functions[path]=test_functions(read_source(root/path))
        except OSError:continue
    def combined(tree):
        merged=defaultdict(set)
        for (path,name,param),mids in _bindings(root,tree,functions).items():merged[(path,name)].update(mids)
        return merged
    old,new=combined(before),combined(after)
    findings=[]
    for donor in moves:
        entire={pair for pair,mids in old.items() if donor in mids}
        files={path for path,name in entire}
        if len(files)!=1:continue
        path=next(iter(files))
        if any(mids!={donor} for (file,name),mids in old.items() if file==path):continue
        recipients=defaultdict(set)
        for (file,name),mids in new.items():
            if file==path and len(mids)==1:recipients[next(iter(mids))].add(name)
        if len(recipients)<2:continue
        directory=str(Path(path).parent)
        destinations=', '.join(f'{mid} {len(names)} -> {directory}/test_{mid}.py' for mid,names in sorted(recipients.items()))
        message=f'{path} tested only {donor}, whose rules moved to '+', '.join(sorted(recipients))+f'; split it with the model in this target: {destinations} (move the TESTED_BY paths too)'
        findings.append(Finding('warn','test_file_not_split',path,message))
    return findings
