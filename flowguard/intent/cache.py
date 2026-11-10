"""Read the existing map cache and declaration facts without importing project code."""
from __future__ import annotations

import ast
from contextlib import closing
import json
import re
from pathlib import Path
import sqlite3

from .config import intent_files
from .loader import api_aliases, api_call_name, distinct_identifier, literal_problems
from flowguard.map.common import MapError, content_digest, git_common_directory, git_head, literal_value as _literal


# flowguard: owner meta.k writers=flowguard.intent.cache:put_meta
# flowguard: owner meta.v writers=flowguard.intent.cache:put_meta
def put_meta(con, name, text):
    """The one writer of the test cache's keys in the map's SQLite meta table (the map writes its own keys)."""
    con.execute('INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)', (name, text))


def session_baseline(cfg, *, remember=False):
    """The comparison commit: `task_baseline`'s, recording nothing; None where nothing can be compared: outside
    Git, before the first commit, and for a recorded commit this repository lacks (kind 'missing', which pytest,
    `check` and `check --static` name in their title with the next step). `remember` is the brief's call
    (`remember_baseline`), which keeps a task's baseline while HEAD descends from it."""
    if remember:
        return remember_baseline(cfg)[0]
    commit, kind = task_baseline(cfg)
    return None if kind == 'missing' else commit


def task_baseline(cfg, *, record=False):
    """(commit, kind) of `task_start`, without the distance from HEAD."""
    return task_start(cfg, record=record)[:2]


def task_start(cfg, *, record=False):
    """(commit, kind, ahead) of the task-start commit in the existing SQLite meta: kind 'task' for a recorded one,
    `ahead` the number of commits HEAD lies after it (None when HEAD does not descend from it); 'missing' for a
    recorded commit this repository does not have (a shallow clone, history rewritten and collected, a cache from
    another clone), which compares nothing until the brief or new-task records HEAD; 'HEAD' when nothing is
    recorded and HEAD stands in; (None, None, None) outside Git or before the first commit. A recorded commit
    costs one git call (`_position`). `record` is the call of pytest with the plugin and of `check` and
    `check --static` without an explicit baseline: when nothing is recorded it records HEAD, so a task that never
    runs the brief gets its baseline at its first run. It never moves a recorded baseline, not even one HEAD does
    not descend from (a run on another branch, an older commit, a bisect step, IDE test discovery after a branch
    switch) or one that is missing: only the brief and new-task move it (`remember_baseline`), and they say why, so
    a run elsewhere neither hides what the task committed nor blames an older commit's changes on it. A detached
    HEAD (a tag or an older commit checked out, a bisect step, a CI checkout) records nothing either: a test run
    there would otherwise fix the next task's start on that commit. Other readers (vitest, `ledger check`,
    `debug watch`) record nothing."""
    if git_common_directory(cfg.root) is None:
        return None, None, None
    recorded = _recorded_baseline(cfg)
    if recorded is not None:
        known, ahead = _position(cfg, recorded)
        return (recorded, 'task', ahead) if known else (recorded, 'missing', None)
    head = git_head(cfg.root)
    if head is None:
        return None, None, None
    if record and _on_branch(cfg):
        _record_baseline(cfg, head)
        return head, 'task', 0
    return head, 'HEAD', 0


def _position(cfg, recorded):
    """(known, ahead) of a recorded commit in one git call: `known` is False when this repository lacks it;
    `ahead` is the number of commits HEAD lies after it when HEAD descends from it, else None."""
    from flowguard.map.common import git_run
    found = git_run(cfg.root, 'rev-list', '--left-right', '--count', f'{recorded}...HEAD', allowed=(0, 128))
    if not found.returncode:
        behind, ahead = (int(number) for number in found.stdout.split())
        return True, None if behind else ahead
    # Git refuses the range for a commit it lacks, and for a HEAD without a commit (an orphan branch).
    if git_run(cfg.root, 'rev-parse', '-q', '--verify', recorded + '^{commit}', allowed=(0, 1)).returncode:
        return False, None
    if git_head(cfg.root) is None:
        return True, None
    raise MapError(f'git rev-list failed in {cfg.root}: '
                   + (found.stderr.decode(errors='replace').strip() or f'exit status {found.returncode}'))


def _on_branch(cfg):
    """Is HEAD a branch (not detached)?"""
    from flowguard.map.common import git_run
    return git_run(cfg.root, 'symbolic-ref', '-q', 'HEAD', allowed=(0, 1)).returncode == 0


def _recorded_baseline(cfg):
    """The recorded task-start commit, or None when nothing is recorded; an unreadable record raises."""
    path = cfg.cache / 'map.sqlite'
    if not path.is_file():
        return None
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as con:
            table = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone()
            row = con.execute("SELECT v FROM meta WHERE k='task_baseline'").fetchone() if table else None
            if not row:
                return None
            data = json.loads(row[0])
            commit = data.get('commit') if isinstance(data, dict) else None
            if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
                raise ValueError('task_baseline needs a full 40-character commit')
            return commit
    except (sqlite3.DatabaseError, ValueError, TypeError) as error:
        raise MapError(f'{path}: task baseline could not be read: {error}') from error


def _record_baseline(cfg, commit):
    """The one write of the task baseline."""
    from ..structure.store import connect
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        put_meta(con, 'task_baseline', json.dumps({'commit': commit}))


def _commits(number):
    return f'{number} commit{"s" * (number != 1)}'


def remember_baseline(cfg, *, new_task=False):
    """(commit, note) of the brief. The task baseline is recorded at HEAD only when none is recorded, when
    the recorded commit is not an ancestor of HEAD (another branch, rewritten history) or this repository lacks
    it, or when `new_task` starts the next task (`python -m flowguard new-task`). Commits made during a task keep
    its baseline, so what the task changed stays reported. On a detached HEAD (a tag or an older commit checked
    out, a bisect step) the brief neither moves nor records it, as test runs do not: back on the branch the task's
    commits are still reported; new-task records HEAD there too. `note` says why the baseline is where it is, ''
    when it was recorded at HEAD with nothing recorded before. When new-task replaces a start HEAD descends from,
    the note says those commits are no longer compared and how to compare them once (pytest, or `check --static` in
    a project whose tests npm runs, `deps.static_only`). Test runs only record a
    baseline when none is recorded (`task_start(record=True)`); moving one is this call's alone, as it says why."""
    if git_common_directory(cfg.root) is None:
        return None, ''
    head = git_head(cfg.root)
    if head is None:
        return None, ''
    recorded = _recorded_baseline(cfg)
    known, ahead = _position(cfg, recorded) if recorded is not None else (False, None)
    if new_task:
        _record_baseline(cfg, head)
        if recorded is None or recorded == head:
            return head, f'baseline: new task from HEAD {head[:12]}'
        if not ahead:
            return head, f'baseline: new task from HEAD {head[:12]} (was {recorded[:12]}' + ('' if known else ', not in this repository') + ')'
        from .deps import static_only       # a TS/JS project has no pytest run to compare with: its map checks do
        once = (f'python -m flowguard check --static --base {recorded[:12]}' if static_only(cfg)
                else f'python -m pytest --flowguard-base {recorded[:12]}')
        return head, (f'baseline: new task from HEAD {head[:12]} (was {recorded[:12]}, {_commits(ahead)} before HEAD: those changes '
                      f'are no longer compared; compare them once with {once})')
    if not _on_branch(cfg):
        state = ('HEAD stands in' if recorded is None else
                 f'the recorded {recorded[:12]} is not in this repository, so nothing is compared' if not known else
                 f'the task baseline stays at {recorded[:12]}, which HEAD does not descend from' if ahead is None else
                 f'the task baseline stays at {recorded[:12]}' + (f', {_commits(ahead)} before HEAD' if ahead else ''))
        return recorded or head, f'baseline: HEAD is detached, so the brief records nothing ({state}); python -m flowguard new-task starts a task here'
    if known and ahead is not None:
        return recorded, f'baseline: task start, {_commits(ahead)} before HEAD; next task: python -m flowguard new-task' if ahead else ''
    _record_baseline(cfg, head)
    if recorded is not None:
        return head, f'baseline: recorded {recorded[:12]} is ' + ('not an ancestor of HEAD' if known else 'not in this repository') + '; the task starts at HEAD'
    return head, ''


# The one-line relation templates and their name parameters (flowguard/intent/api.py).
_TEMPLATES = {'precedes': ('first', 'then'), 'guarded_by': ('guard', 'action'), 'transitions': ('state',), 'checks': ('rule', 'case')}




def scan(cfg, texts=None):
    """Static screen/history facts, using the loader's literal-row validation."""
    texts = texts if texts is not None else {cfg.rel(p): p.read_text(encoding='utf-8-sig') for p in intent_files(cfg)}
    rules, errors, distincts, lines = {}, [], [], 0
    references, identifiers, distinct_calls, flow_calls, template_calls = [], {}, [], [], []
    def expanded(node, bindings, seen=()):
        if isinstance(node, ast.Name) and node.id in bindings and node.id not in seen:
            return expanded(bindings[node.id], bindings, (*seen, node.id))
        return node
    def items(node, bindings, seen=()):
        if isinstance(node, ast.Name) and node.id in bindings:
            return [node] if node.id in seen else items(bindings[node.id], bindings, (*seen, node.id))
        node = expanded(node, bindings)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return [child for value in node.elts for child in
                    (items(value.value, bindings, seen) if isinstance(value, ast.Starred) else [expanded(value, bindings)])]
        return [node] if node is not None else []
    def anchor_names(node, bindings):
        return [_literal(value) if isinstance(_literal(value), str) else 'unresolved:' + ast.unparse(value)
                for value in items(node, bindings)]
    for relative, text in sorted(texts.items()):
        lines += len(text.splitlines())
        try:
            tree = ast.parse(text, relative)
        except SyntaxError as error:
            errors.append(dict(file=relative, line=error.lineno or 0, msg=str(error)))
            continue
        errors.extend(literal_problems(tree, relative))
        aliases = api_aliases(tree)
        bindings = {target.id: node.value for node in tree.body if isinstance(node, ast.Assign)
                    for target in node.targets if isinstance(target, ast.Name)}
        names = {}
        imported = {}
        module = '.'.join(Path(relative).with_suffix('').parts)
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                prefix = module.split('.')[:-node.level] if node.level else []
                origin = '.'.join([*prefix, node.module or '']).strip('.')
                imported.update({a.asname or a.name: origin + '.' + a.name for a in node.names})
        for function in (n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            for decorator in function.decorator_list:
                if not isinstance(decorator, ast.Call) or api_call_name(decorator, aliases) not in {'rule', 'structure_rule'}:
                    continue
                id_node = decorator.args[0] if decorator.args else next((k.value for k in decorator.keywords if k.arg in {'id', 'identifier'}), None)
                identifier = _literal(id_node)
                if not isinstance(identifier, str):
                    continue
                values = {k.arg: _literal(k.value) for k in decorator.keywords}
                if identifier in rules:
                    errors.append(dict(file=relative, line=function.lineno, msg=f'duplicate declaration {identifier}'))
                names[function.name] = identifier
                identifiers[module + '.' + function.name] = identifier
                rules[identifier] = dict(id=identifier, decides=values.get('decides', 'structure'), source=values.get('source', ''),
                    kind='structure' if api_call_name(decorator, aliases) == 'structure_rule' else 'rule', file=relative, line=function.lineno, quote=values.get('quote'),
                    doc=ast.get_docstring(function) or '', rows=0, retired=0, homes=[], row_records=[],
                    uses=[], supersedes=[], overrides=[], total=values.get('total', False),
                    anchors=anchor_names(next((k.value for k in decorator.keywords if k.arg == 'anchor'), None), bindings))
                field_node = next((k.value for k in decorator.keywords if k.arg == 'fields'), None)
                rules[identifier]['fields'] = {_literal(key): ast.unparse(value) for key, value in zip(field_node.keys, field_node.values)} if isinstance(field_node, ast.Dict) else {}
                rules[identifier]['direct_anchors'] = list(rules[identifier]['anchors'])
                references.append((identifier, names, imported, {k.arg: k.value for k in decorator.keywords}))
        for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
            if api_call_name(call, aliases) == 'flow':
                keywords = {key.arg: key.value for key in call.keywords}
                identifier = _literal(call.args[0] if call.args else keywords.get('identifier'))
                if not isinstance(identifier, str):
                    errors.append(dict(file=relative, line=call.lineno, msg='flow id must be a literal'))
                    continue
                if identifier in rules:
                    errors.append(dict(file=relative, line=call.lineno, msg=f'duplicate declaration {identifier}'))
                rules[identifier] = dict(id=identifier, decides='flow', source=_literal(keywords.get('source'), ''),
                    kind='flow', file=relative, line=call.lineno, doc='', rows=0, retired=0,
                    homes=[], anchors=[], fields={}, row_records=[], uses=[], supersedes=[], overrides=[], total=False)
                flow_calls.append((identifier, names, imported, keywords, bindings, aliases))
            if api_call_name(call, aliases) in _TEMPLATES:
                template_calls.append((call, names, imported, relative, aliases))
            if api_call_name(call, aliases) == 'distinct':
                distinct_calls.append((call, names, imported, relative))
            if api_call_name(call, aliases) == 'states':
                target = _literal(call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == 'target'), None))
                if isinstance(target, str):
                    values = {k.arg: _literal(k.value) for k in call.keywords}
                    rules['states:' + target] = dict(id='states:' + target, decides=target, source=values.get('source', ''), kind='states',
                        file=relative, line=call.lineno, doc='', rows=0, retired=0, homes=[target], row_records=[], uses=[], supersedes=[])
            if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name):
                continue
            item = rules.get(names.get(call.func.value.id))
            if item is None:
                continue
            if call.func.attr != 'rows':
                continue
            def rows(node, seen=()):
                if isinstance(node, ast.Call) and api_call_name(node, aliases) == 'row':
                    return [node]
                if isinstance(node, ast.Starred):
                    return rows(node.value, seen)
                if isinstance(node, (ast.List, ast.Tuple)):
                    return [row for child in node.elts for row in rows(child, seen)]
                if isinstance(node, ast.Name) and node.id in bindings and node.id not in seen:
                    return rows(bindings[node.id], (*seen, node.id))
                errors.append(dict(file=relative, line=call.lineno, msg='row registration unresolved by AST: ' + ast.unparse(node)))
                return []
            for row in [row for argument in call.args for row in rows(argument)]:
                fields = {k.arg: ast.dump(k.value, include_attributes=False) for k in row.keywords if k.arg not in {'expect', 'why', 'retired'}}
                values = {k.arg: _literal(k.value) for k in row.keywords}
                retired = values.get('retired')
                expect = next((ast.dump(k.value, include_attributes=False) for k in row.keywords if k.arg == 'expect'), '')
                item['row_records'].append(dict(fields=fields, expect=expect, line=row.lineno, retired=retired, why=values.get('why', '')))
                item['retired' if retired else 'rows'] += 1
    def refs(node, names, imported):
        if isinstance(node, ast.Constant):
            return [node.value] if isinstance(node.value, str) else []
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return [value for child in node.elts for value in refs(child, names, imported)]
        if isinstance(node, ast.Name):
            return [names.get(node.id) or identifiers.get(imported.get(node.id)) or 'unresolved:' + node.id]
        return ['unresolved:' + ast.unparse(node)] if node is not None else []
    for identifier, names, imported, keywords in references:
        for field in ('uses', 'supersedes', 'overrides'):
            rules[identifier][field] = refs(keywords.get(field), names, imported)
    for identifier, names, imported, keywords, bindings, aliases in flow_calls:
        item = rules[identifier]
        nodes = {}
        lower_models = []
        unknown = []
        for value in items(keywords.get('nodes'), bindings):
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                nodes[value.value] = value.value
            elif isinstance(value, ast.Call) and api_call_name(value, aliases) == 'Node':
                arguments = {k.arg: expanded(k.value, bindings) for k in value.keywords}
                local = _literal(expanded(value.args[0] if value.args else arguments.get('name'), bindings))
                target = _literal(expanded(arguments.get('anchor') or (value.args[1] if len(value.args) > 1 else None), bindings)) or local
                if isinstance(local, str) and isinstance(target, str):
                    nodes[local] = target
                    lower_models.extend(refs(arguments.get('model'), names, imported))
                else:
                    unknown.append('node reference: ' + ast.unparse(value))
            else:
                unknown.append('node reference: ' + ast.unparse(value))
        item['nodes'] = nodes
        item['models'] = list(dict.fromkeys(lower_models))
        unknown.extend('lower model reference: ' + name for name in item['models'] if name not in rules)
        item['anchors'] = list(dict.fromkeys(nodes.values()))
        for value in items(keywords.get('transitions'), bindings):
            if isinstance(value, ast.Call) and api_call_name(value, aliases) == 'Transition':
                state = _literal(expanded(value.args[0] if value.args else next((k.value for k in value.keywords if k.arg == 'state'), None), bindings))
                if isinstance(state, str):item['anchors'].append(state)
        for value in items(keywords.get('relations'), bindings):
            if not isinstance(value, ast.Call) or api_call_name(value, aliases) != 'Relation':
                unknown.append('relation reference: ' + ast.unparse(value));continue
            arguments = {key.arg: expanded(key.value, bindings) for key in value.keywords}
            target = value.args[0] if value.args else arguments.get('rule')
            identifiers_ = refs(expanded(target, bindings), names, imported)
            inputs = expanded(value.args[1] if len(value.args) > 1 else arguments.get('inputs'), bindings)
            actual = expanded(value.args[2] if len(value.args) > 2 else arguments.get('actual'), bindings)
            trigger = _literal(expanded(value.args[3] if len(value.args) > 3 else arguments.get('on'), bindings))
            readings = list(inputs.values) if isinstance(inputs, ast.Dict) else []
            if inputs is not None and not isinstance(inputs, ast.Dict):
                unknown.append('input mapping: ' + ast.unparse(inputs))
            readings += [actual] if actual is not None and not (isinstance(actual, ast.Constant) and actual.value is None) else []
            node_names = [trigger] if isinstance(trigger, str) and trigger else []
            state_refs = []
            for read in readings:
                read = expanded(read, bindings)
                if isinstance(read, ast.Call) and api_call_name(read, aliases) == 'Read':
                    args = {k.arg:k.value for k in read.keywords}
                    name = _literal(expanded(read.args[0] if read.args else args.get('node'), bindings))
                    field = _literal(expanded(read.args[1] if len(read.args)>1 else args.get('field'), bindings))
                    if name == '$state':
                        if isinstance(field, str):state_refs.append(field)
                    elif isinstance(name, str):node_names.append(name)
                    if isinstance(field, str) and field.startswith('state.'):
                        state_refs.append(field.removeprefix('state.'))
                else:unknown.append('reading reference: ' + ast.unparse(read))
            anchors = list(dict.fromkeys([nodes[name] for name in node_names if name in nodes] + state_refs))
            item['anchors'] = list(dict.fromkeys(item['anchors'] + state_refs))
            unknown.extend('reading node: ' + name for name in node_names if name not in nodes)
            for rule_id in identifiers_:
                if rule_id not in rules:
                    unknown.append('relation rule: ' + rule_id);continue
                rule = rules[rule_id]
                rule['anchors'] = list(dict.fromkeys(rule.get('anchors', []) + anchors))
                rule.setdefault('flows', []).append(identifier)
        item['navigation_unknown'] = list(dict.fromkeys(unknown))
    for call, names, imported, relative, aliases in template_calls:
        # A one-line relation template is an ordinary Flow: its id, source and anchors as the API makes them.
        from .api import _template_id, _template_source
        kind = api_call_name(call, aliases)
        keywords = {key.arg: key.value for key in call.keywords if key.arg}
        parameters = _TEMPLATES[kind]
        arguments = [call.args[index] if len(call.args) > index else keywords.get(name) for index, name in enumerate(parameters)]
        if kind == 'checks':
            found = refs(arguments[0], names, imported)
            arguments[0] = ast.Constant(found[0]) if len(found) == 1 and not found[0].startswith('unresolved:') else arguments[0]
        values = [_literal(argument) for argument in arguments]
        if not all(isinstance(value, str) for value in values):
            errors.append(dict(file=relative, line=call.lineno, msg=f'{kind}() names must be literals or a rule'))
            continue
        identifier = _template_id(kind, *values)
        if identifier in rules:
            errors.append(dict(file=relative, line=call.lineno, msg=f'duplicate declaration {identifier}'))
        source = _literal(keywords.get('source'), None)
        anchors = values
        if kind == 'checks':
            # The decision read: `actual=`, else the rule's single anchor, else the anchor named like the rule.
            direct = rules.get(values[0], {}).get('direct_anchors', ())
            actual = _literal(keywords.get('actual'), None)
            anchors = [values[1], (actual if isinstance(actual, str) else direct[0] if len(direct) == 1 else values[0]).partition('.')[0]]
        rules[identifier] = dict(id=identifier, decides='flow', source=_template_source(kind, source if isinstance(source, str) else None, *values),
            kind='flow', file=relative, line=call.lineno, doc='', rows=0, retired=0, homes=[], anchors=list(dict.fromkeys(anchors)),
            fields={}, row_records=[], uses=[], supersedes=[], overrides=[], total=False, nodes={}, models=[], navigation_unknown=[])
        if kind == 'checks' and values[0] in rules:
            rule = rules[values[0]]
            rule['anchors'] = list(dict.fromkeys([*rule.get('anchors', []), *anchors[::-1]]))
            rule.setdefault('flows', []).append(identifier)
    for call, names, imported, relative in distinct_calls:
        keywords = {k.arg: k.value for k in call.keywords}
        arguments = {name: call.args[index] if len(call.args) > index else keywords.get(name)
                     for index, name in enumerate(('a', 'b', 'why', 'source'))}
        a, b = refs(arguments['a'], names, imported), refs(arguments['b'], names, imported)
        distincts.append(dict(a=a[0] if a else '', b=b[0] if b else '', why=_literal(arguments['why'], ''), source=_literal(arguments['source'], '')))
        if a and b and a[0] not in rules and b[0] not in rules:
            identifier = distinct_identifier(relative, a[0], b[0])
            rules[identifier] = dict(id=identifier, decides='distinct', kind='anchor_distinct', file=relative,
                line=call.lineno, source=_literal(arguments['source'], ''), doc=_literal(arguments['why'], ''),
                rows=0, retired=0, homes=[], anchors=[a[0], b[0]], fields={}, row_records=[], uses=[], supersedes=[], overrides=[], total=False)
    for item in rules.values():
        for old in item.get('supersedes', []):
            if old in rules:
                rules[old]['superseded_by'] = item['id']
    return dict(rules=rules, errors=errors, files=sorted(texts), intent_lines=lines, distincts=distincts)


def declaration_names(cfg, summary, *, deep=False):
    """Known failure-diagnostic items, without executing intent or application code.

    Scenario bindings require the loader's argument plan. Report that boundary
    instead of implementing a second binding resolver for a missing plugin.
    """
    from contextlib import closing
    from .anchors import collect
    from .loader import item_names
    from ..structure import build
    rules = summary['rules']
    index = None
    if any(rule.get('direct_anchors') for rule in rules.values()):
        with closing(build(cfg.root, roots=cfg.roots)) as graph:
            index = collect(graph)
    declared, unresolved = [], []
    for identifier, rule in rules.items():
        targets = list(rule.get('homes', ()))
        for name in rule.get('direct_anchors', ()):
            found = index.named(name, 'sensor') if index is not None else ()
            targets.extend(anchor.target for anchor in found)
            if not found:
                targets.append(name)
        declared.extend(item_names(identifier, dict.fromkeys(targets), kind=rule['kind'], deep=deep))
        if rule.get('flows'):
            unresolved.append(identifier)
    return declared, unresolved


# flowguard: event CHECK_RESULTS(cfg: Config)
def observations(cfg):
    """Read the last historical observation view only when explicitly requested."""
    path = cfg.cache / 'map.sqlite'
    if not path.is_file():
        return {}
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone():
            return {}
        row = con.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()
    if row is None:
        return {}
    try:
        value = json.loads(row[0])
        if not isinstance(value, dict):
            raise ValueError('expected an observation object')
        return value
    except (ValueError, TypeError) as error:
        from flowguard.map.common import MapError
        raise MapError('historical observations could not be read; run tests to rebuild them') from error


def read(cfg: Config):
    """One SQLite source; a latest failed attempt stays separate from the last full collection."""
    summary = scan(cfg)
    output = dict(summary=summary, results={}, deps={}, attempt=None, collection=None, tests={}, test_deps={}, traces={}, test_collection={})
    path = cfg.cache / 'map.sqlite'
    if not path.is_file():
        return output
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as con, con:
        con.execute('BEGIN')
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        names = ('intent_attempt', 'intent_collection', 'intent_dependencies', 'ordinary_collection')
        metadata = dict(con.execute('SELECT k,v FROM meta WHERE k IN (?,?,?,?)', names)) if 'meta' in tables else {}
        for key, name in [('attempt', 'intent_attempt'), ('collection', 'intent_collection'), ('deps', 'intent_dependencies'), ('test_collection', 'ordinary_collection')]:
            if name in metadata:
                output[key] = json.loads(metadata[name])
        if 'test_dependency' in tables:
            output['test_deps'] = {file: dict(group=group, unknown=bool(unknown))
                                   for file, group, unknown in con.execute('SELECT * FROM test_dependency')}
        if 'result' in tables:
            for nodeid, rid, verdict, payload, stamp in con.execute('SELECT item,rule,verdict,payload,stamp FROM result'):
                output['results'].setdefault(rid, {'items': {}})['items'][nodeid] = json.loads(payload)
        if 'reading' in tables:
            output['tests'] = {r[0]: dict(zip(('outcome', 'kind', 'reason', 'phase', 'seconds', 'stamp'), r[1:]))
                               for r in con.execute('SELECT * FROM reading')}
        # Keep raw readings for audit, but an obsolete function/parameter from a
        # completed file collection is not a current failure. A newer partial
        # run remains visible even when its node was not in that older snapshot.
        readings = output['tests']
        def current(test):
            saved = output['test_collection'].get(test.partition('::')[0])
            return (not saved or test in saved['tests']
                    or readings.get(test, {}).get('stamp', 0) >= saved['stamp'])
        output['tests'] = {test: value for test, value in readings.items() if current(test)}
    return output


def _write_transaction(con):
    if not con.in_transaction:
        con.execute('BEGIN IMMEDIATE')


def save_test_collection(con, files, stamp):
    """Merge only actually completed ordinary file collections into this SQLite."""
    if not files:
        return
    _write_transaction(con)
    row = con.execute("SELECT v FROM meta WHERE k='ordinary_collection'").fetchone()
    current = json.loads(row[0]) if row else {}
    current.update({file: dict(tests=sorted(tests), stamp=stamp) for file, tests in files.items()})
    put_meta(con, 'ordinary_collection', json.dumps(current, sort_keys=True))


STRUCTURE = 'structure_issues'


def save_structure(con, summary):
    """The open structure problems' count and heaviest names (`health.summary`), for the session brief."""
    put_meta(con, STRUCTURE, json.dumps(summary, ensure_ascii=False))


def structure_summary(cfg):
    """The last saved structure summary, read without building the map; None when no check saved one."""
    path = cfg.cache / 'map.sqlite'
    if not path.is_file():
        return None
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone():
            return None
        row = con.execute('SELECT v FROM meta WHERE k = ?', (STRUCTURE,)).fetchone()
    return json.loads(row[0]) if row else None


COMPARISONS = 'CREATE TABLE IF NOT EXISTS comparison(key TEXT PRIMARY KEY, baseline TEXT, payload TEXT)'


def comparisons(cfg, baseline):
    """The anchor comparisons an earlier session stored against this baseline, by fingerprint key."""
    path = cfg.cache / 'map.sqlite'
    if not path.is_file():
        return {}
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='comparison'").fetchone():
            return {}
        return dict(con.execute('SELECT key,payload FROM comparison WHERE baseline=?', (baseline,)))


def save_comparisons(con, baseline, entries):
    """Keep the comparisons of the current baseline only; an older baseline's keys can never match again."""
    _write_transaction(con)
    con.execute(COMPARISONS)
    con.execute('DELETE FROM comparison WHERE baseline!=?', (baseline,))
    con.executemany('INSERT OR REPLACE INTO comparison VALUES(?,?,?)',
                    [(key, baseline, payload) for key, payload in entries.items()])


def save_dependencies(con, records):
    _write_transaction(con)
    row = con.execute("SELECT v FROM meta WHERE k='intent_dependencies'").fetchone()
    existing = json.loads(row[0]) if row else {}
    existing.update(records)
    put_meta(con, 'intent_dependencies', json.dumps(existing, sort_keys=True))


def standard_dependencies(record):
    from .deps import standard_keys
    return standard_keys(record)


def _group_identity(dependencies):
    encoded = json.dumps(sorted(dependencies.items()), separators=(',', ':'), ensure_ascii=False).encode()
    return content_digest(Path('dependency-group'), data=encoded)


def test_signature(record):
    return dict(group=_group_identity(standard_dependencies(record)), unknown='<unresolved>' in record)


def save_test_dependencies(con, records):
    """Store the existing file digest directly, without per-test trace ledgers."""
    _write_transaction(con)
    con.execute('CREATE TABLE IF NOT EXISTS test_dependency(file TEXT PRIMARY KEY, group_id TEXT, unknown INT)')
    con.executemany('INSERT OR REPLACE INTO test_dependency VALUES(?,?,?)',
                    [(file, test_signature(record)['group'], '<unresolved>' in record)
                     for file, record in records.items()])


def save_proven(con, rule, proofs):
    """Attach old-code evidence to an already checked rule, using the existing result payload."""
    _write_transaction(con)
    from .history import current_row_signature
    rows = con.execute('SELECT item,payload FROM result WHERE rule=? ORDER BY item', (rule.id,)).fetchall()
    if not rows:
        return False
    chosen = next(((item, payload) for item, payload in rows if json.loads(payload).get('kind') == 'rules'), rows[0])
    item, encoded = chosen
    payload = json.loads(encoded)
    signatures = {current_row_signature(rule, row) for row in rule.live_rows}
    valid = {proof['signature']: proof for proof in payload.get('proven_rows', []) + list(proofs)
             if proof.get('status') == 'proven' and proof.get('signature') in signatures}
    payload['proven_rows'] = list(valid.values())
    con.execute('UPDATE result SET payload=? WHERE item=?', (json.dumps(payload, sort_keys=True), item))
    return True
