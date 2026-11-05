"""Actual loaded declarations and finite observations carried by the core part."""
from __future__ import annotations

import ast
import inspect
import itertools
import json
import textwrap
from pathlib import Path

from ..map.common import content_digest
from .history import definition_digest
from .model import State


def _key(value):
    return repr(value)


def symbolic(value, model):
    """Logical object slots, so IDs/declared order do not invent scope changes."""
    ids = {obj:f'<{kind}:{index}>' for kind, values in model.kinds.items() for index, obj in enumerate(values)}
    def visit(item):
        if isinstance(item, str):
            return ids.get(item, item)
        if isinstance(item, (list, tuple)):
            return tuple(visit(v) for v in item)
        if isinstance(item, dict):
            return tuple(sorted(((visit(k), visit(v)) for k, v in item.items()), key=repr))
        return item
    return visit(value)


def _definition(functions):
    try:
        return definition_digest('\n'.join(inspect.getsource(fn) for fn in functions if fn is not None))
    except (OSError, TypeError):
        return None


def _rule_action_identity(rule):
    return definition_digest(repr((rule.kind, rule.name, rule.action, rule.obj)))


def _rule_registrations(tree, rule):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call) and
            isinstance(node.func, ast.Attribute) and node.func.attr == rule.kind and
            len(node.args) == 3 and isinstance(node.args[0], ast.Constant) and
            node.args[0].value == rule.name and isinstance(node.args[1], ast.Constant) and
            isinstance(node.args[1].value, str) and isinstance(node.args[2], ast.Lambda)]


def closed_rule_evidence(rule, original, entry=None):
    """Authenticate a closed predicate and its original action, without execution."""
    from ..map.common import read_source
    original = {'definition':original} if isinstance(original, str) else original
    fn = rule.pred
    code = getattr(fn, '__code__', None)
    if (rule.kind not in {'after', 'only_when'} or code is None or code.co_names or code.co_freevars or
            fn.__defaults__ or fn.__kwdefaults__ or rule.obj is not None or
            _definition((fn,)) != original.get('definition')):
        return None
    try:
        tree = ast.parse(read_source(Path(code.co_filename)))
        candidates = [call for call in _rule_registrations(tree, rule)
                      if call.args[2].lineno == code.co_firstlineno]
        if len(candidates) != 1 or candidates[0].args[1].value != rule.action:
            return None
        node = candidates[0].args[2]
        compiled = next(value for value in compile(ast.Expression(node), code.co_filename, 'eval').co_consts
                        if inspect.iscode(value))
        if any(getattr(compiled, key) != getattr(code, key) for key in
               ('co_code', 'co_consts', 'co_names', 'co_varnames', 'co_argcount', 'co_kwonlyargcount', 'co_posonlyargcount')):
            return None
    except (OSError, TypeError, ValueError, SyntaxError, StopIteration):
        return None
    args = {arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
    unsafe = (ast.Call, ast.Attribute, ast.NamedExpr, ast.comprehension, ast.GeneratorExp, ast.Await, ast.Yield, ast.Lambda)
    if (node.args.defaults or node.args.kw_defaults or node.args.vararg is not None or node.args.kwarg is not None or
            any(isinstance(item, unsafe) for item in ast.walk(node.body)) or
            any(item.id not in args for item in ast.walk(node.body) if isinstance(item, ast.Name))):
        return None
    proof = dict(action=rule.action, identity=_rule_action_identity(rule))
    captured = (original.get('dependencies') or {}).get('rule-action')
    if captured is not None:
        return dict(proof, basis='recorded-rule-action') if captured == proof['identity'] else None
    if 'action' in original:                      # already authenticated frozen regression
        return dict(proof, basis='frozen-rule-action') if original['action'] == rule.action else None
    try:
        inline = _rule_registrations(ast.parse(textwrap.dedent(inspect.getsource(fn))), rule)
    except (OSError, TypeError, SyntaxError):
        inline = []
    if len(inline) == 1 and inline[0].args[1].value == rule.action:
        return dict(proof, basis='legacy-complete-registration')
    capsule = (entry or {}).get('detail', {}).get('original_model_source', {})
    if not isinstance(capsule, dict):
        return None
    path, text = capsule.get('path'), capsule.get('text')
    expected = (original.get('dependencies') or {}).get(path) if isinstance(path, str) else None
    if (path != '.flowguard/flow/' + str((entry or {}).get('model')) + '.py' or
            not isinstance(text, str) or expected is None or
            content_digest(Path(path), data=text.encode('utf-8'), source_only=True) != expected):
        return None
    try:
        old = _rule_registrations(ast.parse(text), rule)
    except SyntaxError:
        return None
    if (len(old) != 1 or old[0].args[1].value != rule.action or
            ast.dump(old[0].args[2], include_attributes=False) != ast.dump(node, include_attributes=False)):
        return None
    return dict(proof, basis='authenticated-original-source', source=dict(path=path, sha256=expected))


def closed_rule_definition(rule, original, entry=None):
    return closed_rule_evidence(rule, original, entry) is not None


def _predicate_terms(node, model):
    """Actual field/setting names and their declared values used by a predicate."""
    names = {n.slice.value for n in ast.walk(node) if isinstance(n, ast.Subscript)
             and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)}
    terms = set(names)
    terms.update(item.value for comparison in ast.walk(node) if isinstance(comparison, ast.Compare)
                 for item in ast.walk(comparison) if isinstance(item, ast.Constant) and isinstance(item.value, str))
    for field in model.fields:
        if field.family in names:
            terms.update(value for value in field.domain if isinstance(value, str))
    for name, setting in model.setting_info.items():
        if name in names and isinstance(setting.value, str):
            terms.add(setting.value)
    return sorted(term for term in terms if term.strip())


def input_evidence(root, reads):
    """Computation-side bytes and file mode, captured before model execution."""
    import os
    import stat
    result = {}
    for rel in sorted(set(reads)):
        path = Path(root) / rel
        if not path.exists() and not path.is_symlink():
            result[rel] = None
        elif path.is_symlink():
            from ..map.common import sha256_bytes
            result[rel] = dict(mode='120000', sha256=sha256_bytes(os.readlink(path).encode()))
        else:
            # Git ignores Windows' synthetic executable bits, as does its index.
            mode = '100755' if os.name != 'nt' and path.stat().st_mode & stat.S_IXUSR else '100644'
            result[rel] = dict(mode=mode, sha256=content_digest(path, source_only=True))
    return result


def _guard_rows(model, dependencies, max_cases, *, finite_comparison=True):
    """Guard source sites, with finite predicate results when safely evaluable.

    This uses the actual need expression and globals. A statement-dependent guard
    remains unknown; the action is not reexecuted merely to manufacture a relation.
    """
    rows, limits = [], []
    fields = [f for f in model.fields]
    size = 1
    for field in fields:
        size *= len(field.domain)
    for action in model.actions:
        try:
            tree = ast.parse(textwrap.dedent(inspect.getsource(action.fn)))
        except (OSError, TypeError, SyntaxError):
            continue
        guards = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and
                  isinstance(node.func, ast.Name) and node.func.id == 'need' and node.args]
        for number, node in enumerate(guards):
            source_node = next((kw.value for kw in node.keywords if kw.arg == 'source'), None)
            source = source_node.value if isinstance(source_node, ast.Constant) else None
            if not isinstance(source, str):
                continue
            cases = None
            # Enumerating declared values is bounded by the model's existing
            # exploration budget; absence of this comparison is explicit unknown.
            combinations = size
            for domain in action.domains:
                combinations *= len(domain)
            if finite_comparison and combinations <= max_cases:
                expression = compile(ast.Expression(node.args[0]), action.fn.__code__.co_filename, 'eval')
                candidate = {}
                try:
                    for values in itertools.product(*(field.domain for field in fields)):
                        state = State((field.key, value) for field, value in zip(fields, values))
                        for args in itertools.product(*action.domains):
                            value = eval(expression, action.fn.__globals__,
                                         {next(iter(inspect.signature(action.fn).parameters)): state, **dict(zip(action.params, args))})
                            if type(value) is not bool:
                                raise TypeError('guard predicate did not return bool')
                            candidate[_key((symbolic(state, model), symbolic(args, model)))] = value
                except (NameError, TypeError, KeyError, IndexError, AttributeError, ValueError) as error:
                    limits.append(f'guard:{action.name}:{number}: finite comparison unknown: {type(error).__name__}: {error}')
                    candidate = None
                cases = candidate or None
            elif finite_comparison:
                limits.append(f'guard:{action.name}:{number}: declared combinations exceed exploration budget {max_cases}')
            rows.append(dict(id=f'guard:{action.name}:{number}', kind='guard', sources=[source],
                             definition=definition_digest(ast.dump(node.args[0], include_attributes=False)),
                             cases=cases, dependencies=dependencies, terms=_predicate_terms(node.args[0], model)))
    return rows, limits


def construction_starts(model):
    """Constructor/restoration inputs are scope; the model's output is an oracle."""
    import base64
    from ..map.common import sha256_bytes
    binding = getattr(model, 'adapter_binding', None)
    if binding is None:
        return ['initial:' + _key(symbolic({field.key:field.init for field in model.fields}, model))], {}
    start = dict(binding.start)
    start.setdefault('seed', 0)
    if 'files' in start:
        start['files'] = {name:dict(bytes=len(base64.b64decode(data)), sha256=sha256_bytes(base64.b64decode(data)))
                          for name, data in start['files'].items()}
    selected_world = binding.start.get('world')
    construction = dict(system=binding.spec.get('system'), ui=binding.spec.get('ui'),
                        settings=binding.spec.get('settings'), shipped=binding.spec.get('shipped', {}),
                        start=start, world_sizes=binding.spec.get('worlds', {}).get(selected_world))
    identity = definition_digest(repr(symbolic(construction, model)))
    initial = 'construct:' + str(binding.spec.get('system')) + ':' + identity
    starts, evidence = [initial], {initial:construction}
    if binding.prefix:
        restoration = dict(construction=identity, prefix=binding.prefix)
        restored = 'saved-prefix:' + ','.join(str(call.get('name', call.get('construct', '?'))) for call in binding.prefix)
        restored += ':' + definition_digest(repr(symbolic(restoration, model)))
        starts.append(restored)
        evidence[restored] = restoration
    return starts, evidence


def model_descriptor(loaded, report, digest, inputs, *, finite_comparison=True):
    """Keep declarations; evaluate finite relations when a conflict needs comparison."""
    model, graph = loaded.model, report.graph
    dependencies = {path: data['sha256'] for path, data in inputs.items() if data is not None and path in loaded.reads}
    coverage = {'anchors': list(model.covers) or [f'model:{model.id}']}
    for field in model.fields:
        coverage.setdefault('field:' + field.family, [])
        coverage['field:' + field.family] += [repr(symbolic(v, model)) for v in field.domain]
    for key, values in (('actions', [a.name for a in model.actions]),
                        ('options', [o.name for o in model.options]),
                        ('rules', [f'{r.kind}:{r.name}' for r in model.rules])):
        if values:
            coverage[key] = values
    for name, setting in model.setting_info.items():
        coverage['setting:' + name] = [f'{setting.origin}:{setting.value!r}']
        if setting.origin == 'code':
            coverage['setting:' + name].append(f'code:{setting.code_value!r}')
    coverage = {key: sorted(set(values)) for key, values in sorted(coverage.items())}
    starts, start_inputs = construction_starts(model)
    scope = dict(model=model.id, members=[model.id], bounds={kind:len(ids) for kind, ids in model.kinds.items()},
                 starts=starts, coverage=coverage)
    obligations, limits = _guard_rows(model, dependencies, graph.max_states,
                                     finite_comparison=finite_comparison)
    if not finite_comparison:
        limits.append('finite comparison not evaluated for clean declaration')
    for field in model.fields:
        sources = sorted({s for s in [field.source, *field.value_sources.values()] if s})
        if sources:
            text = repr(symbolic((field.family, field.domain, field.init), model))
            obligations.append(dict(id='field:' + _key(symbolic(field.key, model)), kind='field', sources=sources,
                                    definition=definition_digest(text), dependencies=dependencies,
                                    terms=sorted({field.family, *(v for v in field.domain if isinstance(v, str))}),
                                    cases={repr(symbolic(value, model)):True for value in field.domain}
                                          if finite_comparison else None))
    for action in model.actions:
        if action.source:
            text = repr(symbolic((action.name, action.params, action.domains), model))
            identity = definition_digest(text)
            obligations.append(dict(id='operation:' + action.name, kind='operation', sources=[action.source],
                                    definition=identity, dependencies={'declaration':identity},
                                    terms=[action.name],
                                    cases={_key(symbolic(args, model)):True for args in itertools.product(*action.domains)}
                                          if finite_comparison else None))
    for family, values in model.terminals.items():
        source = model.terminal_sources.get(family)
        if source:
            identity = definition_digest(repr(symbolic((family, values), model)))
            obligations.append(dict(id='ending:' + family, kind='ending', sources=[source],
                definition=identity, dependencies={'declaration':identity},
                terms=sorted({family, *(v for v in values if isinstance(v, str))}),
                cases={repr(symbolic(v, model)):True for v in values} if finite_comparison else None))
    for name, setting in model.setting_info.items():
        if setting.source:
            identity = definition_digest(repr(symbolic((name, setting.value, setting.origin), model)))
            obligations.append(dict(id='setting:' + name, kind='setting', sources=[setting.source],
                definition=identity, dependencies={'declaration':identity}, terms=[name],
                cases={repr(symbolic(setting.value, model)):True} if finite_comparison else None))
    for rule in model.rules:
        if not rule.source:
            continue
        cases = None
        size = 1
        for field in model.fields:
            size *= len(field.domain)
        if finite_comparison and rule.kind in {'always', 'reach', 'progress'} and size <= graph.max_states:
            try:
                cases = {}
                for values in itertools.product(*(field.domain for field in model.fields)):
                    state = State(zip(graph.keys, values))
                    args = (state,) if rule.obj is None else (state, rule.obj)
                    key = _key(symbolic(state, model))
                    if rule.kind == 'progress':
                        cases['when:' + key] = not bool(rule.when(*args))
                        cases['goal:' + key] = bool(rule.goal(*args))
                    else:
                        cases[key] = bool(rule.pred(*args))
            except (NameError, TypeError, KeyError, IndexError, AttributeError, ValueError) as error:
                limits.append(f'rule:{rule.name}: finite comparison unknown: {type(error).__name__}: {error}')
                cases = None
        terms = {rule.name}
        for function in (rule.pred, rule.when, rule.goal):
            if function is not None:
                try:
                    terms.update(_predicate_terms(ast.parse(textwrap.dedent(inspect.getsource(function))), model))
                except (OSError, TypeError, SyntaxError):
                    pass
        obligations.append(dict(id=f'rule:{rule.kind}:{rule.name}', kind=rule.kind, sources=[rule.source],
                                definition=_definition((rule.pred, rule.when, rule.goal)),
                                dependencies=({**dependencies, 'rule-action':_rule_action_identity(rule)}
                                              if rule.kind in {'after', 'only_when'} else dependencies),
                                cases=cases or None, terms=sorted(terms)))
    from ..map.inventory import coverage_kind
    boundary = coverage_kind(model.root, model.covers) if model.root is not None else 'unknown'
    return dict(scope=scope, obligations=obligations, inputs=inputs, receipt=digest, comparison_limits=limits,
                start_inputs=start_inputs, boundary=boundary)


def finding_terms(finding, model):
    """Names from the actual computed item, rather than topic/word similarity."""
    detail = finding.detail
    terms = []
    if detail.get('key'):
        terms.append(detail['key'].partition('[')[0])
    if detail.get('value'):
        try:
            value = ast.literal_eval(detail['value'])
        except (ValueError, SyntaxError):
            value = None
        if isinstance(value, str):
            terms.append(value)
    if detail.get('name'):
        terms.append(detail['name'])
    if detail.get('option'):
        terms.append(detail['option'])
    if detail.get('rule') and detail.get('item') == 'reach':
        terms.append(detail['rule'])
    if detail.get('item') == 'action':
        terms.append(finding.subject.removeprefix('action '))
    for step in [*(finding.path or ()), *(row.get('call', '') for row in detail.get('refused', []))]:
        name = step.partition('(')[0]
        if any(action.name == name for action in model.actions):
            terms.append(name)
    return sorted(set(terms))


def requested_rule_conflicts(report):
    """Combine genuinely incompatible sourced always-rules, preserving members."""
    from .decisions import rule_contradiction
    from .checks import CONFLICT, make_finding
    from .project import _request_problem
    from ..map.requests import REQUEST_DIR, _metadata
    graph = report.graph
    live = {}
    for rule in graph.model.rules:
        if rule.kind != 'always' or not rule.source or graph.model.root is None:
            continue
        if rule.source not in live:
            live[rule.source] = (_request_problem(graph.model.root, rule.source) is None and
                                 _metadata(graph.model.root / REQUEST_DIR / (rule.source + '.json'), rule.source)['kind'] == 'request')
    by_name = {rule.name:rule for rule in graph.model.rules if rule.kind == 'always' and live.get(rule.source)}
    proofs, findings, grouped = {}, [], set()
    for a, b in itertools.combinations(sorted(by_name), 2):
        if by_name[a].source == by_name[b].source:
            continue
        proof = rule_contradiction(graph, (a, b), required=False)
        if proof is None:
            continue
        subject = a + ' / ' + b
        members = [f.to_json() for f in report.findings if f.kind == 'BROKEN' and f.detail.get('name') in {a, b}]
        finding = make_finding('RULE CONTRADICTION', CONFLICT, graph.model.id or graph.model.name, subject,
                               f'requested rules {a!r} and {b!r} cannot both hold in the declared finite scope',
                               sources=proof.sources, detail={'subject_terms':[a,b], 'members':members})
        findings.append(finding)
        proofs[finding.id] = proof.to_dict()
        grouped.update((a,b))
    originals = [f for f in report.findings if not (f.kind == 'BROKEN' and f.detail.get('name') in grouped)]
    return originals + findings, proofs
