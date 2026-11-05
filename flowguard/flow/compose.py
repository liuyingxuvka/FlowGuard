"""Compose ordinary Models; exploration stays with flow.explore.

Construction only binds declarations. ``analyze`` is finite work for an existing
worker/part boundary, never work performed by importing a model file.

Use ``reader.foreign(owner, 'field')`` for a read-only getter. Alone it reads the
owner's declared start; within a composition it reads the joint prestate. Invoke
``owner.call(s, 'operation', ...)`` inside an action for an atomic cross-model
call. Ordinary state mapping methods are observed; bypassing them with raw
``dict`` descriptors is unsupported and raises rather than hiding an effect.

Module operations keep their qualified names. With ``features=True`` equal
operation names synchronize, and explicitly repeated field views need one
``owners={'field': model}`` declaration. Nonowner effects are proposals: they
must agree with the real owner's final write. Each participant sees its own
earlier writes; foreign views keep the joint prestate.

``analyze(model, one_more=lambda: build(n+1))`` checks declared finite bounds.
The builder is responsible for preserving the same business at the next size;
stability at two sizes is not a theorem for arbitrary populations. Bind a real
system to the resulting top-level Model with the existing native adapter API;
component adapters do not become a joint adapter by inference.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import MutableMapping
import copy
import functools
from contextlib import contextmanager
from dataclasses import dataclass, field, replace

from .model import (Action, Field, Ids, Loaded, Model, ModelError, Refused, State,
                    natural_key, show_key, validate)


@dataclass(frozen=True)
class Foreign:
    owner: Model
    family: str
    fields: tuple

    def __call__(self, state, obj=None):
        key = self.family if obj is None else (self.family, obj)
        declared = next((item for item in self.fields if item.key == key), None)
        if declared is None:
            raise ModelError(f'foreign {self.owner.name}.{self.family}: no field {show_key(key)}')
        if isinstance(state, _View):
            return state.foreign(self.owner, declared)
        return declared.init


def foreign(model, owner, family):
    if not isinstance(owner, Model) or owner is model:
        raise ModelError('foreign needs a different owning Model')
    fields = tuple(item for item in owner.fields if item.family == family)
    if not fields:
        raise ModelError(f'foreign: {owner.name} declares no field {family!r}')
    result = Foreign(owner, family, fields)
    model.__dict__.setdefault('_foreign_fields', []).append(result)
    for kind, ids in owner.kinds.items():
        if kind not in model.kinds:
            model.objects(kind, *ids)
    # An external fixed identity/value may distinguish otherwise equal objects.
    # Composition's finite transition verification can establish its own symmetry.
    if len({item.init for item in fields}) > 1:
        model.__dict__['_symmetry_doubt'] = 'fixed foreign inputs distinguish objects'
    return result


def call(owner, state, action, args, kwargs):
    if not isinstance(state, _View) or state.transaction is None:
        raise ModelError('a cross-model call needs compose() with the owner or its interface Model')
    return state.transaction.call(owner, action, args, kwargs)


@dataclass(frozen=True)
class _Member:
    model: Model
    action: Action


@dataclass(frozen=True)
class _Operation:
    name: str
    params: tuple
    domains: tuple
    members: tuple


@dataclass
class _Reads:
    actions: dict = field(default_factory=lambda: defaultdict(set))
    writes: dict = field(default_factory=lambda: defaultdict(set))
    rules: dict = field(default_factory=lambda: defaultdict(set))


class _View(MutableMapping):
    """One invocation's local effects; other participants keep the joint prestate."""
    def __init__(self, spec, actor, values, bucket, *, transaction=None):
        self.spec, self.actor, self._global = spec, actor, values
        self.bucket, self.transaction = bucket, transaction
        self.stack = []
        self._local = {item.key: values[item.key] for item in actor.fields if item.key in values}
        self._writes = {}

    def __getitem__(self, key):
        value = self._local[key]
        self.bucket.add(key)
        return value

    def get(self, key, default=None):
        if key in self._local:
            return self[key]
        return default

    def __contains__(self, key):
        self.bucket.add(key)
        return key in self._local

    def _bulk(self):
        self.bucket.update(self._local)

    def __iter__(self):
        self._bulk()
        return iter(self._local)

    def __len__(self):
        self._bulk()
        return len(self._local)

    def keys(self):
        self._bulk()
        return self._local.keys()

    def values(self):
        self._bulk()
        return self._local.values()

    def items(self):
        self._bulk()
        return self._local.items()

    def copy(self):
        self._bulk()
        return self._local.copy()

    def __setitem__(self, key, value):
        if self.transaction is None:
            raise ModelError('a rule cannot write state')
        if key not in self._local:
            raise ModelError(f'{self.actor.name} writes undeclared field {show_key(key)}')
        source = self.stack[-1] if self.stack else None
        source = self.transaction.write(self.actor, key, value, source)
        self._local[key] = value
        self._writes[key] = (value, source)

    def update(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def setdefault(self, key, default=None):
        if key in self:
            return self[key]
        self[key] = default
        return default

    def __delitem__(self, key):
        raise ModelError('model fields are fixed; model object removal with a lifecycle field')

    def pop(self, *args):
        raise ModelError('model fields cannot be removed')

    clear = pop
    popitem = pop

    @contextmanager
    def source(self, request):
        self.stack.append(request)
        try:
            yield self
        finally:
            self.stack.pop()

    def foreign(self, owner, declared):
        actual = self.spec.physical_owner(owner, declared.key)
        if actual in self.spec.leaves:
            if self.spec.owners.get(declared.key) is not actual:
                raise ModelError(f'foreign field {show_key(declared.key)} has another owner')
            self.bucket.add(declared.key)
            return self._global[declared.key]
        return declared.init


class _Transaction:
    def __init__(self, spec, operation, state, args):
        self.spec, self.operation = spec, operation
        self.before = dict(state)
        self.args = args
        self.pending = defaultdict(list)
        self.called, self.active, self.executing = [], set(), []

    def write(self, actor, key, value, source):
        if actor is not self.spec.owners[key] and actor not in self.spec.views.get(key, ()):
            raise ModelError(f'only {self.spec.owners[key].name} owns {show_key(key)}; {actor.name} cannot write it')
        current = self.executing[-1][1].source if self.executing else None
        self.spec.reads.writes[self.operation.name].add(key)
        return source or current

    def invoke(self, member, bindings):
        actor, action = member.model, member.action
        args = tuple(bindings[name] for name in action.params)
        token = actor, action.name, args
        if token in self.active:
            raise ModelError(f'cyclic synchronous call: {actor.name}.{action.name}')
        self.active.add(token)
        self.called.append((actor, action, args))
        self.executing.append((actor, action, args))
        view = _View(self.spec, actor, self.before, self.spec.reads.actions[self.operation.name], transaction=self)
        try:
            result = action.fn(view, *args)
            for key, (value, source) in view._writes.items():
                self.pending[key].append((actor, value, source))
            return result
        except Refused as refusal:
            raise Refused(refusal.reason, refusal.source or action.source, refusal.where) from refusal
        finally:
            self.executing.pop()
            self.active.remove(token)

    def call(self, owner, action, args, kwargs):
        operation = self.spec.aliases.get((owner, action))
        if operation is None:
            raise ModelError(f'owner operation {owner.name}.{action} is outside this composition')
        if len(args) > len(operation.params):
            raise ModelError(f'{owner.name}.{action}: too many arguments')
        bindings = dict(zip(operation.params, args))
        if set(bindings) & set(kwargs):
            raise ModelError(f'{owner.name}.{action}: argument supplied twice')
        bindings.update(kwargs)
        if set(bindings) != set(operation.params) or any(bindings[name] not in domain
                for name, domain in zip(operation.params, operation.domains)):
            raise ModelError(f'{owner.name}.{action}: arguments are outside the declared interface')
        values = [self.invoke(member, bindings) for member in operation.members]
        return values[0] if len(values) == 1 else tuple(values)

    def commit(self, state):
        writes = []
        for key, proposals in self.pending.items():
            value = proposals[0][1]
            if any(other != value for _, other, _ in proposals):
                raise ModelError(f'inconsistent shared field effects for {show_key(key)}')
            owner = self.spec.owners[key]
            authoritative = [(v, source) for actor, v, source in proposals if actor is owner]
            if not authoritative and value != self.before[key]:
                raise ModelError(f'{owner.name} did not write the proposed change to {show_key(key)}')
            if authoritative:
                writes.append((key, value, authoritative[0][1]))
        for key, value, source in writes:
            with state.source(source):
                state[key] = value


class _Composition:
    def __init__(self, leaves, owners, views, aliases, operations, kind, one_more=None):
        self.leaves, self.owners, self.views = tuple(leaves), owners, views
        self.aliases, self.operations, self.kind = aliases, operations, kind
        self.reads = _Reads()
        self.last = None
        self.model = None
        self.one_more = one_more

    @staticmethod
    def physical_owner(model, key):
        inner = model.__dict__.get('_composition')
        return inner.owners[key] if inner is not None else model

    def execute(self, operation, state, args):
        transaction = _Transaction(self, operation, state, args)
        bindings = dict(zip(operation.params, args))
        outputs = [transaction.invoke(member, bindings) for member in operation.members]
        transaction.commit(state)
        self.last = transaction
        return outputs[0] if len(outputs) == 1 else tuple(outputs) if any(value is not None for value in outputs) else None

    def rule_view(self, actor, state, rule):
        return _View(self, actor, state, self.reads.rules[actor, rule.name])

    def prepare_load(self, root, tree):
        """Keep the existing settings-origin checks on the original component code."""
        from .model import check_settings_from_code
        self.model.code_configs = []
        for actor in self.leaves:
            actor.path = actor.path or self.model.path
            actor.root = root
            check_settings_from_code(actor, root, tree)
            self.model.code_configs.extend(actor.code_configs)
            for setting, info in actor.setting_info.items():
                label = actor.name + '/' + setting
                self.model.setting_info[label] = replace(info, name=label)


def _same_schema(first, second):
    return (first.domain, first.init, first.kind) == (second.domain, second.init, second.kind)


def compose(name, *models, kind, features=False, owners=None, one_more=None):
    """Bind one shared-kind composition without exploring or running model actions.

    Strict module mode rejects duplicate fields. In feature mode ``owners`` names
    the one authoritative model of an explicitly shared view; other effects must
    agree with it. Same-named feature operations synchronize their arguments.
    The optional one_more builder is called only by explicit full qualification,
    inside the existing worker; construction and ordinary check do not call it.
    """
    if not models or any(not isinstance(model, Model) for model in models):
        raise ModelError('compose needs one or more Models')
    if one_more is not None and not callable(one_more):
        raise ModelError('one_more must be a builder of the same composition with one extra object')
    leaves, aliases, candidates, inherited, views = [], {}, defaultdict(list), {}, defaultdict(set)
    inputs = []
    for model in models:
        inner = model.__dict__.get('_composition')
        members = inner.leaves if inner is not None else (model,)
        for member in members:
            if member not in leaves:
                if any(old.name == member.name for old in leaves):
                    raise ModelError(f'two different component Models have the same name {member.name!r}')
                leaves.append(member)
        if inner is not None:
            for key, owner in inner.owners.items():
                if key in inherited and inherited[key] is not owner:
                    raise ModelError(f'overlapping views: {show_key(key)} has different owners')
                inherited[key] = owner
            for key, actors in inner.views.items():
                views[key].update(actors)
            aliases.update(inner.aliases)
            operations = tuple(inner.operations.values())
        else:
            operations = tuple(_Operation(action.name, action.params, action.domains, (_Member(model, action),))
                               for action in model.actions)
        for operation in operations:
            aliases[model, operation.name] = operation
        inputs.extend((model, operation) for operation in operations)
    leaves.sort(key=lambda model: model.name)
    for actor in leaves:
        validate(actor)
        for item in actor.fields:
            candidates[item.key].append((actor, item))
    if not any(kind in actor.kinds for actor in leaves):
        raise ModelError(f'composition has no declared shared object kind {kind!r}')
    selected, fields = {}, []
    for key, declarations in sorted(candidates.items(), key=lambda pair: show_key(pair[0])):
        chosen = (owners or {}).get(key, (owners or {}).get(declarations[0][1].family, inherited.get(key)))
        if isinstance(chosen, str):
            label = chosen
            chosen = next((actor for actor in leaves if actor.name == label), None)
            if chosen is None:
                raise ModelError(f'owner {label!r} of {show_key(key)} is outside this composition')
        if len(declarations) > 1:
            if not all(_same_schema(declarations[0][1], item) for _, item in declarations[1:]):
                names = ', '.join(actor.name for actor, _ in declarations)
                raise ModelError(f'overlapping views: different domains/starts for {show_key(key)} in {names}')
            if chosen is None or not (features or key in inherited):
                raise ModelError(f'overlapping views: {show_key(key)} needs exactly one declared owner')
            views[key].update(actor for actor, _ in declarations if actor is not chosen)
        chosen = chosen or declarations[0][0]
        declared = next((item for actor, item in declarations if actor is chosen), None)
        if declared is None:
            raise ModelError(f'owner of {show_key(key)} does not declare that field')
        selected[key] = chosen
        value_sources = dict(declared.value_sources)
        for _, item in declarations:
            for value, source in item.value_sources.items():
                value_sources.setdefault(value, source)
        source = declared.source or next((item.source for _, item in declarations if item.source), None)
        fields.append(replace(declared, source=source, value_sources=value_sources))
    groups = defaultdict(list)
    for model, operation in inputs:
        group = operation.name if features else model.name + '.' + operation.name
        groups[group].append(operation)
    operations = {}
    for label, group in groups.items():
        first = group[0]
        domains = dict(zip(first.params, first.domains))
        for other in group[1:]:
            if set(other.params) != set(first.params) or any(set(domain) != set(domains[param])
                    for param, domain in zip(other.params, other.domains)):
                raise ModelError(f'synchronized operation {label!r} has incompatible parameters/domains')
        members = tuple(dict(((member.model, member.action.name), member)
                             for operation in group for member in operation.members).values())
        operations[label] = _Operation(label, first.params, first.domains, members)
    # An interface call is the same synchronized operation, including every
    # feature guard; it must not sneak through one participant's raw function.
    for model, operation in inputs:
        label = operation.name if features else model.name + '.' + operation.name
        bound = operations[label]
        aliases[model, operation.name] = bound
        for member in operation.members:
            key = member.model, member.action.name
            old = aliases.get(key)
            if old is not None and len(old.members) > 1 and set(old.members) != set(bound.members):
                raise ModelError(f'overlapping operation interfaces for {member.model.name}.{member.action.name}')
            aliases[key] = bound
    result = Model(name, covers=tuple(dict.fromkeys(path for actor in leaves for path in actor.covers)))
    if any(actor.valid is not None for actor in leaves):
        result.valid = lambda settings: all(actor.valid(actor.settings) for actor in leaves if actor.valid is not None)
    result.fields = fields
    kinds = defaultdict(set)
    for actor in leaves:
        for group, ids in actor.kinds.items():
            kinds[group].update(ids)
    for group, ids in kinds.items():
        result.objects(group, *sorted(ids, key=natural_key))
    spec = _Composition(leaves, selected, views, aliases, operations, kind, one_more)
    spec.model = result
    result.__dict__['_composition'] = spec
    result.__dict__['_setting_targets'] = {}
    for operation in operations.values():
        def execute(state, *args, _operation=operation):
            return spec.execute(_operation, state, args)
        first = operation.members[0].action
        result.actions.append(Action(len(result.actions), operation.name, operation.params, operation.domains,
                                     execute, first.source, first.note, first.line))
    for actor in leaves:
        for family, values in actor.terminals.items():
            if family in result.terminals and result.terminals[family] != values:
                raise ModelError(f'overlapping end values for {family}')
            result.terminals[family] = values
            result.terminal_sources[family] = result.terminal_sources.get(family) or actor.terminal_sources.get(family)
        for rule in actor.rules:
            _copy_rule(result, spec, actor, rule)
        for option in actor.options:
            for operation in operations.values():
                if not any(member.model is actor and member.action.name == option.action
                           for member in operation.members):
                    continue
                def offered(state, *args, _actor=actor, _option=option):
                    return _option.offered(_View(spec, _actor, state,
                        spec.reads.rules[_actor, 'option:' + _option.name]), *args)
                result.options.append(replace(option, name=actor.name + '/' + option.name + '@' + operation.name,
                                              action=operation.name, offered=offered))
        for setting, info in actor.setting_info.items():
            label = actor.name + '/' + setting
            dict.__setitem__(result._settings, label, actor.settings[setting])
            result.setting_info[label] = replace(info, name=label)
            result.__dict__['_setting_targets'][label] = actor, setting
        for route in actor.second_routes:
            mapped = []
            for action in route.actions:
                labels = [operation.name for operation in operations.values() if any(
                    member.model is actor and member.action.name == action for member in operation.members)]
                if len(labels) != 1:
                    raise ModelError(f'route {actor.name}.{action} needs one public operation')
                mapped.append(labels[0])
            result.second_routes.append(replace(route, actions=tuple(mapped)))
    validate(result)
    return result


def _copy_rule(result, spec, actor, rule):
    label = actor.name + '/' + rule.name
    def wrap(predicate):
        if predicate is None:
            return None
        @functools.wraps(predicate)
        def wrapped(state, *args):
            return predicate(spec.rule_view(actor, state, rule), *args)
        return wrapped
    if rule.kind in {'always', 'reach', 'progress'}:
        result.rules.append(replace(rule, name=label, base=actor.name + '/' + rule.base,
                                    pred=wrap(rule.pred), when=wrap(rule.when), goal=wrap(rule.goal)))
        return
    for operation in spec.operations.values():
        @functools.wraps(rule.pred)
        def predicate(before, *args, _operation=operation):
            if spec.last is None:
                raise ModelError('a composed action rule has no completed synchronous step')
            after = args[0] if rule.kind == 'after' else None
            for called_actor, action, actual_args in spec.last.called:
                if called_actor is not actor or rule.action not in ('*', action.name):
                    continue
                pre = spec.rule_view(actor, before, rule)
                if rule.kind == 'only_when':
                    ok = rule.pred(pre, *actual_args)
                else:
                    post = spec.rule_view(actor, after, rule)
                    ok = (rule.pred(pre, post, action.name, actual_args) if rule.action == '*'
                          else rule.pred(pre, post, *actual_args))
                if not ok:
                    return False
            return True
        result.rules.append(replace(rule, name=label + '@' + operation.name, base=actor.name + '/' + rule.base,
                                    action=operation.name, pred=predicate))


def boundary(model):
    """The explicit scope of imports even when a component is explored alone."""
    spec = model.__dict__.get('_composition')
    members = spec.leaves if spec is not None else (model,)
    return [{'model': actor.name, 'owner': ref.owner.name, 'field': ref.family,
             'mode': 'owner model' if spec is not None and all(spec.physical_owner(ref.owner, item.key) in spec.leaves
                     for item in ref.fields) else 'fixed at owner start'}
            for actor in members for ref in actor.__dict__.get('_foreign_fields', [])]


def source_actions(model):
    """Original action functions, kept for the existing trace/guard AST owners."""
    spec = model.__dict__.get('_composition')
    return [(actor, action) for actor in spec.leaves for action in actor.actions] if spec else [(model, action) for action in model.actions]


def field_views(model, key):
    spec = model.__dict__.get('_composition')
    return [(actor, item) for actor in spec.leaves for item in actor.fields if item.key == key] if spec else [(model, item) for item in model.fields if item.key == key]


def scope_summary(model, report=None):
    """Cheap declared boundary; this function never explores or invokes a builder."""
    spec = model.__dict__.get('_composition')
    if spec is None:
        return None
    return {'objects': _object_bounds(model), 'foreign': boundary(model),
            'finite_scope_complete': None if report is None else report.graph.complete,
            'projection': {'status': 'not run; use check --full', 'verified': False},
            'one_more': {'declared': spec.one_more is not None, 'status': 'not run; use check --full'},
            'ownership': [{'field': show_key(item.key), 'owner': spec.owners[item.key].name,
                           'views': sorted(actor.name for actor in spec.views.get(item.key, ()))}
                          for item in model.fields],
            'synchronizes': {name: [member.model.name + '.' + member.action.name for member in operation.members]
                             for name, operation in spec.operations.items() if len(operation.members) > 1},
            'native': {'checked': False,
                       'top_level_binding': spec.model.adapter_binding is not None,
                       'component_bindings': [actor.name for actor in spec.leaves if actor.adapter_binding is not None],
                       'scope': 'logical Model execution; native conformance uses the existing adapter part'}}


@dataclass
class CompositionReport:
    report: object
    projection: dict
    objects: dict
    symmetry: dict
    foreign: list
    one_more: dict | None = None
    source_report: object = None
    reads: tuple = ()
    inputs: dict = field(default_factory=dict)
    hashes: dict = field(default_factory=dict)

    @property
    def complete(self):
        return self.report.graph.complete and not any(f.cls == 'error' for f in self.report.findings)

    def summary(self):
        return {**scope_summary(self.report.loaded.model, self.report), 'complete': self.complete,
                'finite_scope_complete': self.report.graph.complete,
                'states': len(self.report.graph.states), 'projection': self.projection,
                'objects': self.objects, 'symmetry': self.symmetry, 'foreign': self.foreign,
                'one_more': self.one_more,
                'findings': [finding.to_json() for finding in self.report.findings]}


def _ids_in(value, ids):
    from .explore import _has_id
    return _has_id(value, ids)


def _object_bounds(model):
    return {kind: len(ids) for kind, ids in model.kinds.items()}


def _closure(model):
    spec = model.__dict__['_composition']
    identifiers = set(model.kinds[spec.kind])
    fields = {item.key for item in model.fields if item.kind == spec.kind or
              _ids_in(item.key, identifiers) or _ids_in(item.domain, identifiers)}
    actions = {name for name, operation in spec.operations.items()
               if any(_ids_in(domain, identifiers) for domain in operation.domains)}
    rules = set()
    if not fields and not actions:
        return None
    changed = True
    while changed:
        prior = len(fields), len(actions), len(rules)
        for name in spec.operations:
            read = spec.reads.actions[name]
            written = spec.reads.writes[name]
            if read & fields or written & fields:
                actions.add(name)
            if name in actions:
                fields.update(read | written)
        for actor in spec.leaves:
            for rule in actor.rules:
                read = spec.reads.rules[actor, rule.name]
                if not read or read & fields:
                    rules.add((actor, rule.name))
                    fields.update(read)
            for option in actor.options:
                read = spec.reads.rules[actor, 'option:' + option.name]
                if not read or read & fields:
                    fields.update(read)
        changed = prior != (len(fields), len(actions), len(rules))
    projected = copy.copy(model)
    projected.fields = [item for item in model.fields if item.key in fields]
    projected.actions = [replace(action, index=index) for index, action in enumerate(model.actions)
                         if action.name in actions]
    # Reindex after the filter rather than retaining holes in the call table.
    projected.actions = [replace(action, index=index) for index, action in enumerate(projected.actions)]
    labels = {actor.name + '/' + name for actor, name in rules}
    projected.rules = [rule for rule in model.rules if
                       any(rule.name == label or rule.name.startswith(label + '@') for label in labels)
                       and (rule.action in (None, '*') or rule.action in actions)]
    projected.options = [option for option in model.options if option.action in actions]
    projected.second_routes = [route for route in model.second_routes if set(route.actions) <= actions]
    families = {item.family for item in projected.fields}
    projected.terminals = {family: values for family, values in model.terminals.items() if family in families}
    projected.terminal_sources = {family: source for family, source in model.terminal_sources.items() if family in families}
    projected._calls = None
    projected.__dict__.pop('_symmetry', None)
    return projected


def _transition_projection(full, projected):
    """Check a finite projected transition relation against its complete source graph."""
    positions = [full.keys.index(key) for key in projected.keys]
    expected = {tuple(state[pos] for pos in positions) for state in full.states}
    if set(projected.states) != expected:
        return False
    index = {state: i for i, state in enumerate(projected.states)}
    calls = {(call.action.name, call.args): call.index for call in full.calls}
    for i, state in enumerate(full.states):
        before = tuple(state[pos] for pos in positions)
        row = projected.out[index[before]]
        for call in projected.calls:
            original = full.out[i][calls[call.action.name, call.args]]
            actual = row[call.index]
            if original < 0 or actual < 0:
                if (original < 0) != (actual < 0):
                    return False
            elif projected.states[actual] != tuple(full.states[original][pos] for pos in positions):
                return False
    return True


def _observe_predicates(graph, progress=None):
    """Finish predicate reads even after the ordinary check found its first witness."""
    model, keys = graph.model, graph.keys
    state_rules = [rule for rule in model.rules if rule.kind in {'always', 'reach', 'progress'}]
    step_rules = [rule for rule in model.rules if rule.kind in {'only_when', 'after'}]
    values = {rule.name: bytearray() for rule in state_rules}
    step_calls = {rule.name: [call.index for call in graph.calls if rule.action in ('*', call.action.name)]
                  for rule in step_rules}
    steps = {rule.name: bytearray(len(graph.states) * len(step_calls[rule.name])) for rule in step_rules}
    options = [bytearray() for _ in graph.option_calls]
    for i, row in enumerate(graph.out):
        before = State(zip(keys, graph.states[i]))
        for rule in state_rules:
            args = (before,) if rule.obj is None else (before, rule.obj)
            value = ((bool(rule.when(*args)) << 1) | bool(rule.goal(*args)) if rule.kind == 'progress'
                     else bool(rule.pred(*args)))
            values[rule.name].append(value)
        for index, (option, args) in enumerate(graph.option_calls):
            options[index].append(bool(option.offered(before, *args)))
        if step_rules:
            for call in graph.calls:
                if row[call.index] < 0:
                    continue
                after = State(before)
                call.action.fn(after, *call.args)
                if tuple(after[key] for key in keys) != graph.raw_successor(i, call.index):
                    raise ModelError('a synchronous step changed when replayed for its rule observations')
                for rule in step_rules:
                    calls = step_calls[rule.name]
                    if call.index not in calls:
                        continue
                    if rule.kind == 'only_when':
                        value = rule.pred(before, *call.args)
                    elif rule.action == '*':
                        value = rule.pred(before, after, call.action.name, call.args)
                    else:
                        value = rule.pred(before, after, *call.args)
                    steps[rule.name][i * len(calls) + calls.index(call.index)] = bool(value)
        if progress is not None and i % 1000 == 0:
            progress({'states': i + 1})
    return values, steps, step_calls, options


def _finite_symmetry(graph, observations):
    """Verify renaming on the existing complete graph; this is no new explorer."""
    from .explore import Symmetry
    from .adapter import _rename
    sym = Symmetry(graph.model)
    if sym.n == 1:
        return None
    generators = []
    for kind in sym.kinds:
        ids = graph.model.kinds[kind]
        for a, b in zip(ids, ids[1:]):
            images = dict(zip(sym.ids, sym.ids))
            images[a], images[b] = b, a
            generators.append(sym.code[tuple(images[value] for value in sym.ids)])
    index = {state: i for i, state in enumerate(graph.states)}
    values, steps, step_calls, options = observations
    rules = {(rule.kind, rule.base, rule.action, rule.obj): rule for rule in graph.model.rules}
    option_index = {(option.name, args): i for i, (option, args) in enumerate(graph.option_calls)}
    spec = graph.model.__dict__['_composition']
    fields = graph.model.fields
    for p in generators:
        for q, field in enumerate(fields):
            other = fields[sym.dest[p][q]]
            if (spec.owners[field.key] is not spec.owners[other.key] or
                    field.source != other.source or field.value_sources != other.value_sources):
                raise ModelError('field ownership or source authority distinguishes objects under renaming')
        for i, state in enumerate(graph.states):
            j = index.get(sym.apply(p, state))
            if j is None:
                raise ModelError('a renamed reachable state is absent from the full finite graph')
            for call in graph.calls:
                c, d = call.index, sym.call_perm[p][call.index]
                a, b = graph.out[i][c], graph.out[j][d]
                if (a < 0) != (b < 0):
                    raise ModelError('objects are not interchangeable: renamed guards accept differently')
                if a >= 0:
                    if sym.apply(p, graph.states[a]) != graph.states[b] or _rename(graph.outputs.get((i, c)), sym.maps[p]) != graph.outputs.get((j, d)):
                        raise ModelError('objects are not interchangeable: renamed effects or outputs differ')
                else:
                    left, right = graph.refusals[-1 - a], graph.refusals[-1 - b]
                    if (sym.rename(p, left.reason), left.source) != (right.reason, right.source):
                        raise ModelError('objects are not interchangeable: refusal reasons or sources differ')
            for rule in graph.model.rules:
                other = rules.get((rule.kind, rule.base, rule.action, sym.rename(p, rule.obj)))
                if other is None:
                    raise ModelError('an object rule has no renamed counterpart')
                if rule.name in values:
                    if values[rule.name][i] != values[other.name][j]:
                        raise ModelError('objects are not interchangeable: renamed rule truth differs')
                else:
                    calls, targets = step_calls[rule.name], step_calls[other.name]
                    for k, c in enumerate(calls):
                        d = sym.call_perm[p][c]
                        if steps[rule.name][i * len(calls) + k] != steps[other.name][j * len(targets) + targets.index(d)]:
                            raise ModelError('objects are not interchangeable: renamed step rules differ')
            for k, (option, args) in enumerate(graph.option_calls):
                target = option_index[option.name, sym.rename(p, args)]
                if options[k][i] != options[target][j]:
                    raise ModelError('objects are not interchangeable: renamed offered options differ')
    return sym


def attribute(model, findings, *, merged=True):
    """Retain every successful synchronized participant's actual request source."""
    from .checks import fingerprint, merge
    spec = model.__dict__['_composition']
    def add(finding):
        sources = set(finding.sources)
        calls = finding.detail.get('calls', ())
        if not isinstance(calls, (list, tuple)):
            calls = ()
        for step in [*finding.path, *calls]:
            for label, operation in spec.operations.items():
                if step.startswith(label + '('):
                    sources.update(member.action.source for member in operation.members if member.action.source)
        for actor in spec.leaves:
            name = finding.detail.get('name', '')
            for rule in actor.rules:
                label = actor.name + '/' + rule.name
                if name == label or name.startswith(label + '@'):
                    for key in spec.reads.rules[actor, rule.name]:
                        item = next((field for field in spec.model.fields if field.key == key), None)
                        if item is not None and item.source:
                            sources.add(item.source)
        key = finding.detail.get('key')
        for actor in spec.leaves:
            for item in actor.fields:
                if key == show_key(item.key):
                    sources.update(source for source in [item.source, *item.value_sources.values()] if source)
        sources = tuple(sorted(sources, key=natural_key))
        return replace(finding, sources=sources,
                       id=fingerprint(finding.kind, finding.model, finding.subject, sources))
    result = [add(finding) for finding in findings]
    return merge(result) if merged else result


def annotate(report):
    report.findings = attribute(report.loaded.model, report.findings)
    report.raw = attribute(report.loaded.model, report.raw, merged=False)
    return report


def _signatures(report):
    # Prepared-check subjects are already object-family expressions. Rule names
    # with concrete ids are normalized for this explicit one-extra-object probe.
    model = report.loaded.model
    signatures = set()
    for finding in report.findings:
        if finding.cls != 'conflict':
            continue
        subject = finding.subject
        for kind, ids in model.kinds.items():
            for obj in sorted(ids, key=len, reverse=True):
                subject = subject.replace('[' + obj + ']', '[' + kind + ']')
        signatures.add((finding.kind, subject, tuple(finding.sources)))
    return signatures


def _build_more(model, builder):
    """A late builder import uses the same fresh source loader and manifest owner."""
    if model.root is None:
        return builder(), (), {}, {}
    from .model import _project_source_scope, _project_modules, _error_location
    from .descriptors import input_evidence
    from .project import file_digest
    root = model.root
    with _project_source_scope(root, model.path) as imports:
        try:
            larger = builder()
        except Exception as error:
            file, line = _error_location(error, root)
            failed = ModelError(f'one_more builder raised {type(error).__name__}: {error}', file, line)
            failed.reads = tuple(sorted(set(_project_modules(root).values()) | imports.reads))
            raise failed from error
        reads = tuple(sorted(set(_project_modules(root).values()) | imports.reads))
        inputs = input_evidence(root, reads)
        hashes = {rel: file_digest(root, rel) for rel in reads}
        return larger, reads, inputs, hashes


def analyze(model, bounds=None, *, progress=None, project=True, reduce=True, one_more=None, _probe=True):
    """Run inside an existing worker, using only the existing Model/check explorer.

    Projection is licensed by a complete finite unreduced dependency observation.
    This foundation trades a prepass for a checked boundary; it does not promise
    that large cartesian products become cheap. A cap keeps the full scope UNKNOWN.
    ``one_more`` is a builder callback that actually constructs the next bound.
    """
    from .checks import check_model, make_finding, verify_symmetry
    from .explore import Bounds
    spec = model.__dict__.get('_composition')
    if spec is None:
        raise ModelError('analyze needs a Model returned by compose')
    if one_more is None and _probe:
        one_more = spec.one_more
    bounds = bounds or Bounds()
    def phase(name):
        return None if progress is None else lambda item: progress({'phase': name, **item})
    observed = check_model(Loaded(model, ()), bounds, explain=False, reduce=False,
                           progress=phase('observing the finite dependency scope'))
    observations = None
    if observed.graph.complete and not any(finding.cls == 'error' for finding in observed.findings):
        try:
            observations = _observe_predicates(observed.graph, phase('observing every finite predicate'))
        except Exception as error:
            observed.findings.append(make_finding('MODEL ERROR', 'error', model.id or model.name,
                'composed predicate observation', str(error)))
    original_fields, original_actions = len(model.fields), len(model.actions)
    projection = {'method': 'complete finite observed read/write closure',
                  'scope': 'shared-object closure; independent state is outside the projected report',
                  'shared_kind': spec.kind, 'source_complete': observations is not None,
                  'fields_before': original_fields, 'actions_before': original_actions,
                  'verified': False, 'status': 'not requested' if not project else 'UNKNOWN'}
    checked = observed
    current = model
    if project and observations is not None:
        candidate = _closure(model)
        if candidate is not None:
            plain = check_model(Loaded(candidate, ()), bounds, explain=False, reduce=False,
                                progress=phase('verifying the shared-object closure'))
            if plain.graph.complete and _transition_projection(observed.graph, plain.graph):
                checked, current = plain, candidate
                observations = _observe_predicates(plain.graph, phase('observing projected predicates'))
                projection.update(verified=True, status='complete within this observed finite scope')
            else:
                projection['status'] = 'UNKNOWN: projection was not equivalent; full scope retained'
        else:
            projection['status'] = 'UNKNOWN: no state/action uses the selected object kind; full scope retained'
    projection.update(fields_after=len(current.fields), actions_after=len(current.actions))
    symmetry = {'used': False, 'verified': None}
    if reduce and observations is not None:
        try:
            sym = _finite_symmetry(checked.graph, observations)
            current = copy.copy(current)
            current.__dict__['_symmetry'] = sym
            reduced = check_model(Loaded(current, ()), bounds, explain=False, reduce=True,
                                  progress=phase('checking object renaming'))
            verification = verify_symmetry(Loaded(current, ()), bounds, reduced, explain=False, plain=checked)
            symmetry = {'used': reduced.graph.sym is not None, 'verified': verification['verified'],
                        'method': 'all finite transitions, predicate truth and renaming generators; existing findings comparison',
                        'text': verification['text'], 'states_unreduced': len(checked.graph.states),
                        'states_reduced': len(reduced.graph.states)}
            if verification['verified'] is True or reduced.graph.sym is None:
                checked = reduced
            elif verification['finding'] is not None:
                checked.findings.append(verification['finding'])
        except ModelError as error:
            symmetry = {'used': False, 'verified': False, 'text': error.text}
            checked.findings.append(make_finding('MODEL ERROR', 'error', model.id or model.name,
                                                 'objects are not interchangeable', error.text))
    checked = annotate(checked)
    result = CompositionReport(checked, projection, _object_bounds(model), symmetry, boundary(model),
                               source_report=annotate(observed) if observed is not checked else checked)
    if one_more is not None:
        larger, result.reads, result.inputs, result.hashes = _build_more(model, one_more)
        if not isinstance(larger, Model) or '_composition' not in larger.__dict__:
            raise ModelError('the one-more builder must return another composed Model')
        counts = _object_bounds(larger)
        if counts.get(spec.kind) != result.objects[spec.kind] + 1 or any(
                counts.get(kind) != count for kind, count in result.objects.items() if kind != spec.kind):
            raise ModelError('the probe must add exactly one object of the selected kind')
        next_result = analyze(larger, bounds, progress=progress, project=project, reduce=reduce, _probe=False)
        complete = result.complete and next_result.complete
        before, after = _signatures(checked), _signatures(next_result.report)
        result.one_more = {'objects': counts, 'complete': complete,
                           'changed': before != after if complete else None,
                           'added': sorted(after - before), 'removed': sorted(before - after),
                           'findings': [finding.to_json() for finding in next_result.report.findings],
                           'boundary': 'these two declared finite object bounds only'}
    return result
