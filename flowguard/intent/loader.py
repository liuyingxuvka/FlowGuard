"""Read declarations once; report rejected intent as a failing pytest collection item."""
from __future__ import annotations

import ast
import copy
from enum import Enum
import importlib.util
from pathlib import Path
import sys
import traceback

from . import api
from .api import Distinct, IntentError, Rule, States, StructureRule
from .flow import Flow, Read, Relation, _UNSET
from .config import intent_files, load_config, setup_path
from .imports import prepare, source_spec
from .sources import parse as parse_source
from ..map.common import sha256_bytes


LITERAL_CALLS = {'D', 'Decimal', 'date', 'datetime', 'timedelta', 'Refused'}


def api_aliases(tree):
    """Resolve spellings of the one SDK API, including ordinary Python import aliases."""
    aliases = {}
    modules = {'flowguard.intent', 'flowguard.intent.api'}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in modules:
            for name in node.names:
                if name.name == '*':
                    aliases.update({key: key for key in ('rule', 'row', 'distinct', 'states', 'structure_rule', 'flow', 'Node', 'Read', 'Relation', 'Transition')})
                else:
                    aliases[name.asname or name.name] = name.name
        elif isinstance(node, ast.ImportFrom) and node.module == 'flowguard':
            for name in node.names:
                if name.name == 'intent':
                    aliases[name.asname or name.name] = '@module'
        elif isinstance(node, ast.Import):
            for name in node.names:
                if name.name in modules:
                    aliases[name.asname or name.name] = '@module'
    for node in tree.body:
        if isinstance(node, ast.Assign):
            name = api_call_name(node.value, aliases, function=True)
            if name:
                aliases.update({target.id: name for target in node.targets if isinstance(target, ast.Name)})
    return aliases


def api_call_name(node, aliases, *, function=False):
    expression = node if function else node.func
    if isinstance(expression, ast.Name):
        return aliases.get(expression.id, '')
    if isinstance(expression, ast.Attribute):
        if aliases.get(ast.unparse(expression.value)) == '@module':
            return expression.attr
    return ''


# flowguard: sensor ROW_LITERAL(node: expression) -> allowed: bool calibrated_by=tests/test_anchor_self_rules.py::test_expression_anchor_case[direct-1]
def is_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float, str, bool, type(None)))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return isinstance(node.operand, ast.Constant) and type(node.operand.value) in (int, float)
    if isinstance(node, (ast.Tuple, ast.List)):
        return all(is_literal(value) for value in node.elts)
    if isinstance(node, ast.Call):
        name = node.func.id if isinstance(node.func, ast.Name) else ''
        args = node.args[1:] if name == 'Refused' and node.args and isinstance(node.args[0], ast.Name) else node.args
        return name in LITERAL_CALLS and all(is_literal(value) for value in args) and all(key.arg and is_literal(key.value) for key in node.keywords)
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)


# flowguard: sensor ROW_PROBLEMS(tree: source, rel: path) -> problems: list[dict] calibrated_by=tests/test_anchor_self_rules.py::test_program_anchor_case[direct-1]
def literal_problems(tree: ast.AST, rel: str) -> list[dict]:
    problems = []
    aliases = api_aliases(tree)
    rule_names = {function.name for function in tree.body
                  if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and any(isinstance(d, ast.Call) and api_call_name(d, aliases) == 'rule'
                          for d in function.decorator_list)}
    rebuild = 'call adapters were removed; rebuild the original test using source anchors and Flow relations'
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {'flowguard.intent', 'flowguard.intent.api'}:
            if any(name.name == 'Home' for name in node.names):
                problems.append(dict(file=rel, line=node.lineno, msg='Home ' + rebuild))
        if (isinstance(node, ast.Attribute) and node.attr == 'home'
                and isinstance(node.value, ast.Name) and node.value.id in rule_names):
            problems.append(dict(file=rel, line=node.lineno, msg='Rule.home() ' + rebuild))
        if not isinstance(node, ast.Call) or api_call_name(node, aliases) != 'row':
            continue
        for key in node.keywords:
            valid = (isinstance(key.value, ast.Constant) and isinstance(key.value.value, (str, type(None)))) if key.arg in {'why', 'retired'} else is_literal(key.value)
            if key.arg is None or not valid:
                problems.append(dict(file=rel, line=node.lineno, msg=f'row {key.arg or "**mapping"} must be a literal'))
    return problems


def item_names(identifier, homes=(), kind='rule'):
    """The one pytest item naming scheme, also used by static failure diagnostics."""
    if kind != 'rule':
        return [f'{identifier}[{kind}]']
    return ([f'{identifier}[rules]']
            + [f'{identifier}[{target.replace(":", ".")}:{part}]' for target in homes for part in ('rows', 'cells', 'live')])


class Model:
    def __init__(self, cfg):
        self.cfg = cfg
        self.rules, self.states, self.structures, self.flows, self.anchor_distincts = {}, {}, {}, {}, {}
        self.anchor_index = None
        self.scenario_issues = {}
        self.distincts, self.errors, self.files = [], [], []
        self.file_of, self.kinds, self.superseded_by = {}, {}, {}
        self.intent_lines = 0
        self.literal_rows = set()

    def key(self, key):
        return [r for r in self.rules.values() if r.decides == key]

    def keys(self):
        return sorted({r.decides for r in self.rules.values()})

    def active(self, key):
        return [r for r in self.key(key) if r.id not in self.superseded_by]

    def overrides(self, winner, loser):
        todo, seen = list(self.rules[winner].overrides), set()
        while todo:
            other = todo.pop()
            if other == loser:
                return True
            if other in self.rules and other not in seen:
                seen.add(other)
                todo.extend(self.rules[other].overrides)
        return False

    def distinct_pair(self, first, second):
        return next((d for d in self.distincts if {d.a, d.b} == {first, second}), None)

    def rules_in(self, rel):
        return [r for r in self.rules.values() if self.file_of[r.id] == rel]

    def items_of(self, rule):
        return item_names(rule.id, [h.target for h in rule.homes])

    def declared_items(self):
        result = [f'{rel}::load' for rel in self.files if any(e['file'] == rel for e in self.errors)]
        result += [f'{self.file_of[r.id]}::{name}' for r in self.rules.values() for name in self.items_of(r)]
        result += [f'{self.file_of[r.id]}::{name}' for items, part in ((self.states, 'states'), (self.structures, 'structure'), (self.flows, 'flow'), (self.anchor_distincts, 'anchor_distinct'))
                   for r in items.values() for name in item_names(r.id, kind=part)]
        return sorted(result)


def _error_line(error, path):
    frames = traceback.extract_tb(error.__traceback__)
    return next((f.lineno for f in reversed(frames) if Path(f.filename) == path), 0)


def distinct_identifier(file, a, b):
    return 'DISTINCT_' + sha256_bytes((file + '\0' + '\0'.join(sorted((a, b)))).encode())[:16]


def _classify_distincts(model):
    for declaration in model.distincts:
        sides = []
        for explicit_rule, name in zip(declaration.rule_sides, (declaration.a, declaration.b)):
            rule = name in model.rules
            anchors = [anchor for anchor in model.anchor_index.entries
                       if anchor.kind == 'sensor' and name in (anchor.name, anchor.target)] if model.anchor_index else []
            sides.append('ambiguous' if rule and anchors and not explicit_rule else 'rule' if rule
                         else 'anchor' if anchors else 'unknown')
        if sides == ['anchor', 'anchor']:
            declaration.binding_kind = 'anchor'
            declaration.id = distinct_identifier(declaration.file, declaration.a, declaration.b)
            if declaration.id in model.file_of:
                model.errors.append(dict(file=declaration.file, line=declaration.line, msg='duplicate distinct declaration'))
                continue
            model.anchor_distincts[declaration.id] = declaration
            model.file_of[declaration.id] = declaration.file
        elif sides != ['rule', 'rule']:
            model.errors.append(dict(file=declaration.file, line=declaration.line,
                                     msg='distinct must name two unambiguous rules or two source anchors; old rule/node adapters were removed: rebuild the original test using source anchors and Flow relations; use module:qual for an anchor'))
            declaration.binding_kind = 'invalid'


class ScenarioBinding(api._AnchorBinding):
    """A test's logical inputs and a fixed real reading, never a call adapter.

    The production anchor remains the liveness/footprint target. The scenario
    anchor identifies the ordinary test function whose arguments the existing
    execution backend may change. The Flow owns every data projection.
    """
    def __init__(self, rule, flow, scenario, anchor, field_map, testnode, relation_indices=(),
                 actual_anchors=(), measurement_anchors=(), anchor_index=None, argument_plan=None):
        super().__init__(rule, anchor, equivalent=rule.equivalent)
        self.flow, self.scenario = flow, scenario
        self.field_map, self.testnode = dict(field_map), testnode
        self.observed_rule = rule.id
        self.relation_indices = tuple(relation_indices)
        self.actual_anchors = tuple(actual_anchors) or (anchor,)
        self.measurement_anchors = tuple(measurement_anchors) or self.actual_anchors
        self.anchor_index = anchor_index
        self.observed_fields = tuple(rule.fields)
        self.argument_plan = argument_plan or dict(fields=dict(field_map), children={})

    @property
    def actual_targets(self):
        return tuple(anchor.target for anchor in self.actual_anchors)

    @property
    def targets(self):
        return tuple(anchor.target for anchor in self.measurement_anchors)


def _bind_scenarios(model):
    """Derive bindings from the four-element model, without another registry."""
    index = model.anchor_index
    for flow in model.flows.values():
        nodes = {node.name: node for node in flow.nodes}
        if not any(node.name in flow.starts and node.phase == 'call'
                   and any(anchor.source_role == 'test' for anchor in index.named(node.reference)) for node in flow.nodes):
            continue  # Production graphs check readings; ordinary test-entry graphs drive scenarios.
        groups = {}
        def unbound(identifier, reason):
            model.scenario_issues.setdefault(identifier, []).append(f'{flow.id}: {reason}')
        def plain_argument(read):
            return (read.field.startswith('arg.') and len(read.field.split('.')) == 2
                    and read.view == '' and read.equals is _UNSET and read.occurrence is None)
        def same_read(left, right):
            return (isinstance(left, Read) and isinstance(right, Read)
                    and (left.node, left.field, left.view, left.occurrence) == (right.node, right.field, right.view, right.occurrence)
                    and (left.equals is _UNSET and right.equals is _UNSET
                         or type(left.equals) is type(right.equals) and left.equals == right.equals))
        def argument_plan(rule, relation, visiting=(), owner=flow):
            if rule.id in visiting:
                raise ValueError('scenario witness mapping contains a rule cycle')
            if set(relation.inputs) != set(rule.fields) or not all(isinstance(read, Read) for read in relation.inputs.values()):
                raise ValueError('scenario inputs must bind every original rule field')
            local_nodes = {node.name: node for node in owner.nodes}
            entries, fields, children = set(), {}, {}
            for name, read in relation.inputs.items():
                if plain_argument(read):
                    if read.node not in local_nodes:
                        raise ValueError('scenario argument node is absent')
                    entries.add(local_nodes[read.node].reference)
                    fields[name] = read.field[4:]
                    continue
                lower_node = local_nodes.get(read.node)
                child_id = getattr(lower_node.model, 'id', lower_node.model) if lower_node else None
                from .flow import _registered_flow, _flow_export, Unverified
                try:
                    child_flow = _registered_flow(lower_node.model, model.flows) if lower_node else None
                    exported = _flow_export(child_flow, model.rules) if child_flow else None
                except Unverified as error:
                    raise ValueError(str(error)) from error
                if exported:
                    child_id = exported[0].id
                    if (lower_node.reference, lower_node.phase, read.field, read.view, read.equals) != (
                            exported[2].reference, exported[2].phase, exported[1].actual.field,
                            exported[1].actual.view, exported[1].actual.equals):
                        raise ValueError('parent lower reading must preserve the explicit child export projection')
                child = model.rules.get(child_id)
                if child is None or child_id not in rule.uses:
                    raise ValueError('a non-argument input needs an explicit lower Rule node and uses=')
                sources = [other for other in owner.relations if isinstance(other, Relation)
                           and getattr(other.rule, 'id', other.rule) == child_id and same_read(other.actual, read)]
                nested_owner = owner
                if not sources and exported:
                    sources, nested_owner = [exported[1]], child_flow
                if len(sources) != 1 or child_id in children:
                    raise ValueError('the lower outcome needs one explicit original-input relation')
                entry, nested = argument_plan(child, sources[0], (*visiting, rule.id), nested_owner)
                entries.add(entry)
                children[child_id] = dict(field=name, plan=nested)
            if len(entries) != 1:
                raise ValueError('scenario arguments need one explicit test entry; mixed scopes are not guessed')
            return next(iter(entries)), dict(fields=fields, children=children)
        for position, relation in enumerate(flow.relations):
            if not isinstance(relation, Relation):
                continue  # Flow validation reports invalid declarations.
            identifier = getattr(relation.rule, 'id', relation.rule)
            rule = model.rules.get(identifier)
            if rule is None or relation.actual is None:
                continue  # A bool invariant does not provide a decision witness.
            if not isinstance(relation.actual, Read):
                unbound(identifier, 'a scenario outcome needs one explicit actual Read'); continue
            try:
                case_name, plan = argument_plan(rule, relation)
            except ValueError as error:
                unbound(identifier, str(error)); continue
            case_nodes = [node for node in flow.nodes if node.reference == case_name and node.phase == 'call']
            case_node = case_nodes[0] if len(case_nodes) == 1 else None
            measured_node = nodes.get(relation.actual.node)
            if case_node is None or measured_node is None:
                unbound(identifier, 'scenario input or measured node is absent'); continue
            if case_node.name not in flow.starts or case_node.phase != 'call':
                unbound(identifier, 'scenario logical inputs must come from a declared call entry'); continue
            scenarios = index.named(case_node.reference, 'event')
            if len(scenarios) != 1 or scenarios[0].source_role != 'test':
                unbound(identifier, 'scenario entry must name one real ordinary-test event anchor'); continue
            scenario = scenarios[0]
            field_map = plan['fields']
            def parameters(part):
                return set(part['fields'].values()) | set().union(*(parameters(child['plan']) for child in part['children'].values()))
            if not parameters(plan) <= {parameter.name for parameter in scenario.parameters}:
                unbound(identifier, 'scenario field names do not match the actual test parameters'); continue
            actual = [anchor for anchor in index.named(measured_node.reference)
                      if anchor.source_role == 'production' and anchor.kind in {'sensor', 'event'}]
            if not actual:
                unbound(identifier, 'actual reading has no production anchor'); continue
            key = identifier, scenario.target
            group = groups.setdefault(key, dict(rule=rule, scenario=scenario, field_map=field_map,
                                               plan=plan, actual={}, actual_nodes=set(), indices=[], ambiguous=False))
            if group['plan'] != plan:
                unbound(identifier, 'the same scenario has conflicting logical argument mappings')
                group['ambiguous'] = True
            group['actual'].update((anchor.target, anchor) for anchor in actual)
            group['actual_nodes'].add(measured_node.name)
            group['indices'].append(position)
        for group in groups.values():
            if group['ambiguous']:
                continue
            rule, scenario = group['rule'], group['scenario']
            actual = list(group['actual'].values())
            tests = {anchor.calibrated_by for anchor in actual if anchor.calibrated_by}
            testnode = scenario.calibrated_by or (next(iter(tests)) if len(tests) == 1 else '')
            if not testnode:
                unbound(rule.id, 'calibrated_by must select one real scenario test for all outcome branches'); continue
            measured = {}
            needed = set(group['actual_nodes'])
            while True:
                more = {edge[0] for edge in flow.edges if len(edge) == 2 and edge[1] in needed}
                if more <= needed:
                    break
                needed.update(more)
            for node in flow.nodes:
                if node.name in needed and (node.model is None or node.name in group['actual_nodes']):
                    measured.update((anchor.target, anchor) for anchor in index.named(node.reference)
                                    if anchor.source_role == 'production' and anchor.kind in {'sensor', 'event'})
            primary = next((anchor for target, anchor in measured.items() if target in group['actual']), actual[0])
            existing = next((home for home in rule.homes if home.target == primary.target), None)
            if existing is not None:
                if isinstance(existing, ScenarioBinding) and (existing.flow.id, existing.scenario.target) != (flow.id, scenario.target):
                    unbound(rule.id, 'several scenarios share one production target; their contract items are not conflated')
                continue  # Keep existing checks until a measured migration replaces them.
            rule.homes.append(ScenarioBinding(rule, flow, scenario, primary, group['field_map'], testnode,
                                             group['indices'], actual, tuple(measured.values()), index, group['plan']))


def load(cfg=None, root=None, *, anchor_index=None, map_path=None):
    cfg = cfg or load_config(root)
    setup_path(cfg)
    prepare(cfg.root)
    model = Model(cfg)
    for path in intent_files(cfg):
        rel = cfg.rel(path)
        model.files.append(rel)
        text = path.read_text(encoding='utf-8-sig')
        model.intent_lines += len(text.splitlines())
        try:
            tree = ast.parse(text, str(path))
        except SyntaxError as error:
            model.errors.append(dict(file=rel, line=error.lineno or 0, msg=str(error)))
            continue
        errors = literal_problems(tree, rel)
        if errors:
            model.errors.extend(errors)
            continue
        aliases = api_aliases(tree)
        model.literal_rows.update((str(path), n.lineno, n.end_lineno, n.col_offset, n.end_col_offset)
                                  for n in ast.walk(tree) if isinstance(n, ast.Call) and api_call_name(n, aliases) == 'row')
        api.DECLARED.clear()
        # Names are private to a project, including a pytest host checking temporary projects.
        name = '_flowguard_intent_' + sha256_bytes(str(path).encode())
        spec = source_spec(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException as error:
            outcome = any(base.__module__ == '_pytest.outcomes' and base.__name__ == 'OutcomeException'
                          for base in type(error).__mro__)
            if not isinstance(error, Exception) and not outcome:
                raise
            model.errors.append(dict(file=rel, line=_error_line(error, path), msg=f'{type(error).__name__}: {error}'))
            continue
        for item in api.DECLARED:
            if isinstance(item, Distinct):
                item.file = rel
                model.distincts.append(item)
                continue
            if item.id in model.file_of:
                model.errors.append(dict(file=rel, line=item.line, msg=f'duplicate declaration {item.id}'))
                continue
            owner = (model.rules if isinstance(item, Rule) else model.states if isinstance(item, States)
                     else model.flows if isinstance(item, Flow) else model.structures)
            owner[item.id], model.file_of[item.id] = item, rel
        api.DECLARED.clear()
    needs_anchors = (model.flows or any(rule.anchors for rule in model.rules.values())
                     or any(side not in model.rules for item in model.distincts for side in (item.a, item.b)))
    if needs_anchors:
        from contextlib import closing
        from ..structure import build
        from .anchors import collect
        if anchor_index is not None:
            model.anchor_index = anchor_index
        else:
            with closing(build(cfg.root, roots=cfg.roots, store_path=map_path)) as graph:
                model.anchor_index = collect(graph)
        for rule in model.rules.values():
            for name in rule.anchors:
                candidates = model.anchor_index.named(name, 'sensor')
                rule.homes.extend(api._AnchorBinding(rule, anchor, equivalent=rule.equivalent) for anchor in candidates)
                if not candidates:
                    rule.homes.append(api._AnchorBinding(rule, None, name=name))
        _bind_scenarios(model)
    _classify_distincts(model)
    _validate(model)
    return model


def _validate(model):
    from .cells import kind_of

    def refuse(item, message, line=None):
        model.errors.append(dict(file=model.file_of[item.id], line=line or item.line, msg=f'{item.id}: {message}'))

    for item in [*model.rules.values(), *model.states.values(), *model.structures.values(), *model.flows.values()]:
        try:
            parse_source(item.source)
        except IntentError as error:
            refuse(item, str(error))
    for rule in model.rules.values():
        for name, spec in rule.fields.items():
            try:
                kind = kind_of(spec)
                prior = model.kinds.setdefault(rule.decides, {}).setdefault(name, kind)
                if prior != kind:
                    refuse(rule, f'field {name} has incompatible types under one decides key')
            except ValueError as error:
                refuse(rule, f'field {name}: {error}')
        for other in rule.overrides + rule.supersedes + rule.uses:
            if other not in model.rules:
                refuse(rule, f'unknown rule {other}')
            elif other in rule.overrides + rule.supersedes and model.rules[other].decides != rule.decides:
                refuse(rule, f'{other} has a different decides key')
        for old in rule.supersedes:
            if old in model.rules:
                if old in model.superseded_by:
                    refuse(rule, f'{old} is already superseded by {model.superseded_by[old]}')
                model.superseded_by[old] = rule.id
        for row in rule.all_rows:
            if row.origin not in model.literal_rows:
                refuse(rule, 'row must come from a verified literal row(...) call in the intent files', row.line)
                continue
            if set(row.inputs) != set(rule.fields):
                refuse(rule, 'row fields do not match the declared fields', row.line)
                continue
            for name, value in row.inputs.items():
                kind = model.kinds.get(rule.decides, {}).get(name)
                if kind and not kind.accepts(value):
                    refuse(rule, f'row {name}={value!r} is outside its declared type', row.line)
            if row.retired is None:
                try:
                    if rule.eval(row.inputs) is None:
                        refuse(rule, 'row is outside the predicate domain', row.line)
                except Exception as error:
                    refuse(rule, f'predicate raises {type(error).__name__}: {error}', row.line)
    for relation in ('overrides', 'supersedes', 'uses'):
        for rule in model.rules.values():
            todo, seen = list(getattr(rule, relation)), set()
            while todo:
                other = todo.pop()
                if other == rule.id:
                    refuse(rule, f'{relation} cycle')
                    break
                if other in model.rules and other not in seen:
                    seen.add(other)
                    todo.extend(getattr(model.rules[other], relation))
    for rule in model.rules.values():
        for old in rule.supersedes:
            if old not in model.rules:
                continue
            for home in model.rules[old].homes:
                if not any(h.target == home.target for h in rule.homes):
                    if isinstance(home, ScenarioBinding):
                        inherited = copy.copy(home)
                        inherited.rule = rule
                        rule.homes.append(inherited)
                    elif isinstance(home, api._AnchorBinding):
                        rule.homes.append(api._AnchorBinding(rule, home.anchor, name=home.name, equivalent=home.equivalent))
            for relation in list(model.distincts):
                if old not in (relation.a, relation.b):
                    continue
                first = rule.id if relation.a == old else relation.a
                second = rule.id if relation.b == old else relation.b
                if any({existing.a, existing.b} == {first, second} for existing in model.distincts):
                    continue
                inherited = copy.copy(relation)
                inherited.a, inherited.b = first, second
                model.distincts.append(inherited)
        used = []
        for other in rule.uses:
            seen = set()
            while other in model.superseded_by and other not in seen:
                seen.add(other)
                other = model.superseded_by[other]
            used.append(other)
        rule.uses = tuple(used)
    # Distinct identities are resolved once by _classify_distincts. There is no
    # rule-to-anonymous-node invocation route or borrowed call adapter.
