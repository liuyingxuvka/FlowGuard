"""The execution side for TS/JS projects tested with vitest (minimal: vitest and ESM only; jest stays static).

`prepare` runs when vitest loads its config (`flowguard.vitest.mjs`, written by `init`). With no TS/JS change
against the task baseline it answers `off` after one `git diff` and nothing is wrapped, unless same-name sensors
disagreed in the last report (`DISAGREED`): those are compared again. Otherwise it plans,
as the pytest side does, the anchored functions (`// flowguard: sensor NAME`) and the functions this change
edited: their positional parameters, representative values from cells (the compared constants of the map's
ecma facts, folded names and table keys included), same-name copies and the baseline sources. The plan is
cached by a fingerprint of the baseline commit (and whether it is a recorded task start or HEAD standing in),
the changed files and the reader.

`report` runs after the tests. It reads what the Node adapter recorded and makes every judgment the way the
pytest side does: what changed against the baseline per case class, which same-name sensors disagree, which
rules the observed calls violate, and what stayed unverified. signals.render prints the usual lines.
Usage: python -m flowguard.intent.vitest prepare --root ROOT | report --root ROOT --plan PLAN --observations DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
from pathlib import Path

from .config import INIT_MARK, RECORDED_PYTHON

ADAPTER = Path(__file__).resolve().parents[1] / 'adapters' / 'vitest'
LIMIT = 512                                      # representative combinations one replayed call may run
STRING_CONTEXTS = frozenset({'compare', 'case', 'member', 'set'})
# A function whose code or callees name a database client is never replayed: a connection opened before the
# replay cannot be refused by the Node guard.
DATABASE = re.compile(r'\b(?:prisma|PrismaClient|centralPrisma|knex|sequelize|mongoose|typeorm|drizzle|mssql|tedious|'
                      r'pg|mysql2?|sqlite3?|redis|ioredis)\b|\$transaction|\$queryRaw')
WRAPPABLE = ('function_declaration', 'generator_function_declaration')
# The map's meta key holding {sensor name: red line} of the same-name sensors whose last comparison disagreed:
# `prepare` compares them again in a run without a TS/JS change, `report` keeps it current.
DISAGREED = 'vitest_same_name_disagreed'


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


def _number_values(consts, copies):
    """cells.points over the compared constants: c-1, c, c+1 and c-0.01, c, c+0.01 (a TS number is both an int
    and a float), far below and above, 0; same-name copies also run the fixed representatives."""
    from . import cells as C
    numbers = [value for value in consts if isinstance(value, (int, float)) and not isinstance(value, bool)]
    out = []
    if numbers and all(isinstance(value, int) for value in numbers):
        out += C.points(C.Kind('int'), numbers)
    if numbers:
        out += C.points(C.Kind('float'), [float(value) for value in numbers])
    if copies:
        out += C.representatives(C.Kind('float'))
    seen, values = set(), []
    for value in out:
        value = int(value) if isinstance(value, float) and value.is_integer() else value
        encoded = _encode(value)
        if json.dumps(encoded) not in seen:
            seen.add(json.dumps(encoded))
            values.append(encoded)
    return values


def _encode(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {'$num': 'NaN' if math.isnan(value) else 'Infinity' if value > 0 else '-Infinity'}
    return value


def _database(graph, ident, text):
    """Why a function is not replayed: its own code or a function it calls (three levels, by name) names a
    database client; '' otherwise."""
    if DATABASE.search(text):
        return '看不清：函数里用到数据库客户端，不回放'
    for callee in graph.call_tree(ident, depth=3):
        found = graph.node(callee)
        if callee == ident or not found or not found.get('file') or found['kind'] not in ('function', 'method'):
            continue
        lines = (graph.root / found['file']).read_text(encoding='utf-8').splitlines()
        if DATABASE.search('\n'.join(lines[found['line'] - 1:found['end_line']])):
            return f'看不清：调用的 {found["qual"]}（{found["file"]}）用到数据库客户端，不回放'
    return ''


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
        modules = {row['file']: row['module'] for row in graph.nodes(kind='module')}
        wanted = {}                     # id -> (name, anchored, rel, qual)
        for anchor in index.entries:
            if anchor.kind == 'sensor' and _ecma(anchor.file) and anchor.source_role != 'test':
                wanted[anchor.target] = (anchor.name, True, anchor.file, anchor.qual)
        old_sources, readers = {}, {}
        for rel in changed:
            if rel not in modules or is_test_rel(rel) or not (cfg.root / rel).is_file():
                continue
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
                                      reason='只观察模块顶层的 function f 和 const f = (...) =>，这个函数不包'))
                continue
            if not anchored and not found['params']:
                continue                # like the pytest side: a changed function without inputs is not observed
            lines = (cfg.root / rel).read_text(encoding='utf-8').splitlines()
            node = found['node']
            body = '\n'.join(lines[node.start_point.row:node.end_point.row + 1])
            skip = '看不清：async 函数返回 Promise，不回放' if found['is_async'] else _database(graph, ident, body)
            points.append(dict(id=ident, name=name, anchored=anchored, rel=rel, file=(cfg.root / rel).as_posix(), fn=qual,
                               line=found['line'], target_line=line, form=found['form'], params=found['params'], skip=skip,
                               consts=numbers.get((rel, qual), []), labels=sorted(set(strings.get((rel, qual), [])))))
    groups = {}
    for point in points:
        if point['anchored']:
            groups.setdefault(point['name'], []).append(point)
    copy_files = sorted({point['file'] for group in groups.values() if len(group) > 1 for point in group})
    files = {}
    baselines = []
    from .cells import OTHER
    shared = {point['id']: (list(point['consts']), list(point['labels'])) for point in points}
    for point in points:
        peers = [other for other in groups.get(point['name'], ()) if other is not point] if point['anchored'] else []
        consts = point.pop('consts') + [value for other in peers for value in shared[other['id']][0]]
        labels = sorted(set(point.pop('labels')).union(*(shared[other['id']][1] for other in peers)))
        point.update(numbers=_number_values(consts, bool(peers)), strings=labels + [OTHER] if labels else [],
                     bounds=sorted({value for value in consts if isinstance(value, (int, float)) and not isinstance(value, bool)}),
                     copies=[dict(id=other['id'], fn=other['fn'], params=other['params'], index=copy_files.index(other['file']))
                             for other in peers])
    for point in points:
        entry = files.get(point['file'])
        if entry is None:
            old = old_sources[point['rel']] if point['rel'] in old_sources else git_blob(cfg.root, commit, point['rel'])
            if old is not None:
                baselines.append(dict(file=point['file'], text=old.decode('utf-8'),
                                      functions=sorted(declarations(old, point['rel']))))
            entry = files[point['file']] = dict(baseline=len(baselines) - 1 if old is not None else None, points=[])
        entry['points'].append(point)
    return dict(key=key, root=cfg.root.as_posix(), baseline=commit, limit=LIMIT, files=files, baselines=baselines,
                copy_files=copy_files, unplanned=unplanned)


def disagreed(cfg):
    """{sensor name: red line} of the same-name sensors whose last vitest comparison disagreed."""
    from contextlib import closing
    import sqlite3
    path = cfg.cache / 'map.sqlite'
    if not path.is_file():
        return {}
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone():
            return {}
        row = con.execute('SELECT v FROM meta WHERE k=?', (DISAGREED,)).fetchone()
    return json.loads(row[0]) if row else {}


def _remember_disagreed(cfg, data, same_name):
    """Keep the record of disagreeing same-name sensors: this run's disagreements, and the earlier ones
    this run did not compare while they are still planned (anchored)."""
    from contextlib import closing
    from .cache import put_meta
    from ..structure.store import connect
    before = disagreed(cfg)
    planned = {point['name'] for entry in data['files'].values() for point in entry['points'] if point['anchored']}
    now = {name: line for name, line in before.items() if name in planned and name not in same_name['compared']}
    now.update(same_name['disagreed'])
    if now != before:
        with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
            put_meta(con, DISAGREED, json.dumps(now, ensure_ascii=False, sort_keys=True))


def prepare(root):
    """{'status': 'off', 'reason'} without a TS/JS change, else {'status': 'on', 'plan', 'adapter'}."""
    from . import cache
    from .config import load_config
    from ..map.common import git_common_directory, git_run
    cfg = load_config(root)
    if git_common_directory(cfg.root) is None:
        return dict(status='off', reason='不是 git 仓库：没有基准提交，执行侧不比较')
    # vitest records no baseline: before the first `check --static` (or pytest, or the brief) of a task, HEAD
    # stands in, and the title says so.
    baseline, kind = cache.task_baseline(cfg)
    if kind == 'missing':
        return dict(status='off', reason=f'记下的任务开始 {baseline[:7]} 不在这个仓库里：执行侧不比较；先运行 python -m flowguard new-task')
    found = git_run(cfg.root, 'rev-parse', '-q', '--verify', (baseline or 'HEAD') + '^{commit}', allowed=(0, 1))
    if found.returncode:
        return dict(status='off', reason='还没有提交：没有基准，执行侧不比较')
    commit = found.stdout.decode().strip()
    changed = _changed(cfg, commit)
    again = sorted(disagreed(cfg)) if not changed else []
    if not changed and not again:
        return dict(status='off', reason='相对基准没有 TS/JS 改动：执行侧不准备')
    # Without a change, the same-name sensors that disagreed last time are compared again (every sensor is
    # planned, as in a run with a change); the record clears once they agree or are no longer anchored.
    key = _key(cfg, commit, changed or ['same-name:' + name for name in again], kind)
    path = cfg.cache / 'vitest' / f'plan-{key}.json'
    if not path.is_file():
        data = plan(cfg, commit, changed, key)
        data['baseline_kind'] = kind
        path.parent.mkdir(parents=True, exist_ok=True)
        for old in path.parent.glob('plan-*.json'):
            old.unlink()                # one current plan; an older one belongs to another change
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    else:
        data = json.loads(path.read_text(encoding='utf-8'))
    if not data['files'] and not data['unplanned']:
        return dict(status='off', reason='这次改动里没有要观察的函数（锚点或改过的模块顶层函数）')
    return dict(status='on', plan=path.as_posix(), adapter=(ADAPTER / 'index.mjs').as_posix())


# ---- init: wire the plugin into the vitest config ---------------------------------------------------

GENERATED = INIT_MARK + ': FlowGuard\'s execution side for vitest (minimal: vitest, ESM).'
MODULE = GENERATED + '''
// The vitest config imports this file and lists flowguard() in its plugins: two lines marked `flowguard: vitest`.
// Delete those two lines to undo. With no TS/JS change against the task baseline it adds nothing; otherwise it
// wraps the functions anchored with a `flowguard: sensor NAME` comment and the changed ones, and FlowGuard's lines follow
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
    return flowguardPlugin({ plan: answer.plan, python: [command, ...prefix], root: ROOT });
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
        patched = patched[:define.end()] + '\n  plugins: [flowguard()], // ' + MARK + patched[define.end():]
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
    (`days<3`, `days=3`, `3<days<10`, `days>10`), a compared string or `其他`, a boolean or date as it is."""
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
            parts.append(f'{name}={C.show(item)}' if item in labels else f'{name}=其他')
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


def judge(cfg, data, records, package=None):
    """The session report signals.render prints: changes per case class, same-name and rule reds, grey.
    `package` is the folder of the vitest run: a point in another package cannot be reached by its tests
    and is not listed as unreached. Each unverified point is one item, named with its place."""
    from . import cache, cells as C
    from .engine import CONFLICT, Engine, PredicateError, outcome_eq
    from .loader import load
    from .sources import parse
    points = {point['id']: point for entry in data['files'].values() for point in entry['points']}
    calls, rows = {}, {}
    for record in records:
        calls.setdefault(record['id'], []).append(record)
    items, red, steps, unverified = [], [], {}, []
    for item in data['unplanned']:
        if _inside(cfg, item['rel'], package):
            unverified.append(f'{item["name"]}（{item["rel"]}:{item["line"]}）：{item["reason"]}')
    for ident, point in points.items():
        where = f'{point["rel"]}:{point["target_line"]}'
        seen, collected, reasons = set(), [], []
        for record in calls.get(ident, ()):
            replay = record.get('replay')
            if replay is None:
                continue
            if replay['status'] != 'ok':
                reasons.append(replay['reason'])
                continue
            for row in replay['rows']:
                signature = json.dumps(row['in'], sort_keys=True)
                if signature not in seen:
                    seen.add(signature)
                    collected.append(dict(row, label=case_class(point, row['in'])))
        rows[ident] = collected
        copy_only = any(copy['id'] == ident for other in points.values() for copy in other['copies']
                        if calls.get(other['id']))
        if not calls.get(ident):
            if point['anchored'] and not copy_only and _inside(cfg, point['rel'], package):
                unverified.append(f'{point["name"]}（{where}）：没有测试走到')
            continue
        if not collected:
            unverified.extend(f'{point["name"]}：{reason}' for reason in dict.fromkeys(reasons))
            continue
        compared = [row for row in collected if 'old' in row and not (isinstance(row['old'], dict) and '$missing' in row['old'])]
        changes = [row for row in compared if not _same(row['old'], row['now'])]
        classes = {row['label'] for row in collected}
        if not changes and not reasons and {row['label'] for row in compared} == classes:
            continue    # every replayed class compared and none changed: quiet, as on the pytest side
        items.append(dict(
            name=point['name'], file=point['rel'], line=point['target_line'], unanchored=not point['anchored'],
            status='ok', complete=False, total=len(classes), checked=len({row['label'] for row in compared}),
            changed=len({row['label'] for row in changes}),
            changes=[dict(inputs={name: value(item) for name, item in row['in']}, region=row['label'],
                          before=C.show(value(row['old'])), after=C.show(value(row['now']))) for row in changes],
            reasons=['TS 的情况类来自比较里的常量，不证明划分完整'] + list(dict.fromkeys(reasons)),
            rows=[(row['in'], row['now']) for row in collected]))
    # same-name sensors: the copies ran on the same replayed inputs. One red per name: what every copy answered
    # on the first input where they differ, never which one to follow (TS has no `distinct`: a different name).
    same_name = dict(compared=set(), disagreed={})
    from .signals import copy_answers, rule_steps
    for ident, point in points.items():
        if not point['copies'] or point['name'] in same_name['disagreed']:
            continue
        for row in sorted(rows.get(ident, ()), key=_counterexample(point, calls.get(ident, ()))):
            answers = [(f'{point["rel"]}:{point["target_line"]} {point["fn"]}', row['now'])]
            for copy in point['copies']:
                theirs = row.get('copies', {}).get(copy['id'])
                if theirs is not None and '$unmatched' not in json.dumps(theirs):
                    other = points[copy['id']]
                    answers.append((f'{other["rel"]}:{other["target_line"]} {other["fn"]}', theirs))
            if len(answers) < 2:
                continue
            same_name['compared'].add(point['name'])
            if all(_same(theirs, row['now']) for _, theirs in answers[1:]):
                continue
            inputs = ', '.join(f'{name}={C.show(value(item))}' for name, item in row['in'])
            text, step = copy_answers(answers, _same, lambda item: C.show(value(item)), total=len(point['copies']) + 1)
            red.append(f'同名锚点 {point["name"]}：{inputs}，{text} -> {step}；有意不同，就给它们起不同的名字')
            same_name['disagreed'][point['name']] = red[-1]
            break
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
                         for record in calls.get(ident, ())]
            usable = [(inputs, actual) for inputs, actual in observed
                      if all(name in inputs and C.kind_of(kind).accepts(inputs[name]) for name, kind in rule.fields.items())]
            if not usable:
                if calls.get(ident):
                    unverified.append(f'{rule.id}：{point["name"]} 的观察里没有规则要的输入（{", ".join(rule.fields)}）')
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
                    red.append(rule.id + ' 出处：' + (source.quote or source.text))
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
                source_changed=True, items=items, paths=[], leads=[], red=list(dict.fromkeys(red)), steps=steps,
                unverified=unverified, same_name_pairs=same_name)


SESSION = 'report.json'           # in the observations folder: what the session test judged, for the teardown


def report(root, plan_path, observations, package=None, *, in_test=False):
    """Judge this run's observations and print FlowGuard's lines; 1 on red. `in_test` is the session test
    (session.test.mjs, run after the project's tests): it keeps the observations and saves the text and
    status for the teardown, which then prints them after the summary instead of judging again."""
    from .config import load_config
    from .differences import display
    from .signals import render
    cfg = load_config(root)
    data = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    result = judge(cfg, data, _observations(observations), package)
    _remember_disagreed(cfg, data, result['same_name_pairs'])
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
