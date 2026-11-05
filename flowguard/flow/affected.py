"""Incremental scope from existing core receipts and the shared source inventory.

No model or application code runs in the caller. Missing prior evidence means a
first check; a current receipt keeps its actual recipe, including across resumes.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import textwrap
from pathlib import Path


def _digest(value):
    return hashlib.sha256(repr(value).encode()).hexdigest()


def _definition(fn):
    if fn is None:
        return None
    try:
        return ast.dump(ast.parse(textwrap.dedent(inspect.getsource(fn))), include_attributes=False)
    except (OSError, TypeError, SyntaxError):
        return None


def _code(binding, *, sources=None):
    """Method plus same-class helper bodies; other module context stays conservative."""
    spec = binding.native_spec()
    system = spec.get('system')
    if not isinstance(system, str) or ':' not in system:
        return None
    module, cls = system.split(':', 1)
    root = Path(spec['root'])
    path = root / (module.replace('.', '/') + '.py')
    if not path.is_file():
        path = root / module.replace('.', '/') / '__init__.py'
    if not path.is_file():
        return None
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    owner = next((node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == cls), None)
    if owner is None or owner.bases:
        return None
    methods = {}
    aliases = {}
    for node in owner.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # A property's getter/setter/deleter share a name; retain every body.
            methods.setdefault(node.name, []).append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    aliases[target.id] = {item.id for item in ast.walk(node.value) if isinstance(item, ast.Name)}

    def definitions(name):
        pending, seen, used = [name], set(), set()
        while pending:
            member = pending.pop()
            if member in seen:
                continue
            seen.add(member)
            if member not in methods:
                pending.extend(aliases.get(member, ()))
                continue
            used.add(member)
            for method in methods[member]:
                receivers = {'self', 'cls'}
                args = method.args.posonlyargs + method.args.args
                if args and not any(isinstance(d, ast.Name) and d.id == 'staticmethod' for d in method.decorator_list):
                    receivers.add(args[0].arg)
                body = [item for statement in method.body for item in ast.walk(statement)]
                # Ordinary local receiver aliases preserve the same class scope.
                while True:
                    newer = set(receivers)
                    for item in body:
                        if isinstance(item, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                            value = item.value
                            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                            if isinstance(value, ast.Name) and value.id in receivers:
                                newer.update(t.id for t in targets if isinstance(t, ast.Name))
                    if newer == receivers:
                        break
                    receivers = newer
                for decorator in method.decorator_list:
                    if (isinstance(decorator, ast.Attribute) and isinstance(decorator.value, ast.Name)
                            and decorator.attr in {'getter', 'setter', 'deleter'}):
                        pending.append(decorator.value.id)
                for item in body:
                    if isinstance(item, ast.Attribute):
                        if isinstance(item.value, ast.Name) and item.value.id in receivers:
                            pending.append(item.attr)
                        else:
                            # An indirect receiver can be this object. Keep that
                            # operation conservative within this class, not all models.
                            pending.extend(methods)
                    elif isinstance(item, ast.Call):
                        if (isinstance(item.func, ast.Name) and item.func.id in {'getattr', 'setattr', 'delattr'}
                                and item.args and isinstance(item.args[0], ast.Name)
                                and item.args[0].id in receivers):
                            if len(item.args) > 1 and isinstance(item.args[1], ast.Constant) and isinstance(item.args[1].value, str):
                                pending.append(item.args[1].value)
                            else:
                                pending.extend(methods)
                        elif any(isinstance(arg, ast.Name) and arg.id in receivers for arg in item.args):
                            pending.extend(methods)
        return [(key, [ast.dump(node, include_attributes=False) for node in methods[key]]) for key in sorted(used)]
    context = copy.deepcopy(tree)
    for node in context.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            node.body = [item for item in node.body if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                         or item.name == '__init__']
    common = ast.dump(context, include_attributes=False)
    # An imported module changing can affect any call. Use the shared inventory's
    # resolved imports; no second import resolver or dependency cache.
    from ..map.common import DEFAULT_IGNORE, content_digest
    from ..map.inventory import build_inventory
    inv = build_inventory(root, DEFAULT_IGNORE, with_bodies=False)
    relative = path.relative_to(root).as_posix()
    pending, dependencies = list(inv.file_deps.get(relative, ())), set()
    while pending:
        dependency = pending.pop()
        if dependency in dependencies or dependency == relative:
            continue
        dependencies.add(dependency)
        pending.extend(inv.file_deps.get(dependency, ()))
    common = (common, definitions('__init__'),
              [(name, content_digest(root / name)) for name in sorted(dependencies)])
    result = {}
    for action, target in binding.operations.items():
        target = {'name':target} if isinstance(target, str) else target
        name = target.get('name')
        if target.get('receiver', 'system') != 'system' or name not in methods and name not in aliases:
            return None
        result[action] = _digest((common, definitions(name)))
    if sources is not None:
        sources.update(str((root / name).absolute()) for name in dependencies | {relative})
    return result


def _inputs_beyond_code(footprint, sources):
    """Keep actual input stamps; source content is covered by operation digests.

    Only source content hashes may advance. File identity, permissions, missing
    import candidates, directory use and all other physical inputs still compare.
    Retained stamps identify dependencies, not newly executed operation checks.
    """
    from ..native.inputs import file_stamp
    if not isinstance(footprint, dict) or "source_data_reads" not in footprint:
        return footprint
    scoped = copy.deepcopy(footprint)

    def covered(path, previous):
        if path not in sources or path in footprint["source_data_reads"] or not isinstance(previous, dict):
            return previous
        current = file_stamp(path)
        return {**previous, **{key:current[key] for key in ('sha256', 'source_sha256')
                              if key in current and key in previous}}

    scoped['files'] = {path:covered(path, stamp) for path, stamp in scoped.get('files', {}).items()}
    for directory, usage in scoped.get('directory_uses', {}).items():
        for lookup in usage.get('lookups', {}).values():
            lookup['slots'] = {name:covered(str(Path(directory) / name), stamp)
                               for name, stamp in lookup.get('slots', {}).items()}
    return scoped


def native_scope(loaded, baseline, report, *, steps=64, seed=0):
    """Select comparisons after the one model load; source stays outside native inputs."""
    model = loaded.model
    actions = {action.name:_definition(action.fn) for action in model.actions}
    # Fields, settings, rules, construction and adapter projections affect the
    # whole oracle. Action bodies alone can be compared independently.
    binding = model.adapter_binding
    context = ([(repr(f.key), repr(f.domain), repr(f.init)) for f in model.fields],
               dict(model.settings), repr(model.terminals),
               [(r.kind, r.name, _definition(r.pred), _definition(r.when), _definition(r.goal)) for r in model.rules],
               [(o.name, _definition(o.offered)) for o in model.options],
               None if binding is None else (binding.spec, binding.start, binding.prefix, binding.operations,
                   _definition(binding.state), _definition(binding.output), _definition(binding.outcome), _definition(binding.dispatch)))
    sources = set()
    snapshot = {'context':_digest(context), 'actions':actions,
                'code':None if binding is None else _code(binding, sources=sources)}
    graph = report.graph
    transitions = None
    if graph.complete and not graph.errors:
        hashes = {action.name:hashlib.sha256() for action in model.actions}
        for index, outcomes in enumerate(graph.out):
            for call in graph.calls:
                outcome = outcomes[call.index]
                observed = ((graph.states[outcome], graph.outputs.get((index, call.index))) if outcome >= 0 else
                            ('refusal', graph.outcome(index, call.index).reason))
                hashes[call.action.name].update(repr((graph.states[index], call.args, observed)).encode())
                hashes[call.action.name].update(b'\0')
        transitions = {name:value.hexdigest() for name, value in hashes.items()}
    snapshot['transitions'] = transitions
    previous = (baseline or {}).get('info', {}).get('incremental')
    operations, retained = None, []
    if (previous and previous.get('context') == snapshot['context'] and transitions is not None and
            previous.get('transitions') is not None and snapshot['code'] is not None and previous.get('code') is not None):
        operations = sorted(name for name in actions if previous['actions'].get(name) != actions[name] or
                            previous['code'].get(name) != snapshot['code'].get(name) or
                            previous['transitions'].get(name) != transitions[name])
        from ..native.inputs import footprint_evidence
        footprints = (baseline or {}).get('info', {}).get('native', {}).get('footprints', ())
        retained = [_inputs_beyond_code(row, sources) for row in footprints]
        if not retained or any(footprint_evidence(row).status != 'current' for row in retained):
            operations, retained = None, []
    return {'snapshot':snapshot, 'operations':operations,
            'retained_footprints':retained, 'retained_from':(baseline or {}).get('digest'),
            'walk_steps':steps if operations is None or operations else None, 'walk_seed':seed}


def baseline(root, digest):
    if digest is None:
        return None
    from .jobs import parts_dir, read_json
    return read_json(parts_dir(root) / (digest + '.json'))


def selected_tests(root):
    """Existing static imports select test files in the reverse dependency closure."""
    from ..map.common import DEFAULT_IGNORE, git_common_directory, matches_any
    from ..map.inventory import build_inventory, module_name, python_roots, resolve_import
    from .project import changed_files
    if git_common_directory(root) is None:
        return []
    changed = changed_files(root)
    if not changed:
        return []
    inv = build_inventory(Path(root), DEFAULT_IGNORE, with_bodies=False)
    dependencies = {path:set(targets) for path, targets in inv.file_deps.items()}
    missing = {path for path in changed if path.endswith('.py') and not (Path(root) / path).is_file()
               and not matches_any(path, DEFAULT_IGNORE)}
    if missing:
        # Current parsing still knows each import statement. Add the removed path
        # vocabulary to the existing resolver so its callers do not vanish too.
        paths = sorted(set(inv.py) | missing)
        roots = python_roots(paths)
        modules = {module_name(path, roots):path for path in paths}
        modules.update(inv.mod_to_path)
        lazy = {info.module:info.lazy_exports for info in inv.py.values() if info.lazy_exports}
        for path, info in inv.py.items():
            for imported in info.imports:
                target = resolve_import(imported, modules, lazy, importer=path, py_paths=paths,
                                        import_roots=inv.import_roots)
                if target and target != path:
                    dependencies.setdefault(path, set()).add(target)
    affected = set(changed)
    for path in changed:
        if Path(path).name == 'conftest.py':
            affected.update(test for test in inv.tests if Path(test).is_relative_to(Path(path).parent))
        elif path in {'pyproject.toml', 'pytest.ini', 'setup.cfg', 'tox.ini'}:
            affected.update(inv.tests)
    while True:
        callers = {path for path, deps in dependencies.items() if deps & affected}
        newer = affected | callers
        if newer == affected:
            break
        affected = newer
    return sorted(set(inv.tests) & affected)
