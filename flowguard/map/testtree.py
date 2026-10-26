"""Read-only test functions, exact anchors and statically resolved project calls."""
from __future__ import annotations
import ast
from pathlib import Path
from .common import read_source
from .inventory import resolve_module


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
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith("test"):
            out[n.name]=n
        elif isinstance(n,ast.ClassDef) and eligible(n):
            out.update({n.name+"."+m.name:m for m in n.body if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)) and m.name.startswith("test")})
    return out


def resolve_test_anchor(path, symbol):
    """Exact qualified test first, otherwise a unique qualified suffix; strip item parameters."""
    symbol=symbol.split("[",1)[0].replace("::",".")
    try: found=test_functions(read_source(Path(path)))
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
    for cls in (n for n in tree.body if isinstance(n,ast.ClassDef)):
        helpers.update({cls.name+'.'+n.name:n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))})
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
            exports = {info.module: info.lazy_exports for info in inv.py.values() if info.lazy_exports}
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
                    result.update(target+':'+value for value in inv.py[target].symbols if value.startswith(qualified+'.'))
                    break
        return result
    return {name:calls(node,module_imports,name.rpartition('.')[0],1) for name,node in functions.items()}
