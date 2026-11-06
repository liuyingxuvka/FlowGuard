"""Read the existing map cache and declaration facts without importing project code."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import sqlite3

from .config import intent_files
from .loader import api_aliases, api_call_name, literal_problems
from flowguard.map.common import content_digest


def _literal(node, default=None):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return default


def scan(cfg, texts=None):
    """Static screen/history facts, using the loader's literal-row validation."""
    texts = texts if texts is not None else {cfg.rel(p): p.read_text(encoding='utf-8-sig') for p in intent_files(cfg)}
    rules, errors, distincts, lines = {}, [], [], 0
    references, identifiers, distinct_calls = [], {}, []
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
                    kind='structure' if api_call_name(decorator, aliases) == 'structure_rule' else 'rule', file=relative, line=function.lineno,
                    doc=ast.get_docstring(function) or '', rows=0, retired=0, homes=[], row_records=[],
                    uses=[], supersedes=[], overrides=[], total=values.get('total', False))
                field_node = next((k.value for k in decorator.keywords if k.arg == 'fields'), None)
                rules[identifier]['fields'] = {_literal(key): ast.unparse(value) for key, value in zip(field_node.keys, field_node.values)} if isinstance(field_node, ast.Dict) else {}
                references.append((identifier, names, imported, {k.arg: k.value for k in decorator.keywords}))
        for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
            if api_call_name(call, aliases) == 'distinct':
                distinct_calls.append((call, names, imported))
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
            if call.func.attr == 'home':
                target = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == 'target'), None)
                item['homes'].append(_literal(target, 'unresolved:' + ast.unparse(target) if target else 'unresolved:home'))
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
    for call, names, imported in distinct_calls:
        keywords = {k.arg: k.value for k in call.keywords}
        arguments = {name: call.args[index] if len(call.args) > index else keywords.get(name)
                     for index, name in enumerate(('a', 'b', 'why', 'source'))}
        a, b = refs(arguments['a'], names, imported), refs(arguments['b'], names, imported)
        distincts.append(dict(a=a[0] if a else '', b=b[0] if b else '', why=_literal(arguments['why'], ''), source=_literal(arguments['source'], '')))
    for item in rules.values():
        for old in item.get('supersedes', []):
            if old in rules:
                rules[old]['superseded_by'] = item['id']
    return dict(rules=rules, errors=errors, files=sorted(texts), intent_lines=lines, distincts=distincts)


def read(cfg):
    """One SQLite source; a latest failed attempt stays separate from the last full collection."""
    summary = scan(cfg)
    output = dict(summary=summary, results={}, deps={}, attempt=None, collection=None, tests={}, test_deps={}, traces={})
    path = cfg.cache / 'map.sqlite'
    if not path.is_file():
        return output
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as con:
        con.execute('BEGIN')
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        names = ('intent_attempt', 'intent_collection', 'intent_dependencies')
        metadata = dict(con.execute('SELECT k,v FROM meta WHERE k IN (?,?,?)', names)) if 'meta' in tables else {}
        for key, name in [('attempt', 'intent_attempt'), ('collection', 'intent_collection'), ('deps', 'intent_dependencies')]:
            if name in metadata:
                output[key] = json.loads(metadata[name])
        if 'trace_test' in tables:
            output['traces'] = {test: dict(groups=[static, observed], unknown=bool(unknown))
                                for test, static, observed, unknown in con.execute('SELECT * FROM trace_test')}
        if 'test_dependency' in tables:
            output['test_deps'] = {file: dict(group=group, unknown=bool(unknown))
                                   for file, group, unknown in con.execute('SELECT * FROM test_dependency')}
        if 'result' in tables:
            for nodeid, rid, verdict, payload, stamp in con.execute('SELECT item,rule,verdict,payload,stamp FROM result'):
                output['results'].setdefault(rid, {'items': {}})['items'][nodeid] = json.loads(payload)
        if 'reading' in tables:
            output['tests'] = {r[0]: dict(zip(('outcome', 'kind', 'reason', 'phase', 'seconds', 'stamp'), r[1:]))
                               for r in con.execute('SELECT * FROM reading')}
    return output


def _write_transaction(con):
    if not con.in_transaction:
        con.execute('BEGIN IMMEDIATE')


def save_dependencies(con, records):
    _write_transaction(con)
    row = con.execute("SELECT v FROM meta WHERE k='intent_dependencies'").fetchone()
    existing = json.loads(row[0]) if row else {}
    existing.update(records)
    con.execute('INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)', ('intent_dependencies', json.dumps(existing, sort_keys=True)))


def standard_dependencies(record):
    return {('engine:' if path == '<engine>' else 'file:' + path): value
            for path, value in record.items() if path != '<unresolved>'}


def _group_identity(dependencies):
    encoded = json.dumps(sorted(dependencies.items()), separators=(',', ':'), ensure_ascii=False).encode()
    return content_digest(Path('dependency-group'), data=encoded)


def test_signature(record):
    return dict(group=_group_identity(standard_dependencies(record)), unknown='<unresolved>' in record)


class _Signatures:
    """Intern immutable dependency values and sets in the existing SQLite cache."""
    def __init__(self, con):
        _write_transaction(con)
        self.con, self.shared = con, {}
        for sql in (
            'CREATE TABLE IF NOT EXISTS trace_value(id INTEGER PRIMARY KEY, key TEXT, digest TEXT, UNIQUE(key,digest))',
            'CREATE TABLE IF NOT EXISTS trace_group(id TEXT PRIMARY KEY, refs TEXT)',
            'CREATE TABLE IF NOT EXISTS trace_test(test TEXT PRIMARY KEY, static_group TEXT, observed_group TEXT, unknown INT)',
            'CREATE TABLE IF NOT EXISTS test_dependency(file TEXT PRIMARY KEY, group_id TEXT, unknown INT)',
        ):
            con.execute(sql)
        self.values = {(key, digest): identifier for identifier, key, digest in con.execute('SELECT * FROM trace_value')}
        self.groups = {row[0] for row in con.execute('SELECT id FROM trace_group')}

    def group(self, dependencies, *, shared=False):
        if shared and id(dependencies) in self.shared:
            return self.shared[id(dependencies)][1]
        identifier = _group_identity(dependencies)
        if identifier not in self.groups:
            refs = []
            for pair in sorted(dependencies.items()):
                if pair not in self.values:
                    cursor = self.con.execute('INSERT INTO trace_value(key,digest) VALUES(?,?)', pair)
                    self.values[pair] = cursor.lastrowid
                refs.append(self.values[pair])
            self.con.execute('INSERT INTO trace_group VALUES(?,?)', (identifier, json.dumps(refs, separators=(',', ':'))))
            self.groups.add(identifier)
        if shared:
            # Pin the shared mapping: an unpinned dict id could be reused by a later test.
            self.shared[id(dependencies)] = dependencies, identifier
        return identifier

    def finish(self):
        cursor = self.con.execute('DELETE FROM trace_group WHERE id NOT IN '
            '(SELECT static_group FROM trace_test UNION SELECT observed_group FROM trace_test UNION SELECT group_id FROM test_dependency)')
        if cursor.rowcount:
            used = {value for (refs,) in self.con.execute('SELECT refs FROM trace_group') for value in json.loads(refs)}
            self.con.executemany('DELETE FROM trace_value WHERE id=?', [(value,) for value in self.values.values() if value not in used])
        # Legacy repeated JSON is ignored, not rewritten or copied here. Removing
        # a very large old blob would itself need a large rollback journal.


def save_test_dependencies(con, records):
    store = _Signatures(con)
    for file, record in records.items():
        group = store.group(standard_dependencies(record))
        con.execute('INSERT OR REPLACE INTO test_dependency VALUES(?,?,?)', (file, group, '<unresolved>' in record))
    store.finish()


def save_trace_signatures(con, records, drop=()):
    """A new reading without a new recording invalidates that test's old evidence."""
    store = _Signatures(con)
    for removed in drop:
        con.execute('DELETE FROM trace_test WHERE test=? OR substr(test,1,?)=?', (removed, len(removed) + 2, removed + '::'))
    for test, record in records.items() if isinstance(records, dict) else records:
        static = store.group(record['static'], shared=True)
        observed = store.group(record['observed'])
        con.execute('INSERT OR REPLACE INTO trace_test VALUES(?,?,?,?)', (test, static, observed, record['unknown']))
    store.finish()


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
