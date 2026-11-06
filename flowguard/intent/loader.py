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
from .config import intent_files, load_config, setup_path
from .imports import prepare, source_spec
from .sources import parse as parse_source
from flowguard.map.common import sha256_bytes


LITERAL_CALLS = {'D', 'Decimal', 'date', 'datetime', 'timedelta', 'Refused'}


def api_aliases(tree):
    """Resolve spellings of the one SDK API, including ordinary Python import aliases."""
    aliases = {}
    modules = {'flowguard.intent', 'flowguard.intent.api'}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in modules:
            for name in node.names:
                if name.name == '*':
                    aliases.update({key: key for key in ('rule', 'row', 'distinct', 'states', 'structure_rule')})
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


def is_literal(node):
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


def literal_problems(tree, rel):
    problems = []
    aliases = api_aliases(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or api_call_name(node, aliases) != 'row':
            continue
        for key in node.keywords:
            valid = (isinstance(key.value, ast.Constant) and isinstance(key.value.value, (str, type(None)))) if key.arg in {'why', 'retired'} else is_literal(key.value)
            if key.arg is None or not valid:
                problems.append(dict(file=rel, line=node.lineno, msg=f'row {key.arg or "**mapping"} must be a literal'))
    return problems


def item_names(identifier, homes=(), distincts=(), kind='rule'):
    """The one pytest item naming scheme, also used by static failure diagnostics."""
    if kind != 'rule':
        return [f'{identifier}[{kind}]']
    return ([f'{identifier}[rules]']
            + [f'{identifier}[{target.replace(":", ".")}:{part}]' for target in homes for part in ('rows', 'cells', 'live')]
            + [f'{identifier}[{target.replace(":", ".")}:distinct]' for target in distincts])


class Model:
    def __init__(self, cfg):
        self.cfg = cfg
        self.rules, self.states, self.structures = {}, {}, {}
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

    def node_distincts(self, rid):
        return [d for d in self.distincts if d.rule == rid]

    def items_of(self, rule):
        return item_names(rule.id, [h.target for h in rule.homes], [d.node for d in self.node_distincts(rule.id)])

    def declared_items(self):
        result = [f'{rel}::load' for rel in self.files if any(e['file'] == rel for e in self.errors)]
        result += [f'{self.file_of[r.id]}::{name}' for r in self.rules.values() for name in self.items_of(r)]
        result += [f'{self.file_of[r.id]}::{name}' for items, part in ((self.states, 'states'), (self.structures, 'structure'))
                   for r in items.values() for name in item_names(r.id, kind=part)]
        return sorted(result)


def _error_line(error, path):
    frames = traceback.extract_tb(error.__traceback__)
    return next((f.lineno for f in reversed(frames) if Path(f.filename) == path), 0)


def load(cfg=None, root=None):
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
            owner = model.rules if isinstance(item, Rule) else model.states if isinstance(item, States) else model.structures
            owner[item.id], model.file_of[item.id] = item, rel
        api.DECLARED.clear()
    _validate(model)
    return model


def _validate(model):
    from .cells import kind_of

    def refuse(item, message, line=None):
        model.errors.append(dict(file=model.file_of[item.id], line=line or item.line, msg=f'{item.id}: {message}'))

    for item in [*model.rules.values(), *model.states.values(), *model.structures.values()]:
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
                    rule.homes.append(api.Home(rule, home.target, home.adapter, home.equivalent))
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
    for distinct in model.distincts:
        sides = [name for name in (distinct.a, distinct.b) if ':' not in name]
        if not sides:
            model.errors.append(dict(file=distinct.file, line=distinct.line, msg='distinct needs at least one rule'))
        if distinct.adapter is not None and distinct.node is None:
            model.errors.append(dict(file=distinct.file, line=distinct.line, msg='distinct adapter needs a real node'))
        if distinct.rule in model.rules and distinct.node:
            if not api.TARGET.fullmatch(distinct.node):
                model.errors.append(dict(file=distinct.file, line=distinct.line, msg='distinct node needs module:function'))
            if any(h.target == distinct.node for h in model.rules[distinct.rule].homes):
                model.errors.append(dict(file=distinct.file, line=distinct.line, msg=f'{distinct.rule} is homed at {distinct.node}, so it cannot be distinct from it'))
        for name in (distinct.a, distinct.b):
            if ':' not in name and name not in model.rules:
                model.errors.append(dict(file=distinct.file, line=distinct.line, msg=f'distinct names unknown rule {name}'))
