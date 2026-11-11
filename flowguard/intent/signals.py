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
    return ', '.join(f'{name}={_shown(value)}' for name, value in row.get('inputs', {}).items()) or 'no record'


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
        return labels[0] + (f' and {len(labels)} classes' if len(labels) > 1 else '')
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
        return 'cause: ' + cause
    return (f'cause: {cause.get("name", "code")} {_shown(cause.get("before"))} → {_shown(cause.get("after"))}'
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
        name += '(unanchored, automatic)'
    location = f'（{item["file"]}:{item["line"]}）' if item.get('file') and item.get('line') else ''
    if comparison:
        first = changes[0] if changes else item
        left, right = first.get('before_target'), first.get('after_target')
        location = f'（{left} ↔ {right}）' if left and right else location
    status = item.get('comparison_status', item.get('status'))
    reasons = list(dict.fromkeys([*item.get('comparison_reasons', ()), *item.get('reasons', ())]))
    unknown = not item.get('complete', False) or status not in (None, 'ok', 'red') or bool(reasons)
    checked = item.get('checked', len(item.get('rows', ())) if status == 'ok' else len(changes))
    summary = (f'candidate classes: {total}; compared: {checked}; comparison incomplete; proven changed classes: {count}' if unknown
               else f'total {total} classes，changed {count} classes')
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
        change = (f'{_region(members)}; function result {row["before"]} → {row["after"]}(example: {_example(row)}）'
                  + (f'; plus {len(groups) - 1} outcome-change groups' if len(groups) > 1 else ''))
        overall = change
        if len(groups) > 1:
            row = smallest(changes)
            overall = (f'{_region(changes)}; function result has {len(groups)} kinds of change (example: {_example(row)}: '
                       f'{row["before"]} → {row["after"]}）')
    return dict(name=name, location=location, count=count, total=total, checked=checked, unknown=unknown,
                summary=summary, change=change, overall=overall, cause=_cause(item.get('cause')), reasons=reasons, status=status)


def _block(item, *, comparison=False, same_name=False):
    facts = _facts(item, comparison=comparison)
    title = f'{facts["name"]}{facts["location"]}：' if facts['name'] or facts['location'] else ''
    if comparison and facts['count']:
        title = ('red same-name anchor ' if same_name else 'red comparison ') + title
    lines = [title + facts['summary']]
    if facts['change']:
        lines.append(facts['change'])
    if facts['cause']:
        lines.append(facts['cause'])
    if facts['reasons'] and len(lines) < 3:
        lines.append('uncovered: ' + '; '.join(facts['reasons']))
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
# Four kinds, in this order: red (every red, the places of one rule or owner on one line, each followed
# by the next step to copy), changed (changed outcomes and paths), lead (leads) and unverified (grey, merged
# and counted). The last three share ten lines; names and places are never shortened.

def red(subject, *texts, next=()):
    """One red finding as report text (`SUBJECT：text`) and its next steps keyed by the subject.

    Reports keep red findings as text; `steps` carries the lines to copy under the merged red line."""
    return (subject + '：' if subject else '') + '；'.join(texts), {subject: list(next)} if subject and next else {}


def copy_answers(answers, same, show, owner=None, total=None, apart=()):
    """What same-name copies answered one input, and the next step, without choosing which copy is right.

    `answers` is [(place, value)] in plan order; equal values (`same`) form one group, listed by its size
    (the reference group first when `owner`, the reference location, is one of them): `3 copies: 2 return 52 (a, b), 1 returns 1 (c)`.
    `total` counts the copies, also those without an answer on this input. `apart` [(place, input)] are copies
    that answer this input as the owner does but differ from it on another input, named on that input's line:
    they are listed after the groups, never counted with the owner. Without an owner the step leaves the
    choice to the reader, also for one answer each; with one, the owner is the reference its copies follow."""
    aside = dict(apart)
    groups = []
    for place, value in answers:
        if place in aside:
            continue
        group = next((group for group in groups if same(group[0], value)), None)
        if group is None:
            groups.append((value, [place]))
        else:
            group[1].append(place)
    groups.sort(key=lambda group: (owner not in group[1], -len(group[1])))
    shown = lambda place: ('reference ' if place == owner else '') + place
    missing = (total or len(answers)) - len(answers)
    text = (f'{len(answers)} copies' + (f' (plus {missing} copies without a result for this input)' if missing else '') + ': '
            + ', '.join(f'{len(places)} copies return {show(value)} ({", ".join(map(shown, places))})' for value, places in groups)
            + (f', plus {len(aside)} copies differ from the reference on other inputs: ' + ', '.join(f'{place} ({where})' for place, where in aside.items())
               if aside else ''))
    if owner is not None:
        others = [place for value, places in groups if owner not in places for place in places]
        return text, f'make {"、".join(others)} agree with the reference'
    return text, 'first decide which copy is correct, then make ' + ('the other copy' if len(answers) == 2 else 'the remaining copies') + ' agree with it'


def copy_lines(inputs, same, show, owner=None, total=None, *, only=None):
    """The lines of one same-name red, in the same words in pytest and `check`: [(input, text, step, pairs)].

    `inputs` [(input, [(place, value)])] is what the copies answered each input, in the order to report. A line
    is kept on an input where it first shows a copy that differs from the owner (`owner`, its place), so each
    such copy is named, with its step, on its own first input that differs; without an owner that answers, where
    it first shows two copies that differ. `pairs` holds the pairs of places the line shows to differ. On another
    line a copy that answers as the owner but differs from it elsewhere is set apart (`copy_answers`)."""
    owned = owner is not None and any(place == owner for _, answers in inputs for place, _ in answers)
    kept, seen = [], set()
    for where, answers in inputs:
        values = dict(answers)
        if owned:
            if owner not in values:
                continue
            pairs = {frozenset((owner, place)) for place, value in answers if not same(values[owner], value)}
        else:
            pairs = {frozenset((place, other)) for number, (place, value) in enumerate(answers)
                     for other, theirs in answers[number + 1:] if not same(value, theirs)}
        if only is not None:
            pairs &= only
        if pairs - seen:
            kept.append((where, answers, pairs))
        seen |= pairs
    lines = []
    for where, answers, pairs in kept:
        values = dict(answers)
        apart = [(place, next(other for other, _, theirs in kept if frozenset((owner, place)) in theirs))
                 for place, value in answers
                 if owned and place != owner and same(values[owner], value)
                 and any(frozenset((owner, place)) in theirs for _, _, theirs in kept)]
        text, step = copy_answers(answers, same, show, owner=owner if owned else None, total=total, apart=apart)
        lines.append((where, text, step, pairs))
    return lines


def copy_partition(inputs, previous, same, show, owner=None, total=None):
    """An existing disagreement cannot hide a newly broken pair of functions."""
    past = {pair for line in copy_lines(previous, same, show, owner, total) for pair in line[3]}
    current = {pair for line in copy_lines(inputs, same, show, owner, total) for pair in line[3]}
    return (copy_lines(inputs, same, show, owner, total, only=current - past),
            copy_lines(inputs, same, show, owner, total, only=current & past))


def copy_red(name, lines):
    """The one red of same-name copies `name` from its `copy_lines`: each input with its step, then the way out."""
    return (f'same-name anchor {name}：' + '；'.join(f'{where}，{text} -> {step}' for where, text, step, _ in lines)
            + '; if intentionally different, use different anchor names and declare distinct')


def rule_steps(rule_id, homes, where, messages=()):
    """The next step of a violated rule by what its red `messages` say, in the same words in pytest, `check` and
    the vitest report (no messages: the code disagrees). The code disagrees with the rule (`-> rule X, code Y`):
    correct the code at `homes`. The rule disagrees with its own regression rows (`self:`, `row`): correct the rows
    or the rule at `where`; it leaves cells undecided (`gap in`): add the rule or rows. Two rules decide a cell
    differently (`conflict A vs B`): one of them stays, which the owner decides. Any other red without a step of
    its own: correct the rule's source, binding or rows. When the need changed, the owner's new words are stored
    first, then the rule changes."""
    kinds, conflicts = set(), []
    # A row the rule itself contradicts (`self:`), or the rule that decides over it (`row X L6 ... the decision of`),
    # also fails against the code that agrees with what decides (`(row L6)`): that is the row's red, not the code's.
    said = '\n'.join(map(str, messages))
    wrong_rows = set(re.findall(r'^self: .*? on its own row (L\d+) ', said, re.M)) | set(re.findall(r'^row \S+ (L\d+) ', said, re.M))
    for message in messages or ('-> rule',):
        text = str(message)
        pair = re.match(r'conflict (\S+) vs (\S+) at ', text)
        row = re.search(r'\(row (L\d+)\)', text)
        if '-> rule ' in text and row and row[1] in wrong_rows:
            continue
        if pair:
            conflicts.append(f'rules {pair[1]} and {pair[2]} conflict; choose one by asking the owner; ')
        elif text.startswith(('self: ', 'row ')):
            kinds.add('rows')
        elif text.startswith('gap in '):
            kinds.add('gap')
        elif '-> rule ' in text:
            kinds.add('code')
        elif ' -> ' not in text:
            kinds.add('other')
    steps = list(dict.fromkeys(conflicts))
    steps += [step for kind, step in (
        ('code', f'change the code so {homes} follows rule {rule_id}; '),
        ('rows', f'correct regression rows or rule {where} so the rule and its regression rows agree; '),
        ('gap', f'add rules or regression rows at {where} so undecided cells have a rule result; '),
        ('other', f'inspect rule {where} and correct its source, binding or regression rows; ')) if kind in kinds]
    if conflicts:
        steps.append(f'when the owner decides, first store the exact owner words with python -m flowguard req add, then update rule {where}')
    elif steps:
        steps.append(f'if requirements changed, first store the new owner words with python -m flowguard req add, then update rule {where}')
    return steps


def _red_entry(message):
    text = str(message)
    for source_marker in (' source: ', ' 出处：'):
        subject, marker, quote = text.partition(source_marker)
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
            # A source comparison keeps its block title: `red same-name anchor NAME（left ↔ right）：counts：first change`.
            facts = _facts(item, comparison=True)
            same = item.get('same_name') or report.get('same_name')
            compared.append(('red same-name anchor ' if same else 'red comparison ') + f'{facts["name"]}{facts["location"]}：{facts["summary"]}：{facts["overall"]}')
            if same:
                compared.append('    make these locations agree; if behavior should differ, use different anchor names and declare distinct')
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
        line = 'red: ' + (entry['subject'] + (entry['separator'] + body if body else '') if entry['subject'] else body)
        if entry['quote']:
            line += f'  {entry["subject"]} source: {entry["quote"]}'
        lines.append(line)
        lines.extend('    ' + step for step in steps.get(entry['subject'], ()) if entry['subject'])
    for finding in report.get('ledger_red', ()):
        lines.append('red: ' + finding['text'])
        lines.extend('    ' + step for step in finding['fix'])
    return lines + compared


def _lead_line(lead):
    if not isinstance(lead, dict):
        return 'lead: ' + str(lead)
    locations = lead.get('locations', ())
    if not locations:
        return ''
    values = ','.join(dict.fromkeys(_shown(row['old']) for row in locations))
    return (f'lead: old values {values} remain in {lead["total"]} decisions: '
            + '  '.join(f'{row["file"]}:{row["line"]}' + ('(in a large function)' if row.get('big') else '') for row in locations)
            + ' -> if requirements changed, update together; to lock them, write # flowguard: same NAME ref above the reference and # flowguard: same NAME above the copies')


def _fit(lines, room, overflow):
    if room <= 0:
        return []
    if len(lines) <= room:
        return lines
    return lines[:room - 1] + [overflow(len(lines) - room + 1)]


def _session(report, limit):
    budget = min(10, max(1, limit))
    title = _title(report)
    if 'seconds' in report:
        title += f'; {report["seconds"]:.3f} s'
    items = list(report.get('items', ()))
    reds = _red_lines(report, items)
    requested = bool(report.get('comparison_requested'))
    # A missing task start compares nothing, and the title alone says so with the next step.
    alone = title if report.get('baseline_kind') == 'missing' or 'seconds' in report else ''
    before = ['before: ' + str(message) for message in report.get('before', ())]
    if not reds and not before and not report.get('source_changed') and not requested:
        return alone
    changes, names, unverified, calls = [], [], [], {}
    compared, compared_names = [], []      # an explicit comparison's unchanged points, after every change
    for item in items:
        if item.get('comparison'):
            continue
        if item.get('name') in ('uncovered', '未覆盖') and not item.get('file'):
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
            counted = facts['summary'] if not facts['unknown'] else f'compared {facts["checked"]} classes (partition incomplete); changed {facts["count"]} classes'
            calls[key] = [len(changes), 1]
            changes.append(f'changed: {subject}{"" if subject.endswith("）") else " "}{counted}：{facts["overall"]}'
                           + (f'  {facts["cause"]}' if facts['cause'] else ''))
            names.append(facts['name'])
        elif item.get('lost'):
            # Set only for an anchored or ruled point: its loss is red, or listed under [unverified]
            # with its reason. A grey unanchored point has no `lost` and is listed below.
            continue
        elif facts['unknown'] or facts['status'] == 'grey':
            # A point whose own code changed is listed before the others. An observed point whose
            # comparison with the baseline did not finish says so; a point not observed gives its reason.
            prefix = '' if item.get('status') == 'grey' else 'comparison incomplete: '
            unverified.extend((subject, prefix + reason, bool(item.get('cause'))) for reason in facts['reasons'] or ['reason not recorded'])
        elif requested:
            compared.append(f'compared: {subject}{"" if subject.endswith("）") else " "}{facts["summary"]}')
            compared_names.append(facts['name'])
    for position, number in calls.values():
        if number > 1:
            changes[position] += f'（{number} identical calls)'
    for path in report.get('paths', ()):
        if path['before'] != path['after']:
            changes.append(f'changed: path {path["test"]}：' + ' → '.join(path['before']) + ' became ' + ' → '.join(path['after']))
            names.append('path ' + path['test'])
    changes, names = _unique(changes, names)
    compared, compared_names = _unique(compared, compared_names)
    leads = [line for line in dict.fromkeys(_lead_line(lead) for lead in report.get('leads', ())) if line]
    # What this change adds comes before the old ledger (`--all`): the budget never hides a new lead behind old ones.
    leads.sort(key=lambda line: line.startswith(('lead: before', '线索：旧账')))
    unverified.extend((*_grey(str(reason)), False) for reason in report.get('unverified', ()))
    counted, causes = {}, {}
    for subject, reason, changed in sorted(unverified, key=lambda entry: not entry[2]):
        counted[(subject, reason)] = counted.get((subject, reason), 0) + 1
        cause = re.sub(r'^(comparison incomplete: )?[A-Za-z_][\w.]*: ', r'\1', reason)
        causes.setdefault(cause, set()).add(subject or reason)
    if not (reds or before or changes or compared or leads or counted):
        return alone
    room = budget
    # Changes come first and keep their room; an unchanged comparison never pushes a change into the overflow.
    shown = _fit(changes, room - bool(leads) - bool(counted),
                 lambda rest: f'changed: plus {rest} changes: ' + '、'.join(dict.fromkeys(names[len(changes) - rest:])))
    shown += _fit(compared, room - len(shown) - bool(leads) - bool(counted),
                  lambda rest: f'compared: plus {rest} unchanged items: ' + '、'.join(dict.fromkeys(compared_names[len(compared) - rest:])))
    room -= len(shown)
    # `all_leads` (check --leads) prints every lead outside the budget; otherwise the overflow names that command.
    more = report['more_leads'] if 'more_leads' in report else more_leads('check --static')
    if report.get('all_leads'):
        shown_leads = leads
    else:
        shown_leads = _fit(leads, room - bool(counted), lambda rest: f'lead: plus {rest} entries: {more} lists all leads')
        room -= len(shown_leads)
    lines = [title, *reds, *before[:2], *shown, *shown_leads]
    if counted and room > 0:
        subjects = {subject or reason for subject, reason in counted}
        common = max(causes, key=lambda cause: (len(causes[cause]), -list(causes).index(cause)))
        # One point, its line right below: the count says no reason, which that line gives.
        lines.append(f'unverified {len(subjects)} items (not passed)' + ('' if len(counted) == 1 and room > 1 else
                     f': most common reason is "{common}"' + (f'（{len(causes[common])} items)' if len(causes[common]) > 1 else '')))
        details = [f'unverified: {subject + "：" if subject else ""}{reason}' + (f'（{number} times)' if number > 1 else '')
                   for (subject, reason), number in counted.items()]
        keys = list(counted)

        def hidden(rest):
            # The detail lines left out are counted as lines, and the names they cover are listed in full.
            names = '、'.join(dict.fromkeys(subject for subject, _ in keys[len(keys) - rest:] if subject))
            return f'unverified: plus {rest} entries' + (f'（{names}）' if names else '') + ': python -m flowguard show NAME explains why'
        lines.extend(_fit(details, min(3, room - 1), hidden))
    return '\n'.join(lines)


def _unique(lines, names):
    """Each line once, with the name it was written for."""
    kept = dict(zip(reversed(lines), reversed(names)))
    ordered = list(dict.fromkeys(lines))
    return ordered, [kept[line] for line in ordered]


def _grey(text):
    """(subject, reason) of a grey line written as `NAME: reason` or `NAME：reason`."""
    for separator in ('：', ': '):
        head, found, rest = text.partition(separator)
        if found and head and len(head) <= 80 and '=' not in head and ' ' not in head.strip('[]:.'):
            return head, rest
    return '', text


def more_leads(command, everything=False, base=None):
    """The command that prints every lead of a run: the same options, `--leads` added (an explicit baseline as
    `--base`, also pytest's `--flowguard-base`, or it would list the leads against the task baseline instead)."""
    return f'python -m flowguard {command}' + ' --all' * everything + (f' --base {base}' if base else '') + ' --leads'


def missing_start(commit):
    """The one line of a run whose recorded task start this repository lacks (a shallow clone, collected history,
    another clone's cache): it compares nothing, and new-task records HEAD."""
    return f'FlowGuard(recorded task baseline {commit[:7]} is not in this repository: old/new comparison is off; first run python -m flowguard new-task)'


def _title(report):
    baseline, kind = report.get('baseline'), report.get('baseline_kind', 'task')
    if not baseline:
        return 'FlowGuard(no baseline commit: old/new comparison is off)'
    if kind == 'missing':
        return missing_start(baseline)
    # An explicit baseline is named by the option that gave it: pytest's --flowguard-base, or `--base` of the
    # CLI check (`baseline_option`).
    option = report['baseline_option'] if 'baseline_option' in report else '--flowguard-base'
    label = {'task': 'since task start', 'base': 'since ' + option, 'HEAD': 'since HEAD'}.get(kind, 'since')
    ahead = report.get('baseline_ahead')
    if kind == 'task' and ahead:
        # A task start HEAD has moved past: the commits since are this task's, or an earlier task's without new-task.
        return f'FlowGuard（{label} {baseline[:7]}, commits before HEAD: {ahead}; first run python -m flowguard new-task for a new task)'
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
    lines = ['red: ' + str(message) for message in red[:budget]]
    if len(red) > budget:
        lines[-1] = f'red: plus {len(red) - budget + 1} constraint violations; complete results retained in the report'
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
            lines.append(f'path {path["test"]}：' + ' → '.join(path['before'])
                         + ' became ' + ' → '.join(path['after']))
    leads = list(report.get('leads', ()))
    for lead in leads[:max(5, budget - len(lines))]:
        if len(lines) >= budget:
            break
        if isinstance(lead, dict):
            locations = lead.get('locations', ())
            if not locations:
                continue
            values = ','.join(dict.fromkeys(_shown(row['old']) for row in locations))
            lines.append(f'lead: old values {values} remain in {lead["total"]} decisions: '
                         + '  '.join(f'{row["file"]}:{row["line"]}' + ('(in a large function)' if row.get('big') else '') for row in locations)
                         + ' -> if requirements changed, update together; to lock them, write # flowguard: same NAME ref above the reference and # flowguard: same NAME above the copies')
        else:
            lines.append('lead: ' + str(lead))
    blocks(unverified)
    if not lines and quiet:
        return ''
    if not lines:
        lines.append(f'total {report.get("total", 0)} classes，changed {report.get("changed", 0)} classes'
                     if report.get('complete') else 'not compared: no observations available')
    # Red lines and leads carry full names, places and the next step to copy: never shortened.
    return '\n'.join(line if line.startswith(('red', 'lead')) else _short(line) for line in lines)


def stale_copies(graph, changes):
    """Decision sites of the existing map that still spell an old value: the folded constant of a site,
    a member of a tuple or set it tests, or a member of the tuple or dict constant it reads; in JS/TS
    files the decision literals (comparisons, cases, returns, sets, unions). Field names are not required
    to share a word. A lead, never equality evidence."""
    import ast
    import json
    from decimal import Decimal, InvalidOperation
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
            if value not in direct_members:
                try:
                    folded = json.loads(value)
                except ValueError:
                    folded = value
                direct_members[value] = tuple(members(folded))
            if any(equal(old, item) for item in direct_members[value]):
                return True
        if identity not in constant_members:
            base, bracket, key = (identity or '').partition('[')
            if base in constants:
                data = constants[base]
                if bracket:
                    try:
                        index = ast.literal_eval(key.removesuffix(']'))
                        data = data[index]
                    except (ValueError, SyntaxError, KeyError, IndexError, TypeError):
                        constant_members[identity] = ()
                        return False
                constant_members[identity] = tuple(members(data))
            else:
                constant_members[identity] = ()
        return any(equal(old, item) for item in constant_members[identity])

    def key(value, *, old=False):
        """What equal() compares a value by, to narrow the scan: its text for a str, its decimal number for an
        int, float or Decimal; None for a value equal() matches with nothing. `ANY` for an old value of another
        type: every site is read for it. An int member keys by its exact number even where equal() cannot
        read it, which only adds a candidate that held() then refuses."""
        kind = type(value)
        if kind is str:
            return value
        if kind is bool or kind not in (int, float, Decimal):
            return ANY if old and kind is not bool else None
        number = Decimal(value) if kind is int else Decimal(str(value))
        return None if number.is_nan() else number

    from flowguard.structure.readers.registry import ECMA, language_for
    from .owners import named
    ANY = object()
    if 'stale_copy_facts' not in graph._derived:
        sites = graph.con.execute('SELECT s.node,s.line,s.field,s.const,s.value,s.vkind,s.identity,s.file,n.line,n.end_line '
                                  'FROM site s LEFT JOIN node n ON n.id = s.node ORDER BY s.file,s.line').fetchall()
        constants = {}
        for ident, sig in graph.con.execute("SELECT id, sig FROM node WHERE kind = 'const'"):
            try:
                constants[ident] = ast.literal_eval(sig)
            except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                continue
        # Without a direct value or a known constant, held() is false for every old value.
        sites = [row for row in sites if row[4] or (row[6] or '').partition('[')[0] in constants]
        # Facts and symbol associations only: old-value matching remains below, per change.
        foreign = [(row, named(row['node'])) for row in [*graph.literals(), *graph.numbers()]
                   if language_for(row['file']) in ECMA]
        graph._derived['stale_copy_facts'] = sites, constants, foreign
    else:
        graph._mark_query('literals')  # cached facts still count in this predicate's query coverage
    sites, constants, foreign = graph._derived['stale_copy_facts']
    direct_members, constant_members = graph._derived.setdefault('stale_copy_members', ({}, {}))
    if 'stale_copy_index' not in graph._derived:
        # Which sites an old value can match: a site's direct members join by_key once held() has read them
        # (until then the site is pending and read for every old value); a site with a known constant is read
        # for every old value, so its constant is still read only when an old value first needs it.
        foreign_by_key = {}
        for position, (row, _) in enumerate(foreign):
            if (found_key := key(row['value'])) is not None:
                foreign_by_key.setdefault(found_key, []).append(position)
        graph._derived['stale_copy_index'] = (
            {}, [position for position, row in enumerate(sites) if (row[6] or '').partition('[')[0] in constants],
            {position for position, row in enumerate(sites) if row[4]}, foreign_by_key, {}, {})
    by_key, by_constant, pending, foreign_by_key, direct_keys, constant_keys = graph._derived['stale_copy_index']
    found = {}
    for change in changes:
        old, own = change['before'], change.get('identity') or ''
        wanted = key(old, old=True)
        positions = range(len(sites)) if wanted is ANY else \
            sorted(by_key.get(wanted, set()).union(by_constant, pending))
        for position in positions:
            target, line, field, literal, value, vkind, identity, file, start, end = sites[position]
            if target == change.get('target') or own and (identity or '').startswith(own):
                continue                    # the changed function and the readers of the changed constant
            if wanted is not ANY and identity in constant_keys and position not in pending \
                    and wanted not in direct_keys.get(position, ()) and wanted not in constant_keys[identity]:
                continue                    # neither its value nor its constant has a member equal() can match
            matched = held(old, value, vkind, identity)
            if position in pending:
                pending.discard(position)
                keys = {found_key for item in direct_members[value] if (found_key := key(item)) is not None}
                direct_keys[position] = keys
                for found_key in keys:
                    by_key.setdefault(found_key, set()).add(position)
            if identity in constant_members and identity not in constant_keys:
                constant_keys[identity] = {found_key for item in constant_members[identity] if (found_key := key(item)) is not None}
            if not matched:
                continue
            big = bool(start and end and end - start >= 20 and line - start >= 3)
            found[(file, line)] = dict(file=file, line=line, target=target, field=field, old=old,
                                      identity=identity, big=big, kind='lead')
        for position in range(len(foreign)) if wanted is ANY else foreign_by_key.get(wanted, ()):
            row, target = foreign[position]
            if target == change.get('target') or (row['file'], row['line']) == (change['file'], change['line']) \
                    or not equal(old, row['value']):
                continue
            found[(row['file'], row['line'])] = dict(file=row['file'], line=row['line'], target=target,
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
