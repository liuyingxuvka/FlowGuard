"""Parse legacy target PLAN lines and check their concrete owner/source evidence."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import re
import subprocess

from .common import Finding, normalize_newlines, read_source, sha256_bytes
from .mapfile import MapError, model_registry, resolve_model_path
from .modelstatic import StaticModel
from .requests import REQUEST_DIR, _metadata, glossary_entries, validate_request_links

PLAN_RELPATH = Path('.flowguard/target/PLAN.txt')
_CHANGE = re.compile(r'changes:\s+(\S+)\s+(?:by\s+(\S+)|because)\s+"(.+)"\s*\Z')
_TOUCH = re.compile(r'touch:\s+(.+?)(?:\s+because\s+"(.+)")?\s*\Z')


def quote_matches(text: str, quote: str) -> bool:
    """Compare owner words exactly, permitting only whitespace runs and ... elision."""
    source = ' '.join(text.split())
    position = 0
    for fragment in quote.split('...'):
        fragment = ' '.join(fragment.split())
        found = source.find(fragment, position)
        if found < 0:
            return False
        position = found + len(fragment)
    return bool(quote.strip())


def _terms(value):
    value = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', value)
    value = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', value)
    return {word[:-1] if word.endswith('s') and len(word) > 1 else word
            for word in re.findall(r'[a-z]+|[\u4e00-\u9fff]+', value.lower())}


def rule_info(root, target, view, *, current_data=None, only_target=True):
    """Target rule identities and reads from the existing static model owner."""
    info = {}
    data = view.data if view is not None else current_data
    for entry in model_registry(root, data, view=view).entries:
        if entry.kind != 'contract' or only_target and Path(entry.path).name not in target.models:
            continue
        path = resolve_model_path(root, entry.path, view=view)
        if path is None:
            continue
        try:
            static = StaticModel(root, entry.path, ast.parse(read_source(path)), view=view)
            rules = static.explorer_rules()
        except (OSError, SyntaxError, ValueError, TypeError):
            continue
        for name, _ in rules or ():
            words = set().union(*(_terms(item) for item in static.rule_read_names(name)), _terms(name))
            info[entry.id + '.' + name] = dict(definition=static.rule_defs.get(name), terms=words)
    return info


def record_evidence(root, current, target, view, items):
    """Keep the checked lines and the same static rule identities used by PLAN."""
    before = rule_info(root, target, None, current_data=current, only_target=False)
    after = rule_info(root, target, view, only_target=False)
    models = [{entry.id for entry in model_registry(root, data, view=planned).entries
               if entry.kind == 'contract'} for data, planned in ((current, None), (view.data, view))]
    def fingerprint(info, name, known_models):
        if name in info:
            definition = info[name]['definition']
            return 'fp:' + sha256_bytes(definition.encode()) if definition is not None else 'unknown: static definition unavailable'
        model = name.rpartition('.')[0]
        return None if model not in known_models or any(key.rpartition('.')[0] == model for key in info) else 'unknown: static rule names unavailable'
    origins = {}
    for item in items:
        if item['kind'] == 'changes':
            name = item['model'] + '.' + item['rule']
            origin = 'owner ' + item['request'] if item['request'] else 'because ' + item['reason']
            origins.setdefault(name, []).append(origin)
    rules = []
    for name in sorted(before.keys() | after.keys() | origins.keys()):
        old, new = fingerprint(before, name, models[0]), fingerprint(after, name, models[1])
        if old != new or name in origins:
            rules.append(dict(id=name, old=old, new=new,
                              provenance='; '.join(dict.fromkeys(origins[name])) if name in origins else
                              'unjudged: no checked PLAN changes line'))
    return [dict(line=item['line'], added_after_code=None, cleared=[]) for item in items], rules


def function_identities(text: str) -> dict[str, str | None] | None:
    """Whole-function ASTs keep signatures/decorators and omit scoped docstrings."""
    try:
        syntax = ast.parse(normalize_newlines(text.encode('utf-8')))
    except (SyntaxError, ValueError, UnicodeError):
        return None
    class WithoutDocstrings(ast.NodeTransformer):
        def scope(self, node):
            self.generic_visit(node)
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
            return node
        visit_FunctionDef = scope
        visit_AsyncFunctionDef = scope
        visit_ClassDef = scope
    syntax = WithoutDocstrings().visit(copy.deepcopy(syntax))
    definitions = {}
    def visit(node, prefix=''):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = prefix + node.name
            if not isinstance(node, ast.ClassDef):
                definitions.setdefault(name, []).append(ast.dump(node, include_attributes=False))
            prefix = name + '.'
        for child in ast.iter_child_nodes(node):
            visit(child, prefix)
    visit(syntax)
    return {name: sha256_bytes(values[0].encode('utf-8')) if len(values) == 1 else None
            for name, values in definitions.items()}


def _touch_problem(root, path, symbol):
    try:
        relative = (root / path).resolve().relative_to(root).as_posix()
        current = function_identities(read_source(root / relative))
        base = json.loads((root / '.flowguard/target/base.json').read_bytes())
    except (OSError, ValueError, SyntaxError, TypeError):
        return 'the function or its target-start baseline is unavailable'
    if not isinstance(base, dict):
        return 'the target-start function baseline is unknown'
    if current is None:
        return 'the current function AST is unavailable'
    if symbol not in current:
        return 'the named function is absent from the current source'
    if current[symbol] is None:
        return 'the named function has ambiguous same-name definitions'
    if isinstance(base.get('git'), str):
        try:
            previous = subprocess.run(['git', '-C', str(root), 'show', f'{base["git"]}:./{relative}'], capture_output=True)
            if previous.returncode:
                known = subprocess.run(['git', '-C', str(root), 'cat-file', '-e', base['git'] + '^{commit}'], capture_output=True)
                if known.returncode:
                    return 'the historical Git baseline is unavailable'
                old = {}
            else:
                old = function_identities(normalize_newlines(previous.stdout).decode('utf-8-sig'))
        except (OSError, UnicodeError, SyntaxError, ValueError):
            return 'the historical function AST is unavailable'
        if old is None:
            return 'the historical function AST is unavailable'
    elif isinstance(base.get('files'), dict):
        entry = base['files'].get(relative)
        old = {} if entry is None else entry.get('functions') if isinstance(entry, dict) else None
        if not isinstance(old, dict):
            return 'this older target has no per-function baseline; the change is unknown'
    else:
        return 'the target-start function baseline is unknown'
    if symbol in old and old[symbol] is None:
        return 'the target-start function has ambiguous same-name definitions'
    return 'the function is unchanged since target start' if old.get(symbol) == current[symbol] else None


def _glossaries(root):
    found = []
    for path in sorted((root / REQUEST_DIR).glob('*.json')):
        try:
            item = _metadata(path, path.stem)
            if item['kind'] != 'glossary':
                continue
            validate_request_links(root, [dict(id=path.stem, part=True)])
            for word, terms in glossary_entries(path.with_suffix('.md').read_bytes()):
                found.append(dict(id=path.stem, word=word, terms=list(terms)))
        except (OSError, ValueError, KeyError, TypeError, MapError):
            continue  # The existing request-integrity check reports malformed stored files.
    return found


def _shared_terms(quote, terms, glossaries):
    chinese = re.search(r'[\u4e00-\u9fff]', quote) is not None
    direct = any(term.lower() in quote.lower() for term in terms) if chinese else bool(_terms(quote) & terms)
    if direct:
        return True, []
    used = []
    for item in glossaries:
        words = set().union(*(_terms(term) for term in item['terms']))
        word = item['word']
        present = word.lower() in quote.lower() if chinese else bool(re.search(r'\b' + re.escape(word) + r'\b', quote, re.I))
        if present and words & terms:
            used.append(item)
    return direct or bool(used), used


def check_plan(root, target, view):
    """Validate every line once; the target owner routes plan_item_not_done as TO-DO."""
    root = Path(root).resolve()
    path = root / PLAN_RELPATH
    if not path.exists():
        return [], []
    try:
        lines = path.read_text(encoding='utf-8-sig').splitlines()
    except (OSError, UnicodeError) as error:
        return [], [Finding('error', 'line_syntax', 'target', f'{path}: {error}')]
    items, findings = [], []
    rules, glossaries = None, None
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        where = f'PLAN.txt:{number}'
        if line.startswith('touch:'):
            match = _TOUCH.fullmatch(line)
            given, reason = match.groups() if match else ('', None)
            source, separator, symbol = given.rpartition(':')
            if (not separator or not source.strip() or not all(part.isidentifier() for part in symbol.strip().split('.'))
                    or reason is not None and not reason.strip()):
                findings.append(Finding('error', 'line_syntax', 'target', f'{where}: expected touch: <path>:<qualified name> [because "<reason>"]'))
                continue
            item = dict(kind='touch', line=raw, number=number, path=source.strip(), function=symbol.strip(), reason=reason)
            problem = _touch_problem(root, item['path'], item['function'])
            if problem:
                findings.append(Finding('error', 'plan_item_not_done', 'target', f'{where}: {given}: {problem}'))
            items.append(item)
            continue
        match = _CHANGE.fullmatch(line)
        if not match:
            findings.append(Finding('error', 'line_syntax', 'target', f'{where}: expected changes: <model>.<rule> by <id> "<quote>" or changes: <model>.<rule> because "<reason>"'))
            continue
        name, identifier, text = match.groups()
        if not text.strip():
            findings.append(Finding('error', 'line_syntax', 'target', f'{where}: quote or reason must be nonempty'))
            continue
        if rules is None:
            rules = rule_info(root, target, view)
        if name not in rules:
            findings.append(Finding('error', 'line_syntax', 'target', f'{where}: {name} is not a rule of a model in the target'))
            continue
        model, _, rule = name.rpartition('.')
        item = dict(kind='changes', line=raw, number=number, model=model, rule=rule,
                    request=identifier, quote=text if identifier else None, reason=None if identifier else text,
                    glossary_used=[])
        if identifier:
            try:
                validate_request_links(root, [dict(id=identifier, part=True)])
                owner = (root / REQUEST_DIR / (identifier + '.md')).read_bytes().decode('utf-8-sig')
                if not quote_matches(owner, text):
                    findings.append(Finding('error', 'quote_not_in_request', 'target', f'{where}: {text!r} is not in {identifier}; quote the request verbatim (... elides)'))
                else:
                    shared, used = _shared_terms(text, rules[name]['terms'], [])
                    if not shared:
                        if glossaries is None:
                            glossaries = _glossaries(root)
                        shared, used = _shared_terms(text, rules[name]['terms'], glossaries)
                    item['glossary_used'] = used
                    if not shared:
                        findings.append(Finding('error', 'link_without_shared_term', 'target', f'{where}: the quote shares no term with {name}'))
            except MapError as error:
                findings.append(Finding('error', str(error).split(':', 1)[0], 'target', f'{where}: {error}'))
            except (OSError, UnicodeError) as error:
                findings.append(Finding('error', 'quote_not_in_request', 'target', f'{where}: cannot read {identifier} as UTF-8: {error}'))
        items.append(item)
    return items, findings


def static_plan_rows(root, target, view):
    """Reuse PLAN parsing; static edits never stand for a completed check."""
    path = Path(root) / PLAN_RELPATH
    if not path.exists():
        return []
    items, findings = check_plan(root, target, view)
    by_line = {item['number']: item for item in items}
    rows = []
    for source_line, raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        item = by_line.get(source_line)
        problems = [finding.message for finding in findings
                    if finding.message.startswith(f'PLAN.txt:{source_line}:')]
        state = 'static, now'
        if item is None or problems:
            state = ('not edited' if item and item['kind'] == 'touch'
                     and all('unchanged since target start' in problem for problem in problems) else 'unknown')
        elif item['kind'] == 'touch':
            state = 'edited, not verified'
        rows.append(dict(number=len(rows) + 1, source_line=source_line, line=raw,
                         state=state, known_from='static, now', problems=problems,
                         added_after_code=None))
    return rows


def _rule_sources(root, data, requested, *, view=None, fallback=None):
    """Known absence differs from an unreadable model or rule definition."""
    sources, paths = {}, {}
    entries = {entry.id: entry for entry in model_registry(root, data, view=view).entries
               if entry.kind == 'contract'}
    for model in sorted({name.rpartition('.')[0] for name in requested}):
        names = {name for name in requested if name.rpartition('.')[0] == model}
        entry = entries.get(model)
        if entry is None:
            previous = root / fallback[model] if fallback and model in fallback else None
            text = '(unknown: the previous model is unreadable)' if previous is not None and previous.exists() else '(absent: this model did not exist)'
            sources.update((name, text) for name in names)
            continue
        paths[model] = entry.path
        try:
            path = resolve_model_path(root, entry.path, view=view)
            if path is None:
                raise ValueError('model source is unavailable')
            static = StaticModel(root, entry.path, ast.parse(read_source(path)), view=view)
            rules = static.explorer_rules()
            if rules is None:
                raise ValueError('static rule names are unavailable')
            available = {name for name, _ in rules}
            for name in names:
                rule = name.rpartition('.')[2]
                sources[name] = ('(absent: this rule did not exist)' if rule not in available else
                                 static.rule_source(rule) or '(unknown: static rule source is unavailable)')
        except (OSError, SyntaxError, ValueError, TypeError) as error:
            sources.update((name, f'(unknown: {error})') for name in names)
    return sources, paths


def render_owner_block(root, current_data, target, view, items):
    """Show checked PLAN evidence unchanged; never add a judgment or owner claim."""
    if not items:
        return ''
    root = Path(root).resolve()
    changes = {item['model'] + '.' + item['rule'] for item in items if item['kind'] == 'changes'}
    new, paths = _rule_sources(root, view.data, changes, view=view) if changes else ({}, {})
    old, _ = _rule_sources(root, current_data, changes, fallback=paths) if changes else ({}, {})
    lines = ['owner block (paste it unchanged into your final message):']
    owner_rules, shown_full = None, set()
    try:
        base = json.loads((root / '.flowguard/target/base.json').read_bytes())
        current_started = base.get('started') if isinstance(base, dict) else None
    except (OSError, ValueError):
        current_started = None
    if not isinstance(current_started, str) or not current_started:
        current_started = None

    def context(identifier):
        metadata = _metadata(root / REQUEST_DIR / (identifier + '.json'), identifier)
        captured = metadata.get('stored_during')
        if not isinstance(captured, dict):
            return None
        received = metadata.get('received') or 'unknown time'
        started, goal = captured.get('started'), captured.get('goal')
        known_start = isinstance(started, str) and bool(started)
        if known_start and current_started is not None and goal == target.goal and started == current_started:
            return 'stored during this change at ' + received
        description = repr(goal) if isinstance(goal, str) and goal else '(unknown goal)'
        timing = started if known_start else 'unknown'
        if known_start and current_started is not None and isinstance(goal, str) and goal:
            return f'stored during another change {description} (started {timing}) at {received}'
        return f'stored during change {description} (started {timing}) at {received}; relation to this change unknown'

    def full_text(identifier):
        if identifier not in shown_full:
            shown_full.add(identifier)
            lines.append('  full request ' + identifier + ':')
            text = (root / REQUEST_DIR / (identifier + '.md')).read_bytes().decode('utf-8-sig')
            lines.extend('    ' + line for line in text.splitlines())

    def owner_rule(name):
        nonlocal owner_rules
        if owner_rules is None:
            from .records import change_records
            owner_rules = {rule.get('id') for _, record in change_records(root)
                           for rule in record['rules'] if isinstance(rule, dict)
                           and isinstance(rule.get('provenance'), str)
                           and rule['provenance'].startswith('owner ')}
        return name in owner_rules

    for item in items:
        lines.append('- ' + item['line'])
        if item['kind'] != 'changes':
            continue
        name = item['model'] + '.' + item['rule']
        identifier = item.get('request')
        mark = context(identifier) if identifier else None
        if mark:
            lines.append('  ' + identifier + ': ' + mark)
            if owner_rule(name):
                full_text(identifier)
        for label, text in (('old', old[name]), ('new', new[name])):
            lines.append('  ' + label + ' rule:')
            lines.extend('    ' + line for line in text.splitlines())
        for glossary in item.get('glossary_used', []):
            source = glossary['id']
            lines.append('  glossary ' + source + ': ' + glossary['word'] + ' = ' + ', '.join(glossary['terms']))
            glossary_mark = context(source)
            if glossary_mark:
                lines.append('  ' + source + ': ' + glossary_mark)
                if owner_rule(name):
                    full_text(source)
    return '\n'.join(lines)
