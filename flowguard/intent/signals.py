"""Small, bounded views over comparison facts; never runs application code."""
from __future__ import annotations

from collections import defaultdict
import re
from decimal import Decimal, InvalidOperation

from . import cells as C


def _short(text, width=100):
    text = ' '.join(str(text).split())
    return text if len(text) <= width else text[:width - 1] + '…'


def _shown(value):
    return C.show(value)


def constraint(message, rule=None):
    """Keep the independent expected/actual witness before a long source name."""
    if rule is None:
        rule, separator, body = message.partition(': ')
        if not separator:
            return message
    else:
        body = message
    if 'smallest ' in body and ' -> rule ' in body:
        before, _, witness = body.partition('smallest ')
        body = 'smallest ' + witness + '；' + before
    return str(rule) + '：' + body


def _example(row):
    if 'witness' in row:
        return ', '.join(f'{name}={value}' for name, value in row['witness'].items())
    return ', '.join(f'{name}={_shown(value)}' for name, value in row.get('inputs', {}).items()) or '无记录'


def _changes(item):
    records = item.get('changes', item.get('changed', ()))
    for change in records if isinstance(records, (list, tuple)) else ():
        if isinstance(change, dict):
            yield change
        else:
            inputs, before, after = change
            yield dict(inputs=inputs, before=before, after=after)


def _points(values):
    """Exact finite values only; gaps never become asserted continuous intervals."""
    if values and all(type(value) is int for value in values):
        ordered, spans = sorted(set(values)), []
        first = last = ordered[0]
        for value in ordered[1:]:
            if value == last + 1:
                last = value
            else:
                spans.append(str(first) if first == last else f'{first}–{last}')
                first = last = value
        spans.append(str(first) if first == last else f'{first}–{last}')
        return ','.join(spans)
    return ','.join(dict.fromkeys(_shown(value) for value in values))


def _region(rows):
    if rows[0].get('region'):
        labels = list(dict.fromkeys(row.get('region', '') for row in rows))
        return labels[0] + (f' 等 {len(labels)} 类' if len(labels) > 1 else '')
    names = tuple(rows[0].get('inputs', {}))
    values = {name: list(dict.fromkeys(row['inputs'][name] for row in rows)) for name in names}
    combinations = 1
    for choices in values.values():
        combinations *= len(choices)
    actual = {tuple(_shown(row['inputs'][name]) for name in names) for row in rows}
    if combinations != len(actual):
        # Correlated axes must not be presented as their Cartesian product. Two integer inputs equal in
        # every row are one relation, when the rows are exactly that relation times the other values.
        equal = [(left, right) for index, left in enumerate(names) for right in names[index + 1:]
                 if all(type(row['inputs'][left]) is int and row['inputs'][left] == row['inputs'][right] for row in rows)]
        if len(equal) == 1:
            left, right = equal[0]
            rest = [name for name in names if name not in equal[0]]
            product = len(values[left])
            for name in rest:
                product *= len(values[name])
            if product == len(actual):
                return '，'.join([f'{left}={right}（{_points(values[left])}）', *(f'{name}={_points(values[name])}' for name in rest)])
        return _example(rows[0])
    return '，'.join(f'{name}={_points(choices)}' for name, choices in values.items())


def _cause(cause):
    if not cause:
        return ''
    if isinstance(cause, str):
        return '原因：' + cause
    return (f'原因：{cause.get("name", "代码")} {_shown(cause.get("before"))} → {_shown(cause.get("after"))}'
            f'（{cause["file"]}:{cause["line"]}）')


def _unknown(item):
    status = item.get('comparison_status', item.get('status'))
    return (not item.get('complete', False) or status not in (None, 'ok', 'red')
            or bool(item.get('comparison_reasons') or item.get('reasons')))


def _facts(item, *, comparison=False):
    """The parts every view of one observed point shares: name, place, counts, first change, cause."""
    changes = list(_changes(item))
    total = item.get('total', len(item.get('rows', ())))
    count = item.get('changed', len(changes))
    count = len(count) if isinstance(count, (list, tuple)) else count
    name = item.get('name', item.get('anchor', changes[0].get('anchor', '') if changes else ''))
    if item.get('unanchored'):
        name += '（未挂锚点，自动）'
    location = f'（{item["file"]}:{item["line"]}）' if item.get('file') and item.get('line') else ''
    if comparison:
        first = changes[0] if changes else item
        left, right = first.get('before_target'), first.get('after_target')
        location = f'（{left} ↔ {right}）' if left and right else location
    status = item.get('comparison_status', item.get('status'))
    reasons = list(dict.fromkeys([*item.get('comparison_reasons', ()), *item.get('reasons', ())]))
    unknown = not item.get('complete', False) or status not in (None, 'ok', 'red') or bool(reasons)
    checked = item.get('checked', len(item.get('rows', ())) if status == 'ok' else len(changes))
    summary = (f'候选 {total} 类，已比较 {checked} 类；比较未完成，已证变化 {count} 类' if unknown
               else f'共 {total} 类，变 {count} 类')
    change = overall = ''
    if changes:
        groups = defaultdict(list)
        for row in changes:
            groups[(str(row['before']), str(row['after']))].append(row)

        def smallest(members):
            row = members[0]
            if row.get('inputs'):
                points = {key: sorted({entry['inputs'][key] for entry in members}, key=C._k) for key in row['inputs']}
                least = C.smallest([entry['inputs'] for entry in members], points)
                row = next(entry for entry in members if entry['inputs'] == least)
            return row
        members = next(iter(groups.values()))
        row = smallest(members)
        change = (f'{_region(members)}；函数返回值 {row["before"]} → {row["after"]}（例：{_example(row)}）'
                  + (f'；另 {len(groups) - 1} 组结果变化' if len(groups) > 1 else ''))
        overall = change
        if len(groups) > 1:
            row = smallest(changes)
            overall = (f'{_region(changes)}；函数返回值有 {len(groups)} 种变化（例：{_example(row)}：'
                       f'{row["before"]} → {row["after"]}）')
    return dict(name=name, location=location, count=count, total=total, checked=checked, unknown=unknown,
                summary=summary, change=change, overall=overall, cause=_cause(item.get('cause')), reasons=reasons, status=status)


def _block(item, *, comparison=False, same_name=False):
    facts = _facts(item, comparison=comparison)
    title = f'{facts["name"]}{facts["location"]}：' if facts['name'] or facts['location'] else ''
    if comparison and facts['count']:
        title = ('红 同名锚点 ' if same_name else '红 对比 ') + title
    lines = [title + facts['summary']]
    if facts['change']:
        lines.append(facts['change'])
    if facts['cause']:
        lines.append(facts['cause'])
    if facts['reasons'] and len(lines) < 3:
        lines.append('未覆盖：' + '; '.join(facts['reasons']))
    return lines[:3]


def render(report, limit=10):
    """A test run's report (`session`) prints red, then changes, leads and what stayed unverified;
    a single comparison keeps its bounded block view. Full facts remain in the report.

    The fallback ledger's red lines come first, complete and untruncated, each with the entry to copy;
    they do not count against the ten-line budget of the other signals. The `--all` listing of open
    structure problems (`structure`) comes last, complete as well."""
    if report.get('session'):
        text = _session(report, limit)
        return '\n'.join([*([text] if text else []), *report.get('structure', ())])
    ledger = list(report.get('ledger', ()))
    structure = list(report.get('structure', ()))
    rest = _render(report, limit, quiet=bool(ledger or structure))
    return '\n'.join([*ledger, *([rest] if rest else []), *structure])


# ---- the end-of-test view ------------------------------------------------------------------------
# Four kinds, in this order: 红 (every red, the places of one rule or owner on one line, each followed
# by the next step to copy), 变 (changed outcomes and paths), 线索 (leads) and 未验证 (grey, merged
# and counted). The last three share ten lines; names and places are never shortened.

def red(subject, *texts, next=()):
    """One red finding as report text (`SUBJECT：text`) and its next steps keyed by the subject.

    Reports keep red findings as text; `steps` carries the lines to copy under the merged red line."""
    return (subject + '：' if subject else '') + '；'.join(texts), {subject: list(next)} if subject and next else {}


def _red_entry(message):
    text = str(message)
    subject, marker, quote = text.partition(' 出处：')
    if marker and subject and '：' not in subject and ': ' not in subject:
        return dict(subject=subject, separator='：', texts=[], quote=quote)
    for separator in ('：', ': '):
        head, found, rest = text.partition(separator)
        if found and head and len(head) <= 60 and '=' not in head and '\n' not in head:
            parts = [part.strip().rstrip(';').strip().removeprefix('smallest ') for part in rest.split('；') if part.strip().rstrip(';')]
            return dict(subject=head, separator=separator, texts=parts, quote='')
    return dict(subject='', separator='', texts=[text], quote='')


def _red_lines(report, items):
    entries, order, compared = {}, [], []
    steps = dict(report.get('steps', {}))
    messages = [*report.get('red', ()), *(message for item in items for message in item.get('red', ()))]
    for item in items:
        if item.get('comparison') and _facts(item, comparison=True)['count']:
            # A source comparison keeps its block title: `红 同名锚点 NAME（left ↔ right）：counts：first change`.
            facts = _facts(item, comparison=True)
            same = item.get('same_name') or report.get('same_name')
            compared.append(('红 同名锚点 ' if same else '红 对比 ') + f'{facts["name"]}{facts["location"]}：{facts["summary"]}：{facts["overall"]}')
            if same:
                compared.append('    让这几处一致；行为本来就该不同时，改用不同的锚点名并写 distinct')
    for message in messages:
        entry = _red_entry(message)
        key = entry['subject'] or ('', len(order))
        if key not in entries:
            entries[key] = entry
            order.append(key)
            continue
        merged = entries[key]
        merged['texts'] += entry['texts']
        merged['quote'] = merged['quote'] or entry['quote']
    lines = []
    for key in order:
        entry = entries[key]
        body = '；'.join(dict.fromkeys(entry['texts']))
        line = '红：' + (entry['subject'] + (entry['separator'] + body if body else '') if entry['subject'] else body)
        if entry['quote']:
            line += f'  {entry["subject"]} 出处：{entry["quote"]}'
        lines.append(line)
        lines.extend('    ' + step for step in steps.get(entry['subject'], ()) if entry['subject'])
    for finding in report.get('ledger_red', ()):
        lines.append('红：' + finding['text'])
        lines.extend('    ' + step for step in finding['fix'])
    return lines + compared


def _lead_line(lead):
    if not isinstance(lead, dict):
        return '线索：' + str(lead)
    locations = lead.get('locations', ())
    if not locations:
        return ''
    values = ','.join(dict.fromkeys(_shown(row['old']) for row in locations))
    return (f'线索：旧值 {values} 还出现在 {lead["total"]} 个判断里：'
            + '  '.join(f'{row["file"]}:{row["line"]}' + ('（大函数中）' if row.get('big') else '') for row in locations)
            + ' → 需求变了就一起改；要锁定它们，在负责人上方写 # flowguard: owner 名，副本上方写 # flowguard: sensor 名')


def _fit(lines, room, overflow):
    if room <= 0:
        return []
    if len(lines) <= room:
        return lines
    return lines[:room - 1] + [overflow(len(lines) - room + 1)]


def _session(report, limit):
    budget = min(10, max(1, limit))
    items = list(report.get('items', ()))
    reds = _red_lines(report, items)
    requested = bool(report.get('comparison_requested'))
    if not reds and not report.get('source_changed') and not requested:
        return ''
    changes, names, unverified, calls = [], [], [], {}
    for item in items:
        if item.get('comparison'):
            continue
        if item.get('name') == '未覆盖' and not item.get('file'):
            unverified.extend((*_grey(str(reason)), False) for reason in item.get('reasons', ()))
            continue
        facts = _facts(item)
        subject = f'{facts["name"]}{facts["location"]}'
        if facts['count']:
            # Calls of one point in several contexts with the same change print once, with their count.
            key = subject, facts['overall'], facts['cause']
            if key in calls:
                calls[key][1] += 1
                continue
            counted = facts['summary'] if not facts['unknown'] else f'已比较 {facts["checked"]} 类（划分未完成），变 {facts["count"]} 类'
            calls[key] = [len(changes), 1]
            changes.append(f'变：{subject}{"" if subject.endswith("）") else " "}{counted}：{facts["overall"]}'
                           + (f'  {facts["cause"]}' if facts['cause'] else ''))
            names.append(facts['name'])
        elif item.get('lost'):
            # Set only for an anchored or ruled point: its loss is red, or listed under [unverified]
            # with its reason. A grey unanchored point has no `lost` and is listed below.
            continue
        elif facts['unknown'] or facts['status'] == 'grey':
            # A point whose own code changed is listed before the others. An observed point whose
            # comparison with the baseline did not finish says so; a point not observed gives its reason.
            prefix = '' if item.get('status') == 'grey' else '比较未完成：'
            unverified.extend((subject, prefix + reason, bool(item.get('cause'))) for reason in facts['reasons'] or ['原因没有记下'])
        elif requested:
            changes.append(f'比较：{subject}{"" if subject.endswith("）") else " "}{facts["summary"]}')
            names.append(facts['name'])
    for position, number in calls.values():
        if number > 1:
            changes[position] += f'（{number} 次调用相同）'
    for path in report.get('paths', ()):
        if path['before'] != path['after']:
            changes.append(f'变：路径 {path["test"]}：' + ' → '.join(path['before']) + ' 变成 ' + ' → '.join(path['after']))
            names.append('路径 ' + path['test'])
    changes = list(dict.fromkeys(changes))
    leads = [line for line in dict.fromkeys(_lead_line(lead) for lead in report.get('leads', ())) if line]
    unverified.extend((*_grey(str(reason)), False) for reason in report.get('unverified', ()))
    counted, causes = {}, {}
    for subject, reason, changed in sorted(unverified, key=lambda entry: not entry[2]):
        counted[(subject, reason)] = counted.get((subject, reason), 0) + 1
        cause = re.sub(r'^(比较未完成：)?[A-Za-z_][\w.]*: ', r'\1', reason)
        causes.setdefault(cause, set()).add(subject or reason)
    if not (reds or changes or leads or counted):
        return ''
    room = budget
    shown = _fit(changes, room - bool(leads) - bool(counted),
                 lambda rest: f'变：另 {rest} 项变化：' + '、'.join(dict.fromkeys(names[len(changes) - rest:])))
    room -= len(shown)
    shown_leads = _fit(leads, room - bool(counted), lambda rest: f'线索：另 {rest} 条：python -m flowguard check 列出全部线索')
    room -= len(shown_leads)
    lines = [_title(report), *reds, *shown, *shown_leads]
    if counted and room > 0:
        subjects = {subject or reason for subject, reason in counted}
        common = max(causes, key=lambda cause: (len(causes[cause]), -list(causes).index(cause)))
        lines.append(f'未验证 {len(subjects)} 项（不是通过）：最常见的原因是"{common}"'
                     + (f'（{len(causes[common])} 项）' if len(causes[common]) > 1 else ''))
        details = [f'未验证：{subject + "：" if subject else ""}{reason}' + (f'（{number} 次）' if number > 1 else '')
                   for (subject, reason), number in counted.items()]
        lines.extend(_fit(details, min(3, room - 1),
                          lambda rest: f'未验证：另 {rest} 项：python -m flowguard show 名字 看它的原因'))
    return '\n'.join(lines)


def _grey(text):
    """(subject, reason) of a grey line written as `NAME: reason` or `NAME：reason`."""
    for separator in ('：', ': '):
        head, found, rest = text.partition(separator)
        if found and head and len(head) <= 80 and '=' not in head and ' ' not in head.strip('[]:.'):
            return head, rest
    return '', text


def _title(report):
    baseline, kind = report.get('baseline'), report.get('baseline_kind', 'task')
    if not baseline:
        return 'FlowGuard（没有基准提交：不比较改前改后）'
    label = {'task': '相对任务开始', 'base': '相对 --flowguard-base', 'HEAD': '相对 HEAD'}.get(kind, '相对')
    return f'FlowGuard（{label} {baseline[:7]}）'


def _render(report, limit, *, quiet=False):
    budget = min(10, max(1, limit))
    items = report.get('items')
    items = [report] if items is None else items
    red = list(report.get('red', ()))
    red.extend(message for item in items if item is not report for message in item.get('red', ()))
    comparison = report.get('comparison', False)
    if comparison and report.get('status') == 'red' and not report.get('changes'):
        red += report.get('reasons', ())
    if not red and report.get('status') != 'red' and not any(item.get('status') == 'red' for item in items) and not report.get('comparison_requested') and (report.get('source_changed') is False
                    or report.get('snapshot', {}).get('kind') == 'no-source-change'):
        return ''
    lines = ['红：' + str(message) for message in red[:budget]]
    if len(red) > budget:
        lines[-1] = f'红：另 {len(red) - budget + 1} 处约束违反；完整结果保留在报告中'
    items = sorted(items, key=lambda item: item.get('status') != 'red')
    # Design order: red, changes, leads, then what stayed unverified.
    unverified = [item for item in items if item.get('status') != 'red' and _unknown(item)]
    def blocks(selected):
        for item in selected:
            if len(lines) >= budget:
                break
            lines.extend(_block(item, comparison=comparison or item.get('comparison', False),
                                same_name=report.get('same_name', False) or item.get('same_name', False))[:budget - len(lines)])
    blocks([item for item in items if not any(item is other for other in unverified)])
    for path in report.get('paths', ()):
        if len(lines) >= budget:
            break
        if path['before'] != path['after']:
            lines.append(f'路径 {path["test"]}：' + ' → '.join(path['before'])
                         + ' 变成 ' + ' → '.join(path['after']))
    leads = list(report.get('leads', ()))
    for lead in leads[:max(5, budget - len(lines))]:
        if len(lines) >= budget:
            break
        if isinstance(lead, dict):
            locations = lead.get('locations', ())
            if not locations:
                continue
            values = ','.join(dict.fromkeys(_shown(row['old']) for row in locations))
            lines.append(f'线索：旧值 {values} 还出现在 {lead["total"]} 个判断里：'
                         + '  '.join(f'{row["file"]}:{row["line"]}' + ('（大函数中）' if row.get('big') else '') for row in locations)
                         + ' → 需求变了就一起改；要锁定它们，在负责人上方写 # flowguard: owner 名，副本上方写 # flowguard: sensor 名')
        else:
            lines.append('线索：' + str(lead))
    blocks(unverified)
    if not lines and quiet:
        return ''
    if not lines:
        lines.append(f'共 {report.get("total", 0)} 类，变 {report.get("changed", 0)} 类'
                     if report.get('complete') else '未比较：没有可用的观察结果')
    # Red lines and leads carry full names, places and the next step to copy: never shortened.
    return '\n'.join(line if line.startswith(('红', '线索')) else _short(line) for line in lines)


def stale_copies(graph, changes):
    """Decision sites of the existing map that still spell an old value: the folded constant of a site,
    a member of a tuple or set it tests, or a member of the tuple or dict constant it reads; in JS/TS
    files the decision literals (comparisons, cases, returns, sets, unions). Field names are not required
    to share a word. A lead, never equality evidence."""
    import ast
    import json
    from decimal import Decimal, InvalidOperation
    sites = graph.con.execute('SELECT s.node,s.line,s.field,s.const,s.value,s.vkind,s.identity,s.file,n.line,n.end_line '
                              'FROM site s LEFT JOIN node n ON n.id = s.node ORDER BY s.file,s.line').fetchall()
    constants = {}
    for ident, sig in graph.con.execute("SELECT id, sig FROM node WHERE kind = 'const'"):
        try:
            constants[ident] = ast.literal_eval(sig)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            continue

    def equal(old, value):
        if type(old) is str or type(value) is str:
            return type(old) is type(value) and old == value
        if type(old) is bool or type(value) is bool or type(value) not in (int, float, Decimal):
            return False
        try:
            return Decimal(str(old)) == Decimal(str(value))
        except (InvalidOperation, ValueError):
            return False

    def members(value):
        if type(value) in (tuple, list, set, frozenset):
            return [item for part in value for item in members(part)]
        if type(value) is dict:
            return [item for part in value.values() for item in members(part)]
        return [value]

    def held(old, value, vkind, identity):
        if value:
            try:
                folded = json.loads(value)
            except ValueError:
                folded = value
            if any(equal(old, item) for item in members(folded)):
                return True
        base, bracket, key = (identity or '').partition('[')
        if base in constants:
            data = constants[base]
            if bracket:
                try:
                    index = ast.literal_eval(key.removesuffix(']'))
                    data = data[index]
                except (ValueError, SyntaxError, KeyError, IndexError, TypeError):
                    return False
            return any(equal(old, item) for item in members(data))
        return False

    from flowguard.structure.readers.registry import ECMA, language_for
    from .owners import named
    # JS/TS decisions are literal facts (comparisons, cases, returns, sets, unions), not folded sites.
    foreign = [row for row in [*graph.literals(), *graph.numbers()] if language_for(row['file']) in ECMA]
    found = {}
    for change in changes:
        old, own = change['before'], change.get('identity') or ''
        for target, line, field, literal, value, vkind, identity, file, start, end in sites:
            if target == change.get('target') or own and (identity or '').startswith(own):
                continue                    # the changed function and the readers of the changed constant
            if not held(old, value, vkind, identity):
                continue
            big = bool(start and end and end - start >= 20 and line - start >= 3)
            found[(file, line)] = dict(file=file, line=line, target=target, field=field, old=old,
                                      identity=identity, big=big, kind='lead')
        for row in foreign:
            if named(row['node']) == change.get('target') or (row['file'], row['line']) == (change['file'], change['line']) \
                    or not equal(old, row['value']):
                continue
            found[(row['file'], row['line'])] = dict(file=row['file'], line=row['line'], target=named(row['node']),
                                                    field=row['context'], old=old, identity='', big=False, kind='lead')
    rows = sorted(found.values(), key=lambda row: (row['file'], row['line']))
    return dict(total=len(rows), locations=rows, kind='lead')


def class_label(atoms, truth, kinds, witness):
    """Intersect readable comparison bounds; preserve relations between axes."""
    import ast
    from math import ceil, floor
    bounds, relations, other = defaultdict(list), defaultdict(set), []
    signs = {ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>=', ast.Eq: '=', ast.NotEq: '!='}
    opposite = {'<': '>=', '<=': '>', '>': '<=', '>=': '<', '=': '!=', '!=': '='}
    reverse = {'<': '>', '<=': '>=', '>': '<', '>=': '<=', '=': '=', '!=': '!='}
    for (text, _, env), yes in zip(atoms, truth):
        if yes is None:
            continue
        expression = ast.parse(text, mode='eval').body
        if isinstance(expression, ast.Name) and expression.id in kinds:
            if kinds[expression.id].name not in ('bool', 'enum', 'str'):
                bounds[(expression.id, kinds[expression.id].name == 'int')].append(('!=' if yes else '=', 0))
            continue
        if (isinstance(expression, ast.Compare) and len(expression.ops) == 1
                and isinstance(expression.ops[0], (ast.Is, ast.IsNot))
                and any(isinstance(node, ast.Constant) and node.value is None
                        for node in (expression.left, *expression.comparators))):
            continue  # Optional absence is already an explicit input class.
        if not isinstance(expression, ast.Compare) or len(expression.ops) != 1 or type(expression.ops[0]) not in signs:
            other.append(text if yes else f'not ({text})')
            continue
        left, right = expression.left, expression.comparators[0]
        operator = signs[type(expression.ops[0])]
        operator = operator if yes else opposite[operator]
        if isinstance(left, ast.Name) and isinstance(right, ast.Name) and left.id in kinds and right.id in kinds:
            pair = tuple(sorted((left.id, right.id)))
            relations[pair].add(operator if pair[0] == left.id else reverse[operator])
            continue
        value = C.const_value(right, dict(env), set(kinds))
        if value is None:
            value = C.const_value(left, dict(env), set(kinds))
            left, operator = right, reverse[operator]
        names = {node.id for node in ast.walk(left) if isinstance(node, ast.Name)}
        if value is not None and type(value[1]) in (int, float, Decimal) and names and names <= kinds.keys():
            integer = all(kinds[name].name == 'int' for name in names) and not any(isinstance(node, ast.Div) or isinstance(node, ast.Constant) and type(node.value) is not int for node in ast.walk(left))
            bounds[(ast.unparse(left), integer)].append((operator, value[1]))
        elif not names <= {name for name, kind in kinds.items() if kind.name in ('bool', 'enum', 'str')}:
            other.append(text if yes else f'not ({text})')
    parts = []
    for (expression, integer), conditions in bounds.items():
        lower = [(floor(value) + 1 if integer and op == '>' else ceil(value) if integer else value, integer or op == '>=') for op, value in conditions if op in ('>', '>=')]
        upper = [(ceil(value) - 1 if integer and op == '<' else floor(value) if integer else value, integer or op == '<=') for op, value in conditions if op in ('<', '<=')]
        equal = [value for op, value in conditions if op == '=']
        low = max(lower, key=lambda pair: (pair[0], not pair[1])) if lower else None
        high = min(upper, key=lambda pair: (pair[0], pair[1])) if upper else None
        if equal or low and high and low[0] == high[0] and low[1] and high[1]:
            parts.append(f'{expression}={_shown(equal[0] if equal else low[0])}')
        elif low and high:
            parts.append(f'{expression}={_shown(low[0])}–{_shown(high[0])}' if integer else
                         f'{_shown(low[0])} {"≤" if low[1] else "<"} {expression} {"≤" if high[1] else "<"} {_shown(high[0])}')
        elif low:
            parts.append(f'{expression}{"≥" if low[1] else ">"}{_shown(low[0])}')
        elif high:
            parts.append(f'{expression}{"≤" if high[1] else "<"}{_shown(high[0])}')
        for op, value in conditions:
            if op == '!=' and not (low and value < low[0] or high and value > high[0]):
                parts.append(f'{expression}≠{_shown(value)}')
    for (left, right), operators in relations.items():
        if '=' in operators or {'<=', '>='} <= operators:
            parts.append(f'{left}={right}')
        else:
            parts.extend(f'{left}{op.replace("<=", "≤").replace(">=", "≥").replace("!=", "≠")}{right}' for op in sorted(operators))
    parts.extend(f'{name}={_shown(witness[name])}' for name, kind in kinds.items()
                 if kind.name in ('bool', 'enum', 'str') or witness[name] is None)
    return '，'.join(dict.fromkeys(parts + other)) or C.show_cell(witness)
