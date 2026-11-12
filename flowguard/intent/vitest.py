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


def _differs(cfg, commit):
    """The files the working tree changed against the baseline commit, untracked ones included (none in
    node_modules)."""
    import os
    from ..map.common import git_run
    changed = git_run(cfg.root, 'diff', '--name-only', '-z', commit).stdout
    added = git_run(cfg.root, 'ls-files', '--others', '--exclude-standard', '-z').stdout
    return sorted({os.fsdecode(value) for value in (changed + added).split(b'\0') if value and b'node_modules/' not in value})


def _changed(cfg, commit):
    """The TS/JS files the working tree changed against the baseline commit, untracked ones included."""
    return [rel for rel in _differs(cfg, commit) if _ecma(rel)]


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _key(cfg, commit, changed, kind):
    """The plan's fingerprint; `kind` is part of it, as the plan's title says whether its commit is a recorded
    task start or HEAD, and so are rules.toml and known.toml, whose entries the plan keeps with their sites
    resolved."""
    from ..structure.store import reader_digest
    from .sources import CATALOG_FILES
    own = [Path(__file__), *sorted(ADAPTER.glob('*.mjs'))]
    parts = [commit, kind, reader_digest(), *(_digest(path.read_bytes()) for path in own)]
    for rel in [*changed, *CATALOG_FILES]:
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


_VITE_EXTENSIONS = ('.mjs', '.js', '.mts', '.ts', '.jsx', '.tsx', '.json')     # Vite's default resolve.extensions


def _literal_table(read, rel, specifier, tables):
    """{name: text} of each `const NAME = literal` (a string, number, boolean or null) at the top level of the
    project file a relative import names, read with `read(path)` and never run; {} for anything else. The file
    is the first that exists in the order Vite tries: the exact path, each default extension, then an index
    file; one Vite would load that is not a script gives {}. `tables` keeps each file's table, so one plan
    reads and parses each imported file once."""
    import posixpath
    from ..structure.readers.common import parse, text
    from ..structure.readers.registry import language_for
    if read is None or not specifier.startswith('.'):
        return {}
    base = posixpath.normpath(posixpath.join(posixpath.dirname(rel), specifier))
    if base in tables:
        return tables[base]
    stem = base.rpartition('.')[0] if base.endswith(('.js', '.mjs', '.cjs')) else base   # TS: ./x.js names x.ts
    found = {}
    for path in (base, *(stem + suffix for suffix in (*_VITE_EXTENSIONS, '.cts', '.cjs')),
                 *(base + '/index' + suffix for suffix in _VITE_EXTENSIONS)):
        if path.startswith('../') or path == '..':
            continue
        data = read(path)
        if data is None:
            continue
        if language_for(path) is None:
            break
        source, tree = parse(data, language_for(path))
        for statement in tree.root_node.named_children:
            inner = statement.child_by_field_name('declaration') if statement.type == 'export_statement' else statement
            if inner is None or inner.type != 'lexical_declaration' or not text(inner, source).startswith('const'):
                continue
            for item in inner.named_children:
                key, value = item.child_by_field_name('name'), item.child_by_field_name('value')
                while value is not None and value.type in ('as_expression', 'satisfies_expression', 'parenthesized_expression'):
                    value = value.named_children[0]
                if key is None or value is None or key.type != 'identifier':
                    continue
                negative = value.type == 'unary_expression' and text(value, source)[:1] == '-' \
                    and [child.type for child in value.named_children] == ['number']
                found.setdefault(text(key, source), text(value, source) if value.type in ('string', 'number', 'true', 'false', 'null')
                                 or negative else None)
        break
    tables[base] = {name: value for name, value in found.items() if value is not None}
    return tables[base]


def sealed_source(data, rel, name, read=None, tables=None):
    """Only the selected function, same-file helpers, and literal constants; never module imports. A name
    imported from a relative project file whose top level declares it `const NAME = literal` is that literal
    (`read(path)` gives a file's bytes, or None), read only when the closed source reads the name; any other
    import stays unavailable. `tables` keeps the imported files' literals across calls (`_literal_table`)."""
    tables = {} if tables is None else tables
    from ..structure.readers.common import parse, text, walk
    from ..structure.readers.registry import language_for
    source, tree = parse(data, language_for(rel))
    found = declarations(data, rel)
    constants, blocked, imported = {}, set(), {}
    for statement in tree.root_node.named_children:
        inner = statement.child_by_field_name('declaration') if statement.type == 'export_statement' else statement
        if inner is None:
            continue
        if inner.type == 'import_statement':
            clause = next((child for child in inner.named_children if child.type == 'import_clause'), None)
            origin = inner.child_by_field_name('source')
            specifier = text(origin, source)[1:-1] if origin is not None else ''
            for item in clause.named_children if clause is not None else ():
                if item.type == 'identifier':
                    blocked.add(text(item, source))
                elif item.type == 'namespace_import':
                    blocked.add(text(item.named_children[-1], source))
                else:
                    for spec in item.named_children:
                        alias = spec.child_by_field_name('alias') or spec.child_by_field_name('name')
                        if alias is None:
                            continue
                        if text(inner, source).startswith('import type') or text(spec, source).startswith('type ') \
                                or read is None or not specifier.startswith('.'):
                            blocked.add(text(alias, source))
                            imported.pop(text(alias, source), None)
                        else:       # a relative project file: read when the closed source reads the name
                            imported[text(alias, source)] = specifier, text(spec.child_by_field_name('name'), source)
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
    module_names = found.keys() | constants.keys() | blocked | imported.keys()
    for node in walk(tree.root_node):
        if node.type in ('assignment_expression', 'augmented_assignment_expression', 'update_expression'):
            target = node.child_by_field_name('left') or node.child_by_field_name('argument')
            while target is not None and target.type in ('member_expression', 'subscript_expression'):
                target = target.child_by_field_name('object')
            if target is not None and target.type == 'identifier' and text(target, source) in module_names:
                blocked.add(text(target, source))
    if name not in found:
        return '', 'only module-level functions can be compared'
    # TypeScript's own syntax, which JavaScript does not parse: a parameter's or result's type, a type guard's
    # `x is T` and an assertion's `asserts x`, and type parameters and arguments
    omitted = {'type_annotation', 'type_predicate_annotation', 'asserts_annotation', 'type_parameters', 'type_arguments'}
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
    # Design 4.5: a constant built from number and string literals, signs, + - * / % ** and constants of this file
    # above it is folded in source order (a cycle never folds); one that is no arithmetic is left to `literal`.
    folded, reasons = {}, {}
    def lookup(constant):
        if constant in folded:
            return folded[constant], ''
        if constant in reasons:
            return None, f'uses {constant}: {reasons[constant]}'
        return None, f'{constant} is not a number or text constant before it'
    for constant, node in constants.items():
        if constant not in blocked:
            value, why = _ecma_fold(node, source, lookup)
            if why:
                reasons[constant] = why
            elif why is not None:
                folded[constant] = value
    pending, used, pieces = [name], set(), []
    while pending:
        current = pending.pop()
        if current in used:
            continue
        used.add(current)
        if current in blocked:
            return '', 'uses imported or mutable binding ' + current
        if current in imported:
            pieces.append(f'const {current} = {imported[current]};')
            continue
        if current in found:
            function = found[current]
            node = function['node']
            bad = next((child.type for child in walk(node) if child.type in forbidden), None)
            spelled = {text(child, source) for child in walk(node) if child.type in ('identifier', 'shorthand_property_identifier')}
            for alias in spelled & {alias for alias, value in imported.items() if type(value) is tuple}:
                value = _literal_table(read, rel, imported[alias][0], tables).get(imported[alias][1])
                if value is None:       # not a literal: unavailable, as any other import
                    blocked.add(alias)
                    del imported[alias]
                else:
                    imported[alias] = value
            shadowed = sorted(spelled & blocked)
            if shadowed:
                return '', 'uses imported or mutable binding ' + shadowed[0]
            if function['is_async'] or 'generator' in node.type or bad:
                return '', 'unsupported ' + (bad or 'async or generator')
            code = stripped(node)
            pieces.append(code if function['form'] == 'function' else f'const {current} = {code};')
            pending.extend(text(child, source) for child in walk(node)
                           if child.type == 'identifier' and text(child, source) in found.keys() | constants.keys() | imported.keys())
        else:
            node = constants[current]
            if current in folded:
                pieces.append(f'const {current} = {_ecma_literal(folded[current])};')
            elif literal(node):
                pieces.append(f'const {current} = {stripped(node)};')
            elif current in reasons:
                return '', f'uses {current}: {reasons[current]}'
            else:
                return '', 'uses nonliteral constant ' + current
    return '\n'.join(reversed(pieces)), ''


_ECMA_WRAPPERS = ('parenthesized_expression', 'as_expression', 'satisfies_expression', 'non_null_expression')
_ECMA_ESCAPES = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0', "'": "'", '"': '"',
                 '\\': '\\', '\n': '', '\u2028': '', '\u2029': ''}


def _ecma_fold(node, source, lookup):
    """The value of a constant's right side built from number and string literals, signs, + - * / % ** and names
    (`lookup(name)` gives (value, why)), with JavaScript's doubles (`features.fold_step`), walking the syntax
    tree without recursion: (value, '') or (None, why it does not fold), and (None, None) when the right side is no
    such arithmetic (a call, an object, a template)."""
    from ..structure.features import FOLD_NUMBER, fold_step
    from ..structure.readers.common import text
    from ..structure.readers.ecma import COMMENTS, literal, operator
    stack, done = [(node, False)], []
    while stack:
        item, ready = stack.pop()
        while item is not None and item.type in _ECMA_WRAPPERS:
            item = next((child for child in item.named_children if child.type not in COMMENTS), None)
        if item is None:
            return None, None
        if item.type == 'number':
            valid, number = literal(item, source)
            if not valid or type(number) not in (int, float) or type(number) is int and abs(number) > FOLD_NUMBER \
                    or not math.isfinite(number):
                return None, 'cannot fold ' + text(item, source)
            done.append(float(number))
            continue
        if item.type in ('string', 'identifier'):
            value, why = _ecma_text(item, source) if item.type == 'string' else lookup(text(item, source))
            if why:
                return None, why
            done.append(value)
            continue
        sign = item.type == 'unary_expression' and operator(item) in ('+', '-')
        if not sign and not (item.type == 'binary_expression' and operator(item) in ('+', '-', '*', '/', '%', '**')):
            return None, None
        children = [item.child_by_field_name('argument')] if sign else [item.child_by_field_name('left'), item.child_by_field_name('right')]
        if not ready:
            stack.append((item, True))
            stack.extend((child, False) for child in reversed(children))
            continue
        value, why = fold_step(operator(item), done[-len(children):], javascript=True)
        if why:
            return None, why
        del done[-len(children):]
        done.append(value)
    return done[0], ''


def _ecma_text(node, source):
    """(the text of a JS string literal, '') or (None, why): its fragments, and the escapes that mean one character
    (\\n, \\xHH, \\uHHHH, \\u{H}, a line continuation...). A lone surrogate or any other escape is not read."""
    from ..structure.readers.common import text
    units = []
    for child in node.named_children:
        spelled = text(child, source)
        if child.type == 'string_fragment':
            units.extend(map(ord, spelled))
        elif child.type == 'escape_sequence' and spelled[1:] in _ECMA_ESCAPES:
            units.extend(map(ord, _ECMA_ESCAPES[spelled[1:]]))
        elif child.type == 'escape_sequence' and re.fullmatch(r'\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|u\{[0-9a-fA-F]{1,6}\})', spelled):
            units.append(int(spelled[2:].strip('{}'), 16))
        else:
            return None, 'cannot fold ' + text(node, source)
    joined, at = [], 0
    while at < len(units):
        unit = units[at]
        if 0xD800 <= unit < 0xDC00 and at + 1 < len(units) and 0xDC00 <= units[at + 1] < 0xE000:
            joined.append(chr(0x10000 + (unit - 0xD800) * 0x400 + units[at + 1] - 0xDC00))
            at += 2
            continue
        if 0xD800 <= unit < 0xE000 or unit > 0x10FFFF:
            return None, 'cannot fold ' + text(node, source)
        joined.append(chr(unit))
        at += 1
    return ''.join(joined), ''


def _ecma_literal(value):
    """A folded value as JavaScript source: a whole number below 2**53 without its fraction, -0 kept."""
    if type(value) is float and value.is_integer() and abs(value) < 2 ** 53 and not (value == 0 and math.copysign(1, value) < 0):
        value = int(value)
    return json.dumps(value, ensure_ascii=False)


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


ABSENT = 'function absent at baseline'
NO_BASELINE = 'no baseline'     # a copy's version at the baseline when the run has none to compare with


def plan(cfg, commit, changed, key):
    """The points to observe and everything the Node adapter needs, as one JSON-ready dict. Without a baseline commit
    (`commit` None: outside Git, before the first commit, a recorded task start this repository lacks) nothing has
    changed and only the same-name copies are planned, each with no version at the baseline (`NO_BASELINE`): as in
    pytest, copies that disagree are then red (design 4.7, D13: the title says nothing was compared)."""
    from contextlib import closing
    from ..map.common import git_blob, git_renames
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
        old_sources, readers, touched = {}, {}, set()
        renamed = git_renames(cfg.root, commit) if commit else {}    # a moved file's baseline version is at its old path
        for rel in changed:
            if rel not in modules or is_test_rel(rel) or not (cfg.root / rel).is_file():
                continue
            if (cfg.root / rel).read_text(encoding='utf-8-sig').startswith(INIT_MARK):
                continue  # FlowGuard's generated wiring is not an application probe.
            old = git_blob(cfg.root, commit, renamed.get(rel, rel))
            old_sources[rel] = old
            before = extract(cfg.root, rel, old, modules[rel], False) if old is not None else dict(nodes=[], const_tables=[])
            now = extract(cfg.root, rel, (cfg.root / rel).read_bytes(), modules[rel], False)
            prior = {row['qual']: row['fp'] for row in before['nodes']}
            # what this change touches (a known entry's site, D31): a declaration it adds, edits or removes
            touched.update(modules[rel] + ':' + row['qual'] for row in now['nodes'] if prior.get(row['qual']) != row['fp'])
            touched.update(modules[rel] + ':' + qual for qual in prior.keys() - {row['qual'] for row in now['nodes']})
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
        tables, old_tables = {}, {}         # each imported file's literals, read once per version
        baseline_files = {renamed.get(rel, rel): data for rel, data in old_sources.items()}    # by baseline path
        for ident, (name, anchored, rel, qual) in sorted(wanted.items()):
            if rel not in parsed:
                parsed[rel] = declarations((cfg.root / rel).read_bytes(), rel)
            found = parsed[rel].get(qual)
            line = graph.node(ident)['line'] if graph.node(ident) else 0
            if found is None:
                unplanned.append(dict(id=ident, name=name, rel=rel, line=line,
                                      reason='only module-level function f and const f = (...) => are observed; this function is not wrapped'))
                continue
            closed, skip = sealed_source((cfg.root / rel).read_bytes(), rel, qual,
                                         lambda path: (cfg.root / path).read_bytes() if (cfg.root / path).is_file() else None, tables)
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
            old_rel = renamed.get(rel, rel)     # a moved file's baseline imports name files next to its old path
            old = old_sources.get(rel) if rel in old_sources else git_blob(cfg.root, commit, old_rel) if commit else None
            prior, old_skip = (sealed_source(old, old_rel, qual, lambda path: baseline_files.get(path) if path in baseline_files
                                             else git_blob(cfg.root, commit, path), old_tables) if old is not None and qual in declarations(old, old_rel)
                               else ('', ABSENT if commit else NO_BASELINE))
            points.append(dict(id=ident, name=name, anchored=anchored, owner=ident in owners, rel=rel, file=(cfg.root / rel).as_posix(), fn=qual,
                               line=found['line'], target_line=line, form=found['form'], params=found['params'], skip=skip,
                               recordable=(not found['is_async'] and 'generator' not in found['node'].type
                                           and skip != 'uses imported or mutable binding ' + qual),
                               source=closed, old_source=prior, old_skip=old_skip,
                               changed=(rel in changed and (old is None or closed != prior)),
                               consts=numbers.get((rel, qual), []) + extra_numbers, labels=sorted(set(strings.get((rel, qual), [])))))
        known, inputs = _catalog(cfg, graph)
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
    return dict(key=key, root=cfg.root.as_posix(), baseline=commit, limit=LIMIT, files=files, unplanned=unplanned,
                touched=sorted(touched), known=known, inputs=inputs)


def _catalog(cfg, graph):
    """(known entries, input findings) of .flowguard/known.toml and rules.toml for the plan: the valid entries with
    their sites resolved on the map (`sources.known_sites`) and the findings of an invalid file, entry or site, both
    as JSON (`_known`, `_issue` read them back)."""
    from dataclasses import asdict
    from . import sources
    if not sources.catalog_files(cfg):
        return [], []
    found = sources.catalog(cfg)
    entries, unresolved = sources.known_sites(graph, found.known.values())
    known = [dict(asdict(entry), sites=list(entry.sites), nodes=sorted(entry.nodes), files=sorted(entry.files)) for entry in entries]
    inputs = [dict(asdict(issue), nodes=sorted(issue.nodes), files=sorted(issue.files), fresh=sorted(issue.fresh))
              for issue in [*found.issues, *unresolved]]
    return known, inputs


def _known(fields):
    """A known entry of the plan (`_catalog`) as `sources.Known`."""
    from .sources import Known
    return Known(**dict(fields, sites=tuple(fields['sites']), nodes=frozenset(fields['nodes']), files=frozenset(fields['files'])))


def _issue(fields):
    """An input finding of the plan (`_catalog`) as `health.Issue`: a place that names several places is a tuple."""
    from .health import Issue
    parts = tuple((function, tuple(place) if isinstance(place, list) else place, what, step) for function, place, what, step in fields['parts'])
    return Issue(**dict(fields, nodes=frozenset(fields['nodes']), files=frozenset(fields['files']), fresh=frozenset(fields['fresh']),
                        entry=tuple(fields['entry']), detail=tuple(fields['detail']), parts=parts))


def prepare(root, package=None):
    """{'status': 'on', 'plan', 'adapter', 'seconds'} with the plan of this vitest run, or {'status': 'off', 'reason',
    'seconds'} for a run that has nothing to observe (no same-name copy, no changed module-level function), a baseline
    commit, and no static test wired in its package (`package`, the folder of its vitest config; the root when not
    given). The first line is always printed (D12): a run whose package has the static test wired prints that test's
    map checks in its block (design 4.7), and a run without a baseline commit (outside Git, before the first commit, a
    recorded task start this repository lacks) compares its same-name copies as pytest does and says in its title
    that nothing was compared with a baseline (D13)."""
    from . import cache
    from .config import load_config
    from ..map.common import atomic_write_text, git_common_directory, git_run
    started = time.perf_counter()
    cfg = load_config(root)
    commit = label = kind = None        # the commit compared with, the commit the title names, and its kind
    if git_common_directory(cfg.root) is not None:
        # vitest records no baseline: before the first `check --static` (or pytest, or the brief) of a task, HEAD
        # stands in, and the title says so.
        label, kind = cache.task_baseline(cfg)
        if kind != 'missing':
            found = git_run(cfg.root, 'rev-parse', '-q', '--verify', (label or 'HEAD') + '^{commit}', allowed=(0, 1))
            commit = label = None if found.returncode else found.stdout.decode().strip()
    changed = _changed(cfg, commit) if commit else []
    # Same-name functions are always planned, including runs without a source change.
    key = _key(cfg, commit or label or '', changed, kind or 'none')
    path = cfg.cache / 'vitest' / f'plan-{key}.json'
    # Without a baseline commit no diff names the files a plan has read, so such a plan is made again on every run.
    if commit is None or not path.is_file():
        data = plan(cfg, commit, changed, key)
        data.update(baseline=label, baseline_kind=kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        for old in path.parent.glob('plan-*.json'):
            old.unlink()                # one current plan; an older one belongs to another change
    else:
        data = json.loads(path.read_text(encoding='utf-8'))
    data['prepare_seconds'] = time.perf_counter() - started
    atomic_write_text(path, json.dumps(data, ensure_ascii=False))
    if not data['files'] and not data['unplanned'] and commit is not None and not _wired(cfg, package):
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
// without either it adds nothing, unless flowguard.static.test.mjs is next to this file or there is no baseline
// commit: then it adds the block only. Comparison runs after the tests, and FlowGuard's lines follow the test
// summary. Python is found as flowguard.static.test.mjs finds it: FLOWGUARD_PYTHON, then the
// interpreter that ran `flowguard init` on this machine, recorded in @RECORDED@ (git-ignored), then `python3`,
// `python` and, on Windows, `py -3`.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, @ROOT@);
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
    const run = spawnSync(command, [...prefix, '-m', 'flowguard.intent.vitest', 'prepare', '--root', ROOT, '--package', HERE], {
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
    return ', '.join(parts)


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
    """Compare source-only functions after the session, using real JSON inputs and copy neighbours. Returns the
    rows, the reasons by point and, by same name, what the input limit left out (`signals.copy_inputs`)."""
    import subprocess
    from .signals import copy_inputs
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
    shared, cuts = {}, {}
    for name, peers in groups.items():
        if len(peers) < 2:
            continue
        # The same union as the pytest side, on the positions of the arguments.
        inputs, cuts[name] = copy_inputs([dict(enumerate(args)) for peer in peers for args in actual.get(peer['id'], ())],
                                         [number for peer in peers for number in peer['numbers']], LIMIT)
        shared[name] = [[row[index] for index in sorted(row)] for row in inputs]
    wanted, jobs, keys = {}, [], {}
    for ident, point in points.items():
        wanted[ident] = unique([*actual.get(ident, ()), *shared.get(point['name'], ())], None)
        for prior in (False, True):
            source, why = (point['old_source'], point['old_skip']) if prior else (point['source'], point['skip'])
            if why:
                # without a baseline nothing is compared with one, which the title says (D13)
                if not prior or why not in (point['skip'], NO_BASELINE):
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
    return rows, reasons, cuts


def _plain(encoded):
    """A recorded value (read by `value`) as the 4.3 lines spell it with `signals.value_text`: numbers, strings,
    booleans and None as they are; a thrown error {'raises': 'Name: message'}; a date its ISO text; a set or a map
    its JSON items as a list."""
    from datetime import datetime
    from . import cells as C
    def spelled(item):
        if isinstance(item, C.Raised):
            return {'raises': str(item.error)}
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, frozenset):
            return [json.loads(member) for member in sorted(item)]
        if isinstance(item, tuple):
            return [[json.loads(key), json.loads(member)] for key, member in item]
        if isinstance(item, list):
            return [spelled(member) for member in item]
        if isinstance(item, dict):
            return {key: spelled(member) for key, member in item.items()}
        return item
    return spelled(value(encoded))


def _shown(encoded):
    from .signals import value_text
    return value_text(_plain(encoded))


def judge(cfg, data, records, package=None):
    """What this run found, as the 4.3 block reads it (`delivered`): `delivery` holds same-name copies as family
    'same' (one member per input: red where this change broke a pair that agreed at the baseline, before where the
    copies already differed on that input, `signals.copy_partition`), the changed line of each changed function whose
    sealed run answers a recorded input differently than its baseline does, the rules bound to observed points (red
    where the code disagrees; their source through the gate of `Engine.run_rules`: red where this change broke it,
    before where it already failed at task start), an intent file that does not load and an invalid known.toml or
    rules.toml (red), one not compared item per point, copy group or rule that could not be compared, with its
    reasons, and what the change touches. `known` are the plan's known entries; `agreed` the same names whose copies
    this run compared on every copy and found to agree. `package` is the folder of the vitest run: a point in another
    package cannot be reached by its tests and is not listed as unreached."""
    from . import cache, cells as C, signals
    from .engine import CONFLICT, Engine, PredicateError, outcome_eq
    from .health import LINES_ONLY, Issue
    from .loader import load
    from .sources import cited, parse, source_state
    points = {point['id']: point for entry in data['files'].values() for point in entry['points']}
    rows, reasons_by_point, cuts = closed_rows(data, records)
    calls = {}
    for record in records:
        calls.setdefault(record['id'], []).append(record)
    issues, lines, unchecked = [], [], {}
    def skipped(subject, reasons, *, function='', places=()):
        entry = unchecked.setdefault((subject, function), dict(places=tuple(places), reasons=[]))
        entry['reasons'].extend(reason for reason in reasons if reason not in entry['reasons'])
    for item in data['unplanned']:
        if _inside(cfg, item['rel'], package):
            where = f'{item["rel"]}:{item["line"]}'
            skipped(f'{item["name"]} ({where})', [item['reason']], function=item['id'], places=(where,))
    for ident, point in points.items():
        where = f'{point["rel"]}:{point["target_line"]}'
        subject = f'{point["name"]} ({where})'
        collected = [dict(row, label=case_class(point, row['in'])) for row in rows.get(ident, ())]
        reasons = list(reasons_by_point.get(ident, []))
        if point['skip']:
            reasons.append(point['skip'])
        rows[ident] = collected
        copy_only = any(copy['id'] == ident for other in points.values() for copy in other['copies']
                        if calls.get(other['id']))
        if not calls.get(ident) and not collected:
            if point['skip'] and (copy_only or _inside(cfg, point['rel'], package)):
                skipped(subject, [point['skip']], function=ident, places=(where,))
            elif point['anchored'] and not copy_only and _inside(cfg, point['rel'], package):
                skipped(subject, ['not reached by any test'], function=ident, places=(where,))
            continue
        if not collected or not point['changed']:
            if reasons:
                skipped(subject, reasons, function=ident, places=(where,))
            continue
        actual_rows = [row for row in collected if row['actual']]
        compared = [row for row in actual_rows if not (isinstance(row['old'], dict) and '$missing' in row['old'])
                    and not (isinstance(row['old'], dict) and '$threw' in row['old'] and _same(row['old'], row['now']))]
        if any(isinstance(row['old'], dict) and '$threw' in row['old'] and _same(row['old'], row['now']) for row in actual_rows):
            reasons.append('both versions raised the same exception')
        changes = [row for row in compared if not _same(row['old'], row['now'])]
        if changes:
            lines.append(signals.changed_line(point['name'], ident, point['rel'], point['target_line'],
                                              [({name: _plain(item) for name, item in row['in']}, _plain(row['old']), _plain(row['now']))
                                               for row in changes], len(compared), unanchored=not point['anchored']))
        elif reasons or {row['label'] for row in compared} != {row['label'] for row in actual_rows}:
            # a replayed case class none of whose inputs could be compared is no evidence that it did not change
            skipped(subject, reasons or ['a case class could not be compared at the baseline'], function=ident, places=(where,))
    # Same-name copies share replayed inputs. Each input is judged on its own against the copies at the
    # baseline: an old disagreement on one input cannot hide a pair newly broken on another (design 4.5).
    for name, left in cuts.items():
        if cut := signals.copy_cut(name, LIMIT, left):
            skipped(name, [cut.removeprefix(name + ': ')])
    handled, agreed = set(), set()
    missing = lambda answer: isinstance(answer, dict) and '$missing' in answer
    threw = lambda answer: isinstance(answer, dict) and '$threw' in answer
    for ident, point in sorted(points.items(), key=lambda pair: not bool(calls.get(pair[0]))):
        if not point['copies'] or point['name'] in handled:
            continue
        handled.add(point['name'])
        group = [ident, *(copy['id'] for copy in point['copies'])]
        places = {target: f'{points[target]["rel"]}:{points[target]["fn"]}' for target in group}     # the 4.3 places
        reference = next((places[target] for target in group if points[target].get('owner')), None)
        samples = [row for row in rows.get(ident, ()) if row['same']]
        current_rows, whole = [], False
        for row in sorted(samples, key=_counterexample(point, [record for record in calls.get(ident, ()) if 'args' in record])):
            inputs = ', '.join(f'{key}={_shown(item)}' for key, item in row['in'])
            old = [(target, answer) for target, answer in [(ident, row['old']), *row['old_copies'].items()]
                   if points[target]['old_skip'] not in (ABSENT, NO_BASELINE)]
            answers = [(places[ident], row['now'])]
            for copy in point['copies']:
                theirs = row['copies'].get(copy['id'])
                if theirs is not None and not missing(theirs):
                    answers.append((places[copy['id']], theirs))
            if len(answers) < 2:
                continue
            if all(threw(answer) for _, answer in answers) and all(_same(answer, answers[0][1]) for _, answer in answers):
                skipped(point['name'], ['all copies raised the same exception'])
                continue
            whole = whole or len(answers) == len(group)
            current_rows.append((inputs, answers, {places[target]: (answer, threw(answer)) for target, answer in old if not missing(answer)},
                                 {places[target] for target, answer in old if missing(answer)}))
        fresh, old, unknown = signals.copy_partition(current_rows, _same, _shown, owner=reference, total=len(group),
                                                     words=signals.copy_says)
        if fresh or old:
            issues.append(signals.copies_issue(point['name'], fresh, old, places=list(places.values()),
                                               files={points[target]['rel'] for target in group}))
        if unknown:
            skipped(point['name'], [f'the baseline of a copy could not run; now on {where}: {text}' for where, text, _, _ in unknown])
        if whole and not (fresh or old or unknown):
            agreed.add(point['name'])
    # rules on the observed calls and replayed classes, as the pytest side checks a reading
    model = load(cfg)
    engine = Engine(model)
    # a rule's source is judged with this run's comparison commit, as in pytest: none outside Git, before the first
    # commit or for a recorded task start this repository lacks (whose commit the title still names)
    commit = None if data['baseline_kind'] == 'missing' else data['baseline']
    engine.baseline = commit
    for error in model.errors:
        place = f'{error["file"]}:{error["line"]}'
        issues.append(signals.finding('input', f'load:{place}', f'load {place}', [signals.ascii_text(error['msg'])],
                                      'correct this declaration; until then none of its file is checked',
                                      places=(place,), files=(error['file'],)))
    for rule in model.rules.values():
        homes = [home for home in rule.homes if getattr(home, 'anchor', None) is not None and home.anchor.target in points]
        if not homes:
            continue
        declared = f'{model.file_of[rule.id]}:{rule.line}'
        sites = [f'{points[home.anchor.target]["rel"]}:{points[home.anchor.target]["fn"]}' for home in homes]
        whats, at = [], []
        # The source gate of `Engine.run_rules`: a source this change broke (rule.<id> missing or invalid, its words
        # gone, a request superseded in this task) is red, one already broken at task start before; the rule's
        # expectations are checked as pytest's intent items check them. An unconfirmed source (assumed:, a request
        # not stored) adds nothing here, as before.
        state, reason = source_state(engine, rule, rule.confirmed, rule.quote)
        if state == 'red':
            whats.append(signals.ascii_text(reason))
        elif state == 'before':
            said = signals.ascii_text(reason)
            issues.append(Issue(f'source:{rule.id}', LINES_ONLY, f'source {rule.id}', f'source {rule.id}: {said}', signals.BEFORE_STEP,
                                files=frozenset({model.file_of[rule.id]}), family='source', subject=f'source {rule.id}',
                                parts=(('', declared, said, signals.BEFORE_STEP),), detail=(said,)))
        for home, site in zip(homes, sites):
            ident = home.anchor.target
            point = points[ident]
            observed = [({name: value(item) for name, item in row['in']}, value(row['now'])) for row in rows.get(ident, ())]
            observed += [({name: value(item) for name, item in zip(point['params'], record['args'])}, value(record['result']))
                         for record in calls.get(ident, ()) if 'args' in record and 'result' in record]
            usable = [(inputs, actual) for inputs, actual in observed
                      if all(name in inputs and C.kind_of(kind).accepts(inputs[name]) for name, kind in rule.fields.items())]
            if not usable:
                if calls.get(ident):
                    skipped(f'rule {rule.id}', [f'{point["name"]} ({site}) observation lacks the inputs this rule reads ({", ".join(rule.fields)})'])
                continue
            for inputs, actual in usable:
                cell = {name: inputs[name] for name in rule.fields}
                try:
                    expected = engine.effective(rule, cell)
                except PredicateError as error:
                    whats.append(str(error).removeprefix(rule.id + ': '))   # a predicate failing on an observed cell is red, as in pytest
                    at.append(site)
                    break
                if expected is CONFLICT or expected is None or outcome_eq(expected, actual):
                    continue
                whats.append(f'{C.show_cell(cell)} -> rule {C.show(expected)}, code {C.show(actual)} at {site}')
                at.append(site)
                break
        if whats:
            # One red line per rule (D30), its first step from `signals.rule_steps`, the others and the owner's words in
            # its detail, as pytest says a rule's red.
            steps = [step.rstrip('; ') for step in signals.rule_steps(rule.id, ', '.join(sites), declared, whats)]
            source = cited(parse(rule.source), cfg)
            issues.append(signals.finding('rule', f'rule:{rule.id}', f'rule {rule.id}', whats, steps[0] if steps else '',
                                          places=tuple(dict.fromkeys((declared, *at, *sites))), files=(model.file_of[rule.id],),
                                          detail=[*steps, f'{rule.id} source: {source.quote or source.text}']))
    issues += [_issue(fields) for fields in data['inputs']]
    lines += [signals.not_compared(subject, entry['reasons'], function=function, places=entry['places'])
              for (subject, function), entry in unchecked.items()]
    # What the change touches: the files it changed (read now: an intent file's or a document's change does not
    # change the plan), the TS/JS declarations it added, edited or removed, the changed points, and the members of
    # same-name copies one of whose files it changed (a before line needs that, 4.7).
    touched_files = frozenset(_differs(cfg, commit)) if commit else frozenset()
    touched = {*data['touched'], *(ident for ident, point in points.items() if point['changed'])}
    touched |= {part[0] for issue in issues if issue.family == 'same' and issue.files & touched_files for part in issue.parts}
    # How far HEAD lies after a recorded task start is read now, by the one git call of pytest's title, and not
    # kept in the plan, whose key is the commit and its kind: the title says it as pytest's does.
    kind = data['baseline_kind']
    start = cache.task_start(cfg) if kind == 'task' else (None, None, None)
    return dict(baseline=data['baseline'], baseline_kind=kind,
                baseline_ahead=start[2] if start[:2] == (data['baseline'], 'task') else None,
                delivery=signals.delivery(issues, lines, touched_functions=touched, touched_files=touched_files,
                                          ran={f'same:{name}' for name in agreed}),
                known=[_known(fields) for fields in data['known']], agreed=agreed)


def delivered(result):
    """(lines, ignored, said) of a judged run (`judge`) through `signals.deliver`, with the plan's known entries: one
    naming same-name copies this run compared on every copy and found to agree is `known fixed?` (the delivery's
    `ran` names them; only a vitest run compares TypeScript copies). `said` are the known entries one of the lines
    speaks for."""
    from . import signals
    part = result['delivery']
    lines, ignored = signals.deliver(part['issues'], touched_functions=part['touched_functions'], touched_files=part['touched_files'],
                                     known=result['known'], ran=part['ran'], extra=part['lines'])
    red = {line.name for line in lines if line.kind == 'red'}
    said = {line.name for line in lines if line.kind in ('known', 'known fixed?')}
    said |= {f'known.{entry.id}' for entry in result['known'] if entry.finding in red}
    return lines, ignored, said


SESSION = 'report.json'           # in the observations folder: what the session test judged, for the teardown
STATIC = 'static.json'            # in the observations folder: the map checks of flowguard.static.test.mjs (signals.last_run)
STATIC_TEST = 'flowguard.static.test.mjs'       # the static test init writes next to a vitest package.json
NOT_RUN = 'map checks did not run in this vitest run'


def static_lines(observations):
    """The saved map checks of this vitest run (the `signals.last_run` payload with its `title_parts` that
    `check --static` writes for flowguard.static.test.mjs into the observations folder), its lines as `signals.Line`;
    None when the static test did not run in it. The report reads its lines, seconds, ignored count, deprecated
    features and hidden leads."""
    from .signals import KINDS, Line
    path = Path(observations) / STATIC
    if not path.is_file():
        return None
    saved = json.loads(path.read_text(encoding='utf-8'))
    lines = [Line(**dict(line, places=tuple(line['places']), detail=tuple(line['detail']))) for line in saved['lines']]
    for line in lines:
        if line.kind not in KINDS:
            raise ValueError(f'{path}: {line.name}: kind {line.kind!r} is not one of signals.KINDS')
    return dict(saved, lines=lines)


def merged(own, static, said):
    """The block's lines: this run's, then those of the map checks (`static_lines`), each (kind, name, function) once
    and in KINDS order; a known entry this run already speaks for (`said`) keeps this run's line only, except that a
    `known fixed?` of the map checks is always listed (D8) and replaces this run's `known` line of its entry: the map
    checks judged that entry's finding in the whole project and found it gone, while this run's line only says that
    the change touches the entry's sites (no check of this run judges a family the map checks run)."""
    from .signals import KINDS
    fixed = {line.name for line in static if line.kind == 'known fixed?'}
    unique = {}
    for line in [*(line for line in own if not (line.kind == 'known' and line.name in fixed)),
                 *(line for line in static if not (line.kind == 'known' and line.name in said))]:
        unique.setdefault((line.kind, line.name, line.function), line)
    return sorted(unique.values(), key=lambda line: KINDS.index(line.kind))


def _wired(cfg, package):
    """Whether the package of this vitest run has the static test init writes (which, when it runs in this run,
    saves its map checks into the observations folder)."""
    path = (Path(package) if package else cfg.root) / STATIC_TEST
    return path.is_file() and path.read_text(encoding='utf-8-sig').startswith(INIT_MARK)


def _save_last(cfg, payload):
    """Keep this run's lines for `show --last` (`cache.save_last`)."""
    import sqlite3
    from contextlib import closing
    from .cache import save_last
    from ..map.common import cache_dir
    cache_dir(cfg.root)
    with closing(sqlite3.connect(cfg.cache / 'map.sqlite', timeout=30)) as con:
        con.execute('CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)')
        with con:
            save_last(con, payload)


def report(root, plan_path, observations, package=None, *, in_test=False):
    """Judge this run's observations, merge the map checks the static test saved in this run, print the 4.3 block
    (`signals.render_block`, a place named by the shortest end of its path no other file of the repository has) and
    keep its lines for `show --last`; 1 when a line is red. The first line's time is FlowGuard's own: the preparation,
    the recording, this report and the static test's map checks. `in_test` is the session test (session.test.mjs,
    run after the project's tests): it keeps the observations and saves the block, its status and the number of its
    reds the static test did not already fail on, for the session test and the teardown, which prints the block after
    vitest's summary instead of judging again."""
    import os
    from . import deprecation, signals
    from .config import load_config
    from .differences import display
    from ..map.common import git_files
    started = time.perf_counter()
    since = deprecation.mark()
    cfg = load_config(root)
    data = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    records = _observations(observations)
    recorded = sum(record.get('record_seconds', 0) for record in records)
    result = judge(cfg, data, [record for record in records if 'id' in record], package)
    own, ignored, said = delivered(result)
    static = static_lines(observations)
    if static is None and _wired(cfg, package):
        # D19: the static test is wired but did not run here (a filtered run, or one written by an older init)
        rel = cfg.rel((Path(package) if package else cfg.root) / STATIC_TEST)
        own.append(signals.not_compared(rel, [NOT_RUN], places=(rel,)))
    lines = merged(own, static['lines'] if static else [], said)
    carried = {(line.kind, line.name, line.function) for line in static['lines']} if static else set()
    red = sum(line.kind == 'red' for line in lines)
    mine = sum(line.kind == 'red' and (line.kind, line.name, line.function) not in carried for line in lines)
    files = git_files(cfg.root)         # the repository's files, which no shortened path of the block may name
    seconds = (float(os.environ.get('FLOWGUARD_VITEST_PREPARE_SECONDS', 0)) + recorded + (static['seconds'] if static else 0)
               + time.perf_counter() - started)
    heading = signals.title(lines, baseline=result['baseline'], kind=result['baseline_kind'], ahead=result['baseline_ahead'],
                            seconds=seconds)
    text = signals.render_block(lines, title=heading, files=files)
    _save_last(cfg, signals.last_run(lines, ignored + (static['ignored'] if static else 0), run='vitest', stamp=time.time(),
                                     baseline=result['baseline'], kind=result['baseline_kind'], title=heading, seconds=seconds,
                                     deprecated=list(dict.fromkeys([*deprecation.used(since), *(static['deprecated'] if static else ())])),
                                     hidden=static['hidden'] if static else ()))
    status = 1 if red else 0
    if in_test:
        (Path(observations) / SESSION).write_text(json.dumps(dict(text=text, status=status, red=mine), ensure_ascii=False),
                                                  encoding='utf-8')
    else:
        shutil.rmtree(observations)     # this run's records are read; the next run starts empty
        display(text)
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m flowguard.intent.vitest')
    parser.add_argument('step', choices=('prepare', 'report'))
    parser.add_argument('--root', required=True)
    parser.add_argument('--plan')
    parser.add_argument('--observations')
    parser.add_argument('--package', help='The folder of the vitest run (its vite root); for prepare, of its vitest config')
    parser.add_argument('--in-test', action='store_true', help='Run by the session test: keep the observations')
    options = parser.parse_args(argv)
    if options.step == 'prepare':
        print(json.dumps(prepare(options.root, options.package), ensure_ascii=False))
        return 0
    if not options.plan or not options.observations:
        parser.error('report needs --plan and --observations')
    return report(options.root, options.plan, options.observations, options.package, in_test=options.in_test)


if __name__ == '__main__':
    sys.exit(main())
