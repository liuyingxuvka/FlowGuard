"""Vitest records real primitive calls; after tests, Python judges source-only sealed comparisons.

The Vite transform never imports baseline or copy modules. Python reads their source with the existing
reader, passes extracted functions to a separate Node vm, and reports through the shared signals owner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import time
from pathlib import Path

from .config import INIT_MARK, RECORDED_PYTHON

ADAPTER = Path(__file__).resolve().parents[1] / 'adapters' / 'vitest'
LIMIT = 64                                       # same-name inputs, after the real tests
STRING_CONTEXTS = frozenset({'compare', 'case', 'member', 'set'})
WRAPPABLE = ('function_declaration', 'generator_function_declaration')


# ---- prepare ----------------------------------------------------------------------------------------

def _ecma(rel):
    from ..structure.readers.registry import ECMA, language_for
    return language_for(rel) in ECMA


def _changed(cfg, commit):
    """The TS/JS files the working tree changed against the baseline commit, untracked ones included."""
    import os
    from ..map.common import git_run
    changed = git_run(cfg.root, 'diff', '--name-only', '-z', commit).stdout
    added = git_run(cfg.root, 'ls-files', '--others', '--exclude-standard', '-z').stdout
    return sorted({os.fsdecode(value) for value in (changed + added).split(b'\0')
                   if value and _ecma(os.fsdecode(value)) and b'node_modules/' not in value})


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _key(cfg, commit, changed, kind):
    """The plan's fingerprint; `kind` is part of it, as the plan's title says whether its commit is a recorded
    task start or HEAD."""
    from ..structure.store import reader_digest
    own = [Path(__file__), *sorted(ADAPTER.glob('*.mjs'))]
    parts = [commit, kind, reader_digest(), *(_digest(path.read_bytes()) for path in own)]
    for rel in changed:
        path = cfg.root / rel
        parts.append(rel + ':' + (_digest(path.read_bytes()) if path.is_file() else 'deleted'))
    return _digest('\n'.join(parts).encode())[:20]


def _parameters(node, source):
    from ..structure.readers.common import text
    params = node.child_by_field_name('parameters')
    if params is None:
        single = node.child_by_field_name('parameter')
        return [text(single, source)] if single is not None else []
    names = []
    for index, item in enumerate(item for item in params.named_children if item.type != 'comment'):
        pattern = item.child_by_field_name('pattern') or item.child_by_field_name('name') or item
        names.append(text(pattern, source) if pattern.type == 'identifier' else f'arg{index}')
    return names


def declarations(data, rel):
    """{name: facts} of the module-level functions the adapter can wrap: `function f` and `const f = (...) =>`
    (also `export`ed). `line` is the line of the statement the plugin edits."""
    from ..structure.readers.common import parse, text
    from ..structure.readers.registry import language_for
    source, tree = parse(data, language_for(rel))
    found = {}
    for statement in tree.root_node.named_children:
        inner = statement.child_by_field_name('declaration') if statement.type == 'export_statement' else statement
        if inner is None:
            continue
        if inner.type in WRAPPABLE:
            name = text(inner.child_by_field_name('name'), source)
            found.setdefault(name, dict(form='function', line=inner.start_point.row + 1, node=inner,
                                        params=_parameters(inner, source), is_async=text(inner, source).startswith('async')))
        elif inner.type == 'lexical_declaration' and text(inner, source).startswith('const'):
            for declarator in inner.named_children:
                value = declarator.child_by_field_name('value')
                name = declarator.child_by_field_name('name')
                if declarator.type == 'variable_declarator' and value is not None and name is not None \
                        and value.type in ('arrow_function', 'function_expression', 'function'):
                    found.setdefault(text(name, source), dict(form='const', line=declarator.start_point.row + 1, node=value,
                                                              params=_parameters(value, source),
                                                              is_async=text(value, source).startswith('async')))
    return found


def sealed_source(data, rel, name):
    """Only the selected function, same-file helpers, and literal constants; never module imports."""
    from ..structure.readers.common import parse, text, walk
    from ..structure.readers.registry import language_for
    source, tree = parse(data, language_for(rel))
    found = declarations(data, rel)
    constants, blocked = {}, set()
    for statement in tree.root_node.named_children:
        inner = statement.child_by_field_name('declaration') if statement.type == 'export_statement' else statement
        if inner is None:
            continue
        if inner.type == 'import_statement':
            clause = next((child for child in inner.named_children if child.type == 'import_clause'), None)
            for item in clause.named_children if clause is not None else ():
                if item.type == 'identifier':
                    blocked.add(text(item, source))
                elif item.type == 'namespace_import':
                    blocked.add(text(item.named_children[-1], source))
                else:
                    for spec in item.named_children:
                        alias = spec.child_by_field_name('alias') or spec.child_by_field_name('name')
                        if alias is not None:
                            blocked.add(text(alias, source))
        if inner.type in ('class_declaration', 'abstract_class_declaration', 'enum_declaration', 'internal_module'):
            name_node = inner.child_by_field_name('name')
            if name_node is not None:
                blocked.add(text(name_node, source))
        if inner.type not in ('lexical_declaration', 'variable_declaration'):
            continue
        immutable = text(inner, source).startswith('const')
        for item in inner.named_children:
            key, value = item.child_by_field_name('name'), item.child_by_field_name('value')
            if key is not None and immutable and key.type == 'identifier' and value is not None:
                constants[text(key, source)] = value
            elif key is not None:
                blocked.update(text(child, source) for child in walk(key)
                               if child.type in ('identifier', 'shorthand_property_identifier_pattern'))
    pending_bindings = list(tree.root_node.named_children)
    while pending_bindings:
        node = pending_bindings.pop()
        if node.type in ('function_declaration', 'generator_function_declaration', 'arrow_function', 'function_expression',
                         'function', 'class_declaration', 'abstract_class_declaration'):
            continue
        if node.type == 'variable_declarator' and node.parent.type == 'variable_declaration':
            key = node.child_by_field_name('name')
            if key is not None:
                blocked.update(text(child, source) for child in walk(key) if child.type == 'identifier')
        if node.type in ('assignment_expression', 'augmented_assignment_expression', 'update_expression'):
            target = node.child_by_field_name('left') or node.child_by_field_name('argument')
            while target is not None and target.type in ('member_expression', 'subscript_expression'):
                target = target.child_by_field_name('object')
            if target is not None and target.type == 'identifier':
                blocked.add(text(target, source))
        pending_bindings.extend(node.named_children)
    module_names = found.keys() | constants.keys() | blocked
    for node in walk(tree.root_node):
        if node.type in ('assignment_expression', 'augmented_assignment_expression', 'update_expression'):
            target = node.child_by_field_name('left') or node.child_by_field_name('argument')
            while target is not None and target.type in ('member_expression', 'subscript_expression'):
                target = target.child_by_field_name('object')
            if target is not None and target.type == 'identifier' and text(target, source) in module_names:
                blocked.add(text(target, source))
    if name not in found:
        return '', 'only module-level functions can be compared'
    omitted = {'type_annotation', 'type_parameters', 'type_arguments'}
    wrappers = {'as_expression', 'satisfies_expression', 'non_null_expression'}
    forbidden = {'enum_declaration', 'internal_module', 'decorator', 'jsx_element', 'jsx_self_closing_element', 'meta_property',
                 'accessibility_modifier', 'readonly', 'this', 'await_expression', 'yield_expression'}
    def stripped(node):
        if node.type in omitted or (node.type == '?' and node.parent.type == 'optional_parameter'):
            return ''
        if node.type in wrappers:
            return stripped(node.named_children[0])
        parts, at = [], node.start_byte
        for child in node.children:
            parts.extend((source[at:child.start_byte].decode(), stripped(child)))
            at = child.end_byte
        parts.append(source[at:node.end_byte].decode())
        return ''.join(parts)
    def literal(node):
        if node.type in wrappers:
            return literal(node.named_children[0])
        if node.type in ('string', 'number', 'true', 'false', 'null'):
            return True
        if node.type in ('array', 'object', 'pair'):
            return all(literal(child) or child.type == 'property_identifier' for child in node.named_children)
        return node.type == 'unary_expression' and text(node, source)[:1] in '+-' and all(literal(child) for child in node.named_children)
    # Reuse the reader's literal folder, without admitting calls, attributes or dynamic bindings.
    import ast
    from ..structure import features
    from ..structure.api import _expression
    folded, environment = {}, {}
    arithmetic = (ast.Constant, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp,
                  ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd)
    def number_ast(node):
        if isinstance(node, ast.BinOp):
            return ast.BinOp(number_ast(node.left), node.op, number_ast(node.right))
        if isinstance(node, ast.UnaryOp):
            return ast.UnaryOp(node.op, number_ast(node.operand))
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return ast.Constant(float(node.value))
        return node
    for constant, node in constants.items():
        expression = _expression(stripped(node))
        if constant in blocked or expression is None or any(not isinstance(part, arithmetic) for part in ast.walk(expression)):
            continue
        numeric = [part for part in ast.walk(expression) if isinstance(part, ast.Constant) and type(part.value) in (int, float)]
        if any(abs(part.value) > sys.float_info.max for part in numeric):
            continue
        # Preserve the reader's cached AST; JS Number rounds each step, not only the final value.
        value = features.fold(number_ast(expression), environment, {})
        if value is not None and (value[0] == 'str' or value[0] == 'num' and math.isfinite(value[1])):
            environment[constant] = value
            primitive = value[1]
            if type(primitive) is float and primitive.is_integer() and not (primitive == 0 and math.copysign(1, primitive) < 0):
                primitive = int(primitive)
            folded[constant] = json.dumps(primitive, ensure_ascii=False)
    pending, used, pieces = [name], set(), []
    while pending:
        current = pending.pop()
        if current in used:
            continue
        used.add(current)
        if current in blocked:
            return '', 'uses imported or mutable binding ' + current
        if current in found:
            function = found[current]
            node = function['node']
            bad = next((child.type for child in walk(node) if child.type in forbidden), None)
            shadowed = sorted({text(child, source) for child in walk(node)
                               if child.type in ('identifier', 'shorthand_property_identifier') and text(child, source) in blocked})
            if shadowed:
                return '', 'uses imported or mutable binding ' + shadowed[0]
            if function['is_async'] or 'generator' in node.type or bad:
                return '', 'unsupported ' + (bad or 'async or generator')
            code = stripped(node)
            pieces.append(code if function['form'] == 'function' else f'const {current} = {code};')
            pending.extend(text(child, source) for child in walk(node)
                           if child.type == 'identifier' and text(child, source) in found.keys() | constants.keys())
        else:
            node = constants[current]
            if current in folded:
                pieces.append(f'const {current} = {folded[current]};')
            elif literal(node):
                pieces.append(f'const {current} = {stripped(node)};')
            else:
                return '', 'uses nonliteral constant ' + current
    return '\n'.join(reversed(pieces)), ''


def _top_level(qual):
    return '.' not in qual and not qual.startswith('<')


def _constants_changed(before, now):
    """Names of module constants (`const NAME = literal`, `const TABLE = {...}`) whose value this change altered."""
    def values(facts):
        found = {row['qual']: row['sig'] for row in facts['nodes'] if row['kind'] == 'const' and '.' not in row['qual']}
        found.update({row['name']: json.dumps(row['values'], sort_keys=True) for row in facts.get('const_tables', ())})
        return found
    old, new = values(before), values(now)
    return {name for name in old.keys() | new.keys() if old.get(name) != new.get(name)}


def plan(cfg, commit, changed, key):
    """The points to observe and everything the Node adapter needs, as one JSON-ready dict."""
    from contextlib import closing
    from ..map.common import git_blob
    from ..structure import build
    from ..structure.extract import extract
    from .anchors import collect
    from .config import is_test_rel
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        index = collect(graph)
        owners = {anchor.target for anchor in index.entries if anchor.owner}
        modules = {row['file']: row['module'] for row in graph.nodes(kind='module')}
        wanted = {}                     # id -> (name, anchored, rel, qual)
        for anchor in index.entries:
            if anchor.kind == 'sensor' and _ecma(anchor.file) and anchor.source_role != 'test':
                wanted[anchor.target] = (anchor.name, True, anchor.file, anchor.qual)
        old_sources, readers = {}, {}
        for rel in changed:
            if rel not in modules or is_test_rel(rel) or not (cfg.root / rel).is_file():
                continue
            if (cfg.root / rel).read_text(encoding='utf-8-sig').startswith(INIT_MARK):
                continue  # FlowGuard's generated wiring is not an application probe.
            old = git_blob(cfg.root, commit, rel)
            old_sources[rel] = old
            before = extract(cfg.root, rel, old, modules[rel], False) if old is not None else dict(nodes=[], const_tables=[])
            now = extract(cfg.root, rel, (cfg.root / rel).read_bytes(), modules[rel], False)
            prior = {row['qual']: row['fp'] for row in before['nodes']}
            for row in now['nodes']:
                ident = modules[rel] + ':' + row['qual']
                if row['kind'] == 'function' and _top_level(row['qual']) and prior.get(row['qual']) != row['fp'] and ident not in wanted:
                    wanted[ident] = (row['qual'], False, rel, row['qual'])
            names = _constants_changed(before, now)
            if names:               # like the pytest side: a function reading a changed constant changed too
                readers.setdefault(rel, set()).update(names)
                for row in graph.imports(declarations=True):
                    if row.get('kind') == 'import' and row['dst'] == modules[rel] and row.get('name') in names and row.get('alias'):
                        readers.setdefault(row['file'], set()).add(row['alias'])
        for rel, names in readers.items():
            if rel not in modules or is_test_rel(rel):
                continue
            lines = (cfg.root / rel).read_text(encoding='utf-8').splitlines()
            spelled = re.compile(r'\b(?:' + '|'.join(map(re.escape, sorted(names))) + r')\b')
            for row in graph.nodes(file=rel):
                if row['kind'] == 'function' and _top_level(row['qual']) and row['id'] not in wanted \
                        and spelled.search('\n'.join(lines[row['line'] - 1:row['end_line']])):
                    wanted[row['id']] = (row['qual'], False, rel, row['qual'])
        numbers, strings = {}, {}
        for row in graph.numbers():
            numbers.setdefault((row['file'], row['function']), []).append(row['value'])
        for row in graph.literals(contexts=STRING_CONTEXTS):
            if isinstance(row['value'], str):
                strings.setdefault((row['file'], row['function']), []).append(row['value'])
        for row in graph.lookup_keys():
            strings.setdefault((row['file'], row['function']), []).extend(row['keys'])
        parsed, points, unplanned = {}, [], []
        for ident, (name, anchored, rel, qual) in sorted(wanted.items()):
            if rel not in parsed:
                parsed[rel] = declarations((cfg.root / rel).read_bytes(), rel)
            found = parsed[rel].get(qual)
            line = graph.node(ident)['line'] if graph.node(ident) else 0
            if found is None:
                unplanned.append(dict(id=ident, name=name, rel=rel, line=line,
                                      reason='only module-level function f and const f = (...) => are observed; this function is not wrapped'))
                continue
            closed, skip = sealed_source((cfg.root / rel).read_bytes(), rel, qual)
            from ..structure.readers.common import parse, walk, text
            from ..structure.readers.ecma import literal
            code, closed_tree = parse(closed.encode(), 'javascript')
            extra_numbers = []
            for token in walk(closed_tree.root_node):
                valid, number = literal(token, code) if token.type == 'number' else (False, None)
                if valid and type(number) in (int, float) and math.isfinite(number):
                    if token.parent.type == 'unary_expression' and text(token.parent, code).startswith('-'):
                        number = -number
                    extra_numbers.append(number)
            old = old_sources.get(rel) if rel in old_sources else git_blob(cfg.root, commit, rel)
            prior, old_skip = (sealed_source(old, rel, qual) if old is not None and qual in declarations(old, rel)
                               else ('', 'function absent at baseline'))
            points.append(dict(id=ident, name=name, anchored=anchored, owner=ident in owners, rel=rel, file=(cfg.root / rel).as_posix(), fn=qual,
                               line=found['line'], target_line=line, form=found['form'], params=found['params'], skip=skip,
                               recordable=(not found['is_async'] and 'generator' not in found['node'].type
                                           and skip != 'uses imported or mutable binding ' + qual),
                               source=closed, old_source=prior, old_skip=old_skip,
                               changed=(rel in changed and (old is None or closed != prior)),
                               consts=numbers.get((rel, qual), []) + extra_numbers, labels=sorted(set(strings.get((rel, qual), [])))))
    groups = {}
    for point in points:
        if point['anchored']:
            groups.setdefault(point['name'], []).append(point)
    files = {}
    from .cells import OTHER
    shared = {point['id']: (list(point['consts']), list(point['labels'])) for point in points}
    for point in points:
        peers = [other for other in groups.get(point['name'], ()) if other is not point] if point['anchored'] else []
        consts = point.pop('consts') + [value for other in peers for value in shared[other['id']][0]]
        labels = sorted(set(point.pop('labels')).union(*(shared[other['id']][1] for other in peers)))
        point.update(numbers=sorted({value for value in consts if type(value) in (int, float) and math.isfinite(value)}), strings=labels + [OTHER] if labels else [],
                     bounds=sorted({value for value in consts if isinstance(value, (int, float)) and not isinstance(value, bool)}),
                     copies=[dict(id=other['id'], fn=other['fn'], params=other['params'])
                             for other in peers])
    for point in points:
        files.setdefault(point['file'], dict(points=[]))['points'].append(point)
    return dict(key=key, root=cfg.root.as_posix(), baseline=commit, limit=LIMIT, files=files, unplanned=unplanned)


def prepare(root):
    """{'status': 'off', 'reason'} without a TS/JS change, else {'status': 'on', 'plan', 'adapter'}."""
    from . import cache
    from .config import load_config
    from ..map.common import atomic_write_text, git_common_directory, git_run
    started = time.perf_counter()
    def answer(**values):
        return dict(values, seconds=time.perf_counter() - started)
    cfg = load_config(root)
    if git_common_directory(cfg.root) is None:
        return answer(status='off', reason='not a git repository: no baseline commit; execution comparison is off')
    # vitest records no baseline: before the first `check --static` (or pytest, or the brief) of a task, HEAD
    # stands in, and the title says so.
    baseline, kind = cache.task_baseline(cfg)
    if kind == 'missing':
        return answer(status='off', reason=f'recorded task baseline {baseline[:7]} is not in this repository: execution comparison is off; first run python -m flowguard new-task')
    found = git_run(cfg.root, 'rev-parse', '-q', '--verify', (baseline or 'HEAD') + '^{commit}', allowed=(0, 1))
    if found.returncode:
        return answer(status='off', reason='no commits yet: no baseline; execution comparison is off')
    commit = found.stdout.decode().strip()
    changed = _changed(cfg, commit)
    # Same-name functions are always planned, including runs without a source change.
    key = _key(cfg, commit, changed, kind)
    path = cfg.cache / 'vitest' / f'plan-{key}.json'
    if not path.is_file():
        data = plan(cfg, commit, changed, key)
        data['baseline_kind'] = kind
        path.parent.mkdir(parents=True, exist_ok=True)
        for old in path.parent.glob('plan-*.json'):
            old.unlink()                # one current plan; an older one belongs to another change
    else:
        data = json.loads(path.read_text(encoding='utf-8'))
    data['prepare_seconds'] = time.perf_counter() - started
    atomic_write_text(path, json.dumps(data, ensure_ascii=False))
    if not data['files'] and not data['unplanned']:
        return dict(status='off', reason='no functions to observe in this change (anchors or changed module-level functions)',
                    seconds=data['prepare_seconds'])
    return dict(status='on', plan=path.as_posix(), adapter=(ADAPTER / 'index.mjs').as_posix(), seconds=data['prepare_seconds'])


# ---- init: wire the plugin into the vitest config ---------------------------------------------------

GENERATED = INIT_MARK + ': FlowGuard\'s execution side for vitest (minimal: vitest, ESM).'
MODULE = GENERATED + '''
// The vitest config imports this file and lists flowguard() in its plugins: two lines marked `flowguard: vitest`.
// Delete those two lines to undo. Only a vitest run loads FlowGuard (vitest sets VITEST before it reads the
// config): `vite build`, `vite` and `vite preview` get no plugin and start no Python, so the software itself is
// never changed. In a vitest run it records functions marked `flowguard: same NAME` and changed functions;
// without either it adds nothing. Comparison runs after the tests, and FlowGuard's lines follow
// the test summary. Python is found as flowguard.static.test.mjs finds it: FLOWGUARD_PYTHON, then the
// interpreter that ran `flowguard init` on this machine, recorded in @RECORDED@ (git-ignored), then `python3`,
// `python` and, on Windows, `py -3`.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), @ROOT@);
const RECORDED = path.join(ROOT, ...@RECORDED@.split('/'));

function interpreters() {
  if (process.env.FLOWGUARD_PYTHON) return [[process.env.FLOWGUARD_PYTHON]];
  const listed = fs.existsSync(RECORDED) ? [[fs.readFileSync(RECORDED, 'utf8').trim()]] : [];
  listed.push(['python3'], ['python']);
  if (process.platform === 'win32') listed.push(['py', '-3']);
  return listed;
}

export default async function flowguard() {
  if (!process.env.VITEST) return null;
  const tried = [];
  for (const [command, ...prefix] of interpreters()) {
    const run = spawnSync(command, [...prefix, '-m', 'flowguard.intent.vitest', 'prepare', '--root', ROOT], {
      cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    const output = ((run.stdout || '') + (run.stderr || '')).trimEnd();
    if (run.error || /No module named '?flowguard/.test(output)) {
      tried.push([command, ...prefix].join(' ') + ': ' + (run.error ? run.error.message : output.split('\\n').pop()));
      continue;
    }
    if (run.status !== 0) throw new Error('FlowGuard vitest preparation exit ' + run.status + ':\\n' + output);
    const answer = JSON.parse(run.stdout.trim().split('\\n').pop());
    if (answer.status !== 'on') return null;
    const { flowguardPlugin } = await import(pathToFileURL(answer.adapter).href);
    return flowguardPlugin({ plan: answer.plan, python: [command, ...prefix], root: ROOT, prepareSeconds: answer.seconds });
  }
  throw new Error('FlowGuard: no Python that can import flowguard was found for the vitest execution side; set '
    + 'FLOWGUARD_PYTHON to the interpreter FlowGuard is installed in. Tried:\\n' + tried.join('\\n'));
}
'''
CONFIGS = [f'{stem}.config.{ext}' for stem in ('vitest', 'vite') for ext in ('ts', 'mts', 'js', 'mjs', 'cts', 'cjs')]
MARK = 'flowguard: vitest'
IMPORT = "import flowguard from './flowguard.vitest.mjs'; // " + MARK + " (python -m flowguard init; delete this line and flowguard() to undo)"


def wire(cfg, package):
    """Write `flowguard.vitest.mjs` next to package.json and add it to the vitest config; the text init prints."""
    import os
    folder = package.parent
    data = json.loads(package.read_text(encoding='utf-8-sig'))
    named = {**(data.get('dependencies') or {}), **(data.get('devDependencies') or {})}
    if 'vitest' not in named and 'vitest' not in str((data.get('scripts') or {}).get('test', '')):
        return f'{cfg.rel(package)} does not use vitest: the execution side is not wired there.'
    target = folder / 'flowguard.vitest.mjs'
    if target.exists() and not target.read_text(encoding='utf-8').startswith(GENERATED):
        raise ValueError(f'{target}: an existing file has this name; rename it, then run init again')
    relative = os.path.relpath(cfg.root, folder).replace(os.sep, '/')
    target.write_text(MODULE.replace('@ROOT@', json.dumps(relative)).replace('@RECORDED@', json.dumps(RECORDED_PYTHON)),
                      encoding='utf-8', newline='\n')
    config = next((folder / name for name in CONFIGS if (folder / name).is_file()), None)
    if config is None:
        config = folder / 'vitest.config.mjs'
        config.write_text(INIT_MARK + ": vitest's defaults plus FlowGuard's execution side; "
                          "delete this file to undo.\nimport { defineConfig } from 'vitest/config';\n" + IMPORT + "\n"
                          "export default defineConfig({ plugins: [flowguard()] }); // " + MARK + "\n", encoding='utf-8', newline='\n')
        return f'Generated {cfg.rel(target)} and {cfg.rel(config)}: vitest runs FlowGuard\'s execution side (delete both to undo).'
    text = config.read_text(encoding='utf-8')
    manual = (f'add these two lines to {cfg.rel(config)} yourself: {IMPORT}  and  flowguard(), as the first entry of plugins')
    if 'flowguard.vitest.mjs' in text:
        return f'Generated {cfg.rel(target)}; {cfg.rel(config)} already lists flowguard().'
    if config.suffix in ('.cjs', '.cts') or 'module.exports' in text:
        return f'Generated {cfg.rel(target)}; {cfg.rel(config)} is CommonJS and the execution side supports ESM configs only: {manual}'
    imports = list(re.finditer(r'^import\b[^;]*?;?[ \t]*$', text, re.M | re.S))
    at = imports[-1].end() if imports else 0
    patched = text[:at] + ('\n' if at else '') + IMPORT + ('\n' if not at else '') + text[at:]
    plugins = re.search(r'\bplugins\s*:\s*\[', patched)
    define = re.search(r'\bdefineConfig\(\s*\{', patched)
    if plugins:
        patched = patched[:plugins.end()] + 'flowguard() /* ' + MARK + ' */, ' + patched[plugins.end():]
    elif define:
        # The entry gets a line of its own: what followed `defineConfig({` on its line moves to the next line, so the
        # line comment never swallows it (a one-line config) and deleting the marked line undoes the edit.
        rest = patched[define.end():]
        if not re.match(r'[ \t]*(?:\r?\n|$)', rest):
            rest = rest.lstrip(' \t')
            rest = ('\n' if rest.startswith('}') else '\n  ') + rest
        patched = patched[:define.end()] + '\n  plugins: [flowguard()], // ' + MARK + rest
    else:
        return f'Generated {cfg.rel(target)}; no plugins list or defineConfig({{ in {cfg.rel(config)}: {manual}'
    config.write_text(patched, encoding='utf-8', newline='')
    return (f'Wired FlowGuard\'s execution side into {cfg.rel(config)} through {cfg.rel(target)} '
            f'(two lines marked `{MARK}`; delete them to undo).')


# ---- report -----------------------------------------------------------------------------------------

def value(encoded):
    """A recorded value in Python: numbers, strings, booleans, None (null and undefined), datetimes, lists,
    dicts; a thrown error is cells.Raised; unseen data is None with `unseen` set by the caller."""
    from datetime import datetime
    from . import cells as C
    if isinstance(encoded, list):
        return [value(item) for item in encoded]
    if not isinstance(encoded, dict):
        return encoded
    if '$num' in encoded:
        return float(encoded['$num'].replace('Infinity', 'inf'))
    if '$undef' in encoded:
        return None
    if '$date' in encoded:
        return None if encoded['$date'] == 'Invalid' else datetime.fromisoformat(encoded['$date'].replace('Z', '+00:00'))
    if '$threw' in encoded:
        return C.Raised(Exception(f'{encoded["$threw"]["name"]}: {encoded["$threw"]["message"]}'))
    if '$big' in encoded:
        return int(encoded['$big'])
    if '$set' in encoded:
        return frozenset(json.dumps(item, sort_keys=True) for item in encoded['$set'])
    if '$map' in encoded:
        return tuple(sorted((json.dumps(k, sort_keys=True), json.dumps(v, sort_keys=True)) for k, v in encoded['$map']))
    return {key[1:] if key.startswith('$$') else key: value(item) for key, item in encoded.items()}


def _same(left, right):
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def case_class(point, inputs):
    """The case class of one replayed input: each varied input against the constants its function compares
    (`days<3`, `days=3`, `3<days<10`, `days>10`), a compared string or `other`, a boolean or date as it is."""
    from . import cells as C
    parts, bounds, labels = [], point['bounds'], set(point['strings'])
    for name, encoded in inputs:
        item = value(encoded)
        if isinstance(item, float) and not math.isfinite(item):
            parts.append(f'{name}={item}')
        elif isinstance(item, (int, float)) and not isinstance(item, bool) and bounds:
            if item in bounds:
                parts.append(f'{name}={C.show(item)}')
            elif item < bounds[0]:
                parts.append(f'{name}<{C.show(bounds[0])}')
            elif item > bounds[-1]:
                parts.append(f'{name}>{C.show(bounds[-1])}')
            else:
                low, high = max(b for b in bounds if b < item), min(b for b in bounds if b > item)
                parts.append(f'{C.show(low)}<{name}<{C.show(high)}')
        elif isinstance(item, str):
            parts.append(f'{name}={C.show(item)}' if item in labels else f'{name}=other')
        else:
            parts.append(f'{name}={C.show(item)}')
    return '，'.join(parts)


def _observations(directory):
    records = []
    for path in sorted(Path(directory).glob('obs-*.jsonl')):
        records.extend(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip())
    return records


def _counterexample(point, records):
    """The order in which the rows of a same-name comparison are read for the input to print: the one closest
    to an input a test actually used (the same booleans, strings and dates first, then the smallest numeric
    distance; year=2025 next to the test's 2026, not a representative far away like year=0), then the smallest
    magnitude, as before."""
    from datetime import datetime
    used = [dict(zip(point['params'], record['args'])) for record in records]
    def number(item):
        return isinstance(item, (int, float)) and not isinstance(item, bool)
    def size(item):
        return abs(item) if number(item) and math.isfinite(item) else math.inf if number(item) else 0
    def apart(name, item, seen):
        if name not in seen:
            return 1, 0.0
        mine, theirs = value(item), value(seen[name])
        if number(mine) and number(theirs):
            finite = math.isfinite(mine) and math.isfinite(theirs)
            return 0, abs(mine - theirs) if finite else 0.0 if _same(item, seen[name]) else math.inf
        if isinstance(mine, datetime) and isinstance(theirs, datetime):
            return 0, abs((mine - theirs).total_seconds()) / 86400
        return int(not _same(item, seen[name])), 0.0
    def key(row):
        nearest = min(((sum(apart(name, item, seen)[0] for name, item in row['in']),
                        sum(apart(name, item, seen)[1] for name, item in row['in'])) for seen in used), default=(0, 0.0))
        return nearest, [size(value(item)) for _, item in row['in']]
    return key


def _inside(cfg, rel, package):
    """Whether a file belongs to the package whose vitest run this is (every file without one)."""
    return package is None or (cfg.root / rel).resolve().is_relative_to(Path(package).resolve())


def closed_rows(data, records):
    """Compare source-only functions after the session, using real JSON inputs and copy neighbours."""
    import subprocess
    points = {point['id']: point for entry in data['files'].values() for point in entry['points']}
    actual, groups, reasons = {}, {}, {}
    for record in records:
        if record.get('reason'):
            reasons.setdefault(record['id'], []).append(record['reason'])
        elif 'args' in record:
            actual.setdefault(record['id'], []).append(record['args'])
    for point in points.values():
        if point['anchored']:
            groups.setdefault(point['name'], []).append(point)
    def unique(values, limit):
        result, seen = [], set()
        for args in values:
            key = json.dumps(args, sort_keys=True)
            if key not in seen:
                seen.add(key)
                result.append(args)
            if len(result) == limit:
                break
        return result
    shared = {}
    for name, peers in groups.items():
        if len(peers) < 2:
            continue
        samples = unique([args for peer in peers for args in actual.get(peer['id'], ())], LIMIT)
        extra, constants = [], sorted({number for peer in peers for number in peer['numbers']})
        for args in samples:
            for index, item in enumerate(args):
                if type(item) in (int, float):
                    extra.extend([*args[:index], number, *args[index + 1:]] for number in [item - 1, item + 1, *constants])
        shared[name] = unique([*samples, *extra], LIMIT)
    wanted, jobs, keys = {}, [], {}
    for ident, point in points.items():
        wanted[ident] = unique([*actual.get(ident, ()), *shared.get(point['name'], ())], None)
        for prior in (False, True):
            source, why = (point['old_source'], point['old_skip']) if prior else (point['source'], point['skip'])
            if why:
                if not prior or why != point['skip']:
                    reasons.setdefault(ident, []).append(('baseline: ' if prior else '') + why)
                continue
            for args in wanted[ident]:
                key = (ident, prior, json.dumps(args, sort_keys=True))
                keys[key] = len(jobs)
                jobs.append(dict(source=source, fn=point['fn'], args=args))
    outcomes = []
    if jobs:
        run = subprocess.run(['node', str(ADAPTER / 'sealed.mjs')], input=json.dumps(jobs), capture_output=True,
                             text=True, check=True, timeout=max(30, len(jobs) * 0.4))
        outcomes = json.loads(run.stdout)
        if len(outcomes) != len(jobs):
            raise ValueError('sealed comparison returned the wrong number of results')
    def outcome(ident, prior, args):
        index = keys.get((ident, prior, json.dumps(args, sort_keys=True)))
        if index is None:
            return {'$missing': 1}
        result = outcomes[index]
        why = result.get('reason')
        if 'error' in result:
            error = result['error']
            missing = re.fullmatch(r'(\S+) is not defined', error['message'])
            if error['name'] == 'ReferenceError' and (missing or error['message'].startswith('uses ')):
                why = 'uses ' + missing[1] if missing else error['message']
            elif error['name'] == 'EvalError':
                why = error['message']
            else:
                return {'$threw': error}
        if why:
            reasons.setdefault(ident, []).append(('baseline: ' if prior else '') + why)
            return {'$missing': 1}
        return result['value']
    rows = {}
    for ident, point in points.items():
        real = {json.dumps(args, sort_keys=True) for args in actual.get(ident, ())}
        rows[ident] = []
        for args in wanted[ident]:
            now = outcome(ident, False, args)
            if isinstance(now, dict) and '$missing' in now:
                continue
            old = outcome(ident, True, args)
            rows[ident].append(dict(
                **{'in': list(zip(point['params'], args))}, now=now, old=old,
                actual=json.dumps(args, sort_keys=True) in real,
                same=any(_same(args, sample) for sample in shared.get(point['name'], ())),
                copies={copy['id']: outcome(copy['id'], False, args) for copy in point['copies']},
                old_copies={copy['id']: outcome(copy['id'], True, args) for copy in point['copies']}))
    return rows, reasons


def judge(cfg, data, records, package=None):
    """The session report signals.render prints: changes per case class, same-name and rule reds, grey.
    `package` is the folder of the vitest run: a point in another package cannot be reached by its tests
    and is not listed as unreached. Each unverified point is one item, named with its place."""
    from . import cache, cells as C
    from .engine import CONFLICT, Engine, PredicateError, outcome_eq
    from .loader import load
    from .sources import parse
    points = {point['id']: point for entry in data['files'].values() for point in entry['points']}
    rows, reasons_by_point = closed_rows(data, records)
    calls = {}
    for record in records:
        calls.setdefault(record['id'], []).append(record)
    items, red, before, steps, unverified = [], [], [], {}, []
    for item in data['unplanned']:
        if _inside(cfg, item['rel'], package):
            unverified.append(f'{item["name"]}（{item["rel"]}:{item["line"]}）：{item["reason"]}')
    for ident, point in points.items():
        where = f'{point["rel"]}:{point["target_line"]}'
        collected = [dict(row, label=case_class(point, row['in'])) for row in rows.get(ident, ())]
        reasons = reasons_by_point.get(ident, [])
        if point['skip']:
            reasons.append(point['skip'])
        rows[ident] = collected
        copy_only = any(copy['id'] == ident for other in points.values() for copy in other['copies']
                        if calls.get(other['id']))
        if not calls.get(ident) and not collected:
            if point['skip'] and (copy_only or _inside(cfg, point['rel'], package)):
                unverified.append(f'{point["name"]}: {point["skip"]}')
                continue
            if point['anchored'] and not copy_only and _inside(cfg, point['rel'], package):
                unverified.append(f'{point["name"]}（{where}): not reached by any test')
            continue
        if not collected:
            unverified.extend(f'{point["name"]}：{reason}' for reason in dict.fromkeys(reasons))
            continue
        if not point['changed']:
            if reasons:
                unverified.extend(f'{point["name"]}: {reason}' for reason in dict.fromkeys(reasons))
            continue
        actual_rows = [row for row in collected if row['actual']]
        compared = [row for row in actual_rows if not (isinstance(row['old'], dict) and '$missing' in row['old'])
                    and not (isinstance(row['old'], dict) and '$threw' in row['old'] and _same(row['old'], row['now']))]
        if any(isinstance(row['old'], dict) and '$threw' in row['old'] and _same(row['old'], row['now']) for row in actual_rows):
            reasons.append('both versions raised the same exception; not compared')
        changes = [row for row in compared if not _same(row['old'], row['now'])]
        classes = {row['label'] for row in actual_rows}
        if not changes and not reasons and {row['label'] for row in compared} == classes:
            continue    # every replayed class compared and none changed: quiet, as on the pytest side
        items.append(dict(
            name=point['name'], file=point['rel'], line=point['target_line'], unanchored=not point['anchored'],
            status='ok', complete=False, total=len(actual_rows), checked=len(compared),
            changed=len(changes),
            changes=[dict(inputs={name: value(item) for name, item in row['in']}, region=row['label'],
                          before=C.show(value(row['old'])), after=C.show(value(row['now']))) for row in changes],
            reasons=['TS classes come from comparison constants; this does not prove a complete partition'] + list(dict.fromkeys(reasons)),
            rows=[(row['in'], row['now']) for row in collected]))
    # Same-name copies share replayed inputs. Classify disagreements by function pair: an old
    # broken pair cannot hide another pair newly broken on a different input.
    same_name = dict(compared=set(), disagreed={})
    from .signals import copy_partition, rule_steps
    def copy_report(name, lines, existing=False):
        return (f'same-name anchor {name}: ' + '; '.join(
            f'{where}, {text}' + ('' if existing else f' -> {step}') for where, text, step, _ in lines)
            + (' -> leave it unless your task is about it' if existing
               else '; if intentionally different, use different names'))
    handled = set()
    for ident, point in sorted(points.items(), key=lambda pair: not bool(calls.get(pair[0]))):
        if not point['copies'] or point['name'] in handled:
            continue
        handled.add(point['name'])
        samples = [row for row in rows.get(ident, ()) if row['same']]
        current_rows, past_rows, old_unknown = [], [], False
        places = {target: f'{other["rel"]}:{other["target_line"]} {other["fn"]}'
                  for target, other in points.items()}
        owner = next((places[target] for target in [ident, *(copy['id'] for copy in point['copies'])]
                      if points[target].get('owner')), None)
        for row in sorted(samples, key=_counterexample(point, [record for record in calls.get(ident, ()) if 'args' in record])):
            inputs = ', '.join(f'{name}={C.show(value(item))}' for name, item in row['in'])
            old = [(ident, row['old']), *row['old_copies'].items()]
            old = [(target, answer) for target, answer in old
                   if points[target]['old_skip'] != 'function absent at baseline']
            complete = all(not (isinstance(answer, dict) and '$missing' in answer) for _, answer in old)
            if not complete:
                old_unknown = True
            available_old = [(places[target], answer) for target, answer in old
                             if not (isinstance(answer, dict) and '$missing' in answer)]
            if available_old and all(isinstance(answer, dict) and '$threw' in answer for _, answer in available_old) and all(
                    _same(answer, available_old[0][1]) for _, answer in available_old):
                old_unknown = True
            past_rows.append((inputs, available_old))
            answers = [(places[ident], row['now'])]
            for copy in point['copies']:
                theirs = row['copies'].get(copy['id'])
                if theirs is not None and not (isinstance(theirs, dict) and '$missing' in theirs):
                    answers.append((places[copy['id']], theirs))
            if len(answers) < 2:
                continue
            if all(isinstance(answer, dict) and '$threw' in answer for _, answer in answers) and all(
                    _same(answer, answers[0][1]) for _, answer in answers):
                unverified.append(point['name'] + ': all copies raised the same exception; not compared')
                continue
            current_rows.append((inputs, answers))
        new_lines, previous_lines = copy_partition(current_rows, past_rows, _same, lambda item: C.show(value(item)),
                                                   owner=owner, total=len(point['copies']) + 1)
        if not old_unknown and any(len(answers) == len(point['copies']) + 1 for _, answers in current_rows):
            same_name['compared'].add(point['name'])
        if previous_lines:
            before.append(copy_report(point['name'], previous_lines, existing=True))
        if new_lines:
            line = copy_report(point['name'], new_lines)
            if old_unknown:
                unverified.append(line + ': baseline could not be compared')
            else:
                red.append(line)
        if new_lines or previous_lines:
            same_name['disagreed'][point['name']] = copy_report(point['name'], new_lines + previous_lines)
    # rules on the observed calls and replayed classes, as the pytest side checks a reading
    model = load(cfg)
    engine = Engine(model)
    unverified.extend(f'{error["file"]}:{error["line"]}: {error["msg"]}' for error in model.errors)
    quoted = set()
    for rule in model.rules.values():
        for home in rule.homes:
            if getattr(home, 'anchor', None) is None or home.anchor.target not in points:
                continue
            ident = home.anchor.target
            point = points[ident]
            observed = [({name: value(item) for name, item in row['in']}, value(row['now'])) for row in rows.get(ident, ())]
            observed += [({name: value(item) for name, item in zip(point['params'], record['args'])}, value(record['result']))
                         for record in calls.get(ident, ()) if 'args' in record and 'result' in record]
            usable = [(inputs, actual) for inputs, actual in observed
                      if all(name in inputs and C.kind_of(kind).accepts(inputs[name]) for name, kind in rule.fields.items())]
            if not usable:
                if calls.get(ident):
                    unverified.append(f'{rule.id}：{point["name"]} observation lacks the inputs required by this rule ({", ".join(rule.fields)}）')
                continue
            for inputs, actual in usable:
                cell = {name: inputs[name] for name in rule.fields}
                try:
                    expected = engine.effective(rule, cell)
                except PredicateError as error:
                    red.append(str(error))      # a predicate failing on an observed cell is red with its text, as in pytest
                    break
                if expected is CONFLICT or expected is None or outcome_eq(expected, actual):
                    continue
                red.append(f'{rule.id}: {C.show_cell(cell)} -> rule {C.show(expected)}, code {C.show(actual)}'
                           f'（{point["rel"]}:{point["target_line"]} {point["fn"]}）')
                if rule.id not in quoted:
                    source = parse(rule.source)
                    red.append(rule.id + ' source: ' + (source.quote or source.text))
                    quoted.add(rule.id)
                    steps.setdefault(rule.id, rule_steps(rule.id, f'{point["rel"]}:{point["target_line"]} {point["fn"]}',
                                                         f'{model.file_of[rule.id]}:{rule.line}'))
                break
    # How far HEAD lies after a recorded task start is read now, by the one git call of pytest's title, and not
    # kept in the plan, whose key is the commit and its kind: the title says it as pytest's does.
    kind = data.get('baseline_kind', 'task')
    start = cache.task_start(cfg) if kind == 'task' else (None, None, None)
    return dict(session=True, baseline=data['baseline'], baseline_kind=kind,
                baseline_ahead=start[2] if start[:2] == (data['baseline'], 'task') else None,
                source_changed=True, items=items, paths=[], leads=[], red=list(dict.fromkeys(red)), before=list(dict.fromkeys(before)), steps=steps,
                unverified=unverified, same_name_pairs=same_name)


SESSION = 'report.json'           # in the observations folder: what the session test judged, for the teardown


def report(root, plan_path, observations, package=None, *, in_test=False):
    """Judge this run's observations and print FlowGuard's lines; 1 on red. `in_test` is the session test
    (session.test.mjs, run after the project's tests): it keeps the observations and saves the text and
    status for the teardown, which then prints them after the summary instead of judging again."""
    from .config import load_config
    from .differences import display
    from .signals import render
    started = time.perf_counter()
    cfg = load_config(root)
    data = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    records = _observations(observations)
    recorded = sum(record.get('record_seconds', 0) for record in records)
    result = judge(cfg, data, [record for record in records if 'id' in record], package)
    import os
    result['seconds'] = float(os.environ.get('FLOWGUARD_VITEST_PREPARE_SECONDS', 0)) + recorded + time.perf_counter() - started
    text = render(result)
    status = 1 if result['red'] else 0
    if in_test:
        (Path(observations) / SESSION).write_text(json.dumps(dict(text=text, status=status), ensure_ascii=False), encoding='utf-8')
    else:
        shutil.rmtree(observations)     # this run's records are read; the next run starts empty
    if text:
        display(text)
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m flowguard.intent.vitest')
    parser.add_argument('step', choices=('prepare', 'report'))
    parser.add_argument('--root', required=True)
    parser.add_argument('--plan')
    parser.add_argument('--observations')
    parser.add_argument('--package', help='The folder of the vitest run (its vite root)')
    parser.add_argument('--in-test', action='store_true', help='Run by the session test: keep the observations')
    options = parser.parse_args(argv)
    if options.step == 'prepare':
        print(json.dumps(prepare(options.root), ensure_ascii=False))
        return 0
    if not options.plan or not options.observations:
        parser.error('report needs --plan and --observations')
    return report(options.root, options.plan, options.observations, options.package, in_test=options.in_test)


if __name__ == '__main__':
    sys.exit(main())
