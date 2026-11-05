"""Read-only test functions, exact anchors and statically resolved project calls."""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path
from .common import read_source
from .inventory import resolve_module, syntax_tree as _syntax, inventory_memo


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
    try: tree=_syntax(text)
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
    """One content-keyed call scan per inventory, with fresh mutable results for callers."""
    memo = inventory_memo(inv, 'test_calls')
    key = (path, hashlib.sha256(text.encode('utf-8')).digest())
    if key not in memo:
        memo[key] = _test_calls(path, text, inv)
    return {test: set(calls) for test, calls in memo[key].items()}


def _test_calls(path, text, inv):
    """Per-test direct project calls, including one same-file helper level and constructors."""
    try: tree=_syntax(text)
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
                syntax = _syntax(read_source(inv.root / target))
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
    walked = {}
    def calls(node, env, owner, depth):
        if id(node) not in walked:
            walked[id(node)] = list(ast.walk(node))
        nodes = walked[id(node)]
        result=set(); env=imports(nodes,env)
        instances={}
        for n in nodes:
            if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call):
                origin=dotted(n.value.func)
                for target in n.targets:
                    if isinstance(target,ast.Name): instances[target.id]=origin
        for n in nodes:
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



def test_units(nodeids, weights, shard_count):
    """Split overweight real directory/file groups; one function's cases stay together."""
    from collections import defaultdict
    children = defaultdict(dict)
    root = ()
    for node in nodeids:
        path, function, _ = _node_function(node)
        parts = (*Path(path).parts, '::' + function)
        for length in range(1, len(parts) + 1):
            parent, key = parts[:length - 1], parts[:length]
            children[parent].setdefault(key, []).append(node)
    def weight(items):
        return sum(max(0.01, float(weights.get(item, 0.01))) for item in items)
    share = weight(nodeids) / shard_count
    units = {root: tuple(nodeids)}
    while True:
        choices = [(key, children[key]) for key, items in units.items()
                   if weight(items) > share and children.get(key)]
        if not choices:
            break
        key, split = min(choices, key=lambda pair: (-weight(units[pair[0]]), pair[0]))
        del units[key]
        units.update((part, tuple(items)) for part, items in split.items())
    def label(key):
        if not key:
            return '.'
        return '/'.join(key[:-1]) + key[-1] if key[-1].startswith('::') else '/'.join(key)
    return {label(key): items for key, items in sorted(units.items()) if items}

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
