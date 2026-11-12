"""Small, bounded views over comparison facts; never runs application code."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from decimal import Decimal, InvalidOperation

from . import cells as C
from .sources import ACTS, SHA


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


def _distinct(values):
    """Each recorded value once, in the order first seen: values with equal JSON are one value (a list or a dict too,
    which cannot be hashed; an int and a float stay apart)."""
    import json
    kept = {}
    for value in values:
        kept.setdefault(json.dumps(value, sort_keys=True), value)
    return list(kept.values())


def _ordered(values):
    """`_distinct` values in the order `cells.smallest` reads a field's points: by type, then value; a list or a dict
    by its JSON."""
    import json
    return sorted(_distinct(values), key=lambda value: (type(value).__name__, json.dumps(value, sort_keys=True))
                  if type(value) in (dict, list) else C._k(value))


def _region(rows):
    if rows[0].get('region'):
        labels = list(dict.fromkeys(row.get('region', '') for row in rows))
        return labels[0] + (f' and {len(labels)} classes' if len(labels) > 1 else '')
    names = tuple(rows[0].get('inputs', {}))
    values = {name: _distinct(row['inputs'][name] for row in rows) for name in names}
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
                points = {key: _ordered(entry['inputs'][key] for entry in members) for key in row['inputs']}
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


# ---- the nine kinds of line (4.3) ------------------------------------------------------------------
# Every finding reaches the agent as `Line`s of these kinds, in this order. `deliver` gives each member of a
# finding its kind from the finding's family, whether this change added it (`Issue.fresh`), what this change
# touches and the entries of `.flowguard/known.toml`; it reads no map, no Git and no file.

KINDS = ('red', 'before', 'known', 'known fixed?', 'changed', 'impact', 'loosened', 'not compared', 'deprecated')


@dataclass(frozen=True)
class Line:
    """One line of the end-of-run block, `{kind}: {text} -> {step}`; (kind, name, function) is its identity."""
    kind: str                   # one of KINDS
    name: str                   # the finding's name (Issue.name), 'known.<id>', 'changed:<function>', ...
    function: str = ''          # the finding's member; '' for a file-level one
    text: str = ''              # between '{kind}: ' and ' -> ', paths relative to the repository
    step: str = ''              # after ' -> '
    places: tuple = ()          # the repository-relative places `text` names
    detail: tuple = ()          # further lines only `show --last` prints


# family: (can it be red, the kind of a member this change added when it cannot, may known.toml ignore it)
FAMILIES = {
    'pair': (True, None, False), 'writer': (True, None, False), 'values': (True, None, False),
    'same': (True, None, False), 'changed-alone': (True, None, False), 'source': (True, None, False),
    'rule': (True, None, False), 'flow': (True, None, False), 'test': (True, None, False),
    'ledger': (True, None, False), 'input': (True, None, False),
    'delete': (False, 'impact', True), 'columns': (False, 'impact', True), 'ondelete': (False, 'impact', True),
    'labels': (False, 'impact', True), 'uncreated': (False, 'impact', True), 'copies': (False, 'impact', True),
    'declarations': (False, 'impact', True),
    'writers': (False, None, True),     # fields several files write without an agreement: shown in impact lines
}
BEFORE_STEP = 'leave it unless your task is about it'
BROKEN = {'same': 'disagreed at task start'}        # what a before line says of an old member; else 'was broken ...'
IMPACT_STEP = 'fix it, or say why in your report'
KNOWN_STEPS = {'leave': 'leave it (the owner deferred it)', 'fix': 'fix it in this change and say so in your report'}
FIXED_STEPS = {'leave': 'the owner deferred it: revert, or say why in your report',
               'ask': 'the owner has not decided: revert, or say why in your report',
               'fix': 'say so in your report; remove known.{id} once the owner agrees',
               'ignore': 'say so in your report; remove known.{id} once the owner agrees'}


def family_of(name):
    """The family of a finding name by its prefix ('pair:A>B' -> 'pair'); '' when the prefix is none."""
    head = name.partition(':')[0]
    return head if head in FAMILIES else ''


def _known_step(entry):
    if entry.act == 'ask':
        return f'asked on {entry.asked}; leave it until the owner answers' if entry.asked else 'ask owner (not asked yet)'
    return KNOWN_STEPS[entry.act]


def _known_detail(entry):
    return tuple(f'{key}: {getattr(entry, key)}' for key in ('why', 'ask', 'fix', 'source') if getattr(entry, key))


def deliver(issues, *, touched_functions, touched_files, known=(), ran=frozenset(), everything=False, extra=()):
    """(lines, ignored): the findings as `Line`s in KINDS order, and the number of members an `act = "ignore"`
    entry of known.toml covers (counted, never a line).

    A member this change added (in `Issue.fresh`) is red when its family can be red, also when a known entry
    names its finding (the entry goes into the line's detail: an entry never silences a new finding); otherwise
    it gets its family's new kind (impact), unless an ignore entry covers it. Every other member counts when this
    change touches it (its function; for a file-level member, one of the finding's files), and with `everything`
    always: a known entry naming its finding gives a `known` line when the change also touches the entry's sites
    (else nothing: `known` needs the entry's sites touched, `before` no entry), an ignore entry alone counts it,
    and without an entry it is `before`. An ignore entry covers only a family that may be ignored, and an entry
    of another act beside it keeps the member shown. Fields several files write without an agreement (family 'writers')
    have no line of their own except with `everything`. A known entry whose finding belongs to a family that ran
    (`ran`: a family whose checks judged the whole project, or a finding name whose own check ran, as a pytest
    session's sealed comparison of the copies of one same name) and is not among the findings is `known fixed?`
    (`copies of NAME now agree` for same-name copies); any other entry, except an ignore entry, whose
    sites this change touches (`Known.nodes` in `touched_functions` or `Known.files` in `touched_files`, every
    entry with `everything`) and that has no line yet is `known`. `extra` are lines already of their kind
    (changed, impact, loosened, not compared). Lines are unique by (kind, name, function), the first one kept.
    A part's place is one 'path:symbol' (the line reads `{subject}: {place} {what}`, before `{subject} at {place} was
    broken at task start`) or a tuple of them that `what` names itself (`{subject}: {what}`; before: `{subject}
    disagreed at task start {what}` for same-name copies, `was broken at task start` otherwise).
    Pure: no map, no Git, no file."""
    touched_functions, touched_files = frozenset(touched_functions), frozenset(touched_files)
    entries = list(known)
    for entry in entries:
        if entry.act not in ACTS:
            raise ValueError(f'known.{entry.id}: act is one of {", ".join(ACTS)}, not {entry.act!r}')
    lines, ignored, said, names = [], set(), set(), set()      # said: entries that already have a line
    for issue in issues:
        if issue.family not in FAMILIES:
            raise ValueError(f'{issue.name}: family {issue.family!r} is not a key of signals.FAMILIES')
        if not issue.subject or not issue.parts:
            raise ValueError(f'{issue.name}: a finding needs its subject and one part per member')
        if not issue.fresh <= {part[0] for part in issue.parts}:
            raise ValueError(f'{issue.name}: fresh names a function that is no part: {sorted(issue.fresh)}')
        red, new, ignorable = FAMILIES[issue.family]
        shown = issue.family != 'writers' or everything
        naming = [entry for entry in entries if entry.finding == issue.name]
        speaking = [entry for entry in naming if entry.act != 'ignore']
        ignoring = ignorable and len(speaking) < len(naming)
        names.add(issue.name)
        verb = BROKEN.get(issue.family, 'was broken at task start')
        for function, place, what, step in issue.parts:
            # A tuple of places is named by `what` itself, which reads on after the subject (and after the verb of a
            # before line: `same N disagreed at task start on year=2025: ...`).
            many = isinstance(place, tuple)
            places = tuple(place) if many else (place,) if place else ()
            text = f'{issue.subject}: {place} {what}' if place and not many else f'{issue.subject}: {what}'
            where = ', '.join(places)
            if function in issue.fresh and red:
                lines.append(Line('red', issue.name, function, text, step, places,
                                  issue.detail + tuple(f'known.{entry.id} names this finding; this change added it, '
                                                       'so it stays red' for entry in naming)))
                said.update(entry.id for entry in naming)
            elif function in issue.fresh:
                if ignoring and not speaking:
                    ignored.add((issue.name, function))
                elif shown:
                    lines.append(Line(new or 'impact', issue.name, function, text, IMPACT_STEP, places, issue.detail))
            elif ignoring and not speaking:
                ignored.add((issue.name, function))
            elif shown and (everything or (function in touched_functions if function else bool(issue.files & touched_files))):
                for entry in speaking:
                    if everything or entry.nodes & touched_functions or entry.files & touched_files:
                        lines.append(Line('known', f'known.{entry.id}', function, f'known.{entry.id}' + (f' at {where}' if where else ''),
                                          _known_step(entry), places, _known_detail(entry)))
                        said.add(entry.id)
                if not speaking:
                    lines.append(Line('before', issue.name, function,
                                      f'{issue.subject} {verb} {what}' if many else
                                      f'{issue.subject} at {place} {verb}' if place else f'{issue.subject} {verb}',
                                      BEFORE_STEP, places, issue.detail))
    for entry in entries:
        if entry.id in said:
            continue
        if entry.finding and (family_of(entry.finding) in ran or entry.finding in ran) and entry.finding not in names:
            gone = (f'copies of {entry.finding.partition(":")[2]} now agree' if family_of(entry.finding) == 'same'
                    else f'{entry.finding} no longer found')
            lines.append(Line('known fixed?', f'known.{entry.id}', '', f'known.{entry.id}: {gone}',
                              FIXED_STEPS[entry.act].format(id=entry.id), (), _known_detail(entry)))
        elif entry.act != 'ignore' and (everything or entry.nodes & touched_functions or entry.files & touched_files):
            lines.append(Line('known', f'known.{entry.id}', '', f'known.{entry.id} at {", ".join(entry.sites)}',
                              _known_step(entry), tuple(entry.sites), _known_detail(entry)))
    for line in extra:
        if line.kind not in KINDS:
            raise ValueError(f'{line.name}: kind {line.kind!r} is not one of signals.KINDS')
        lines.append(line)
    unique = {}
    for line in lines:
        unique.setdefault((line.kind, line.name, line.function), line)
    return sorted(unique.values(), key=lambda line: KINDS.index(line.kind)), len(ignored)


# ---- the end-of-run block (4.3) -------------------------------------------------------------------
# One renderer for every run: the first line counts each kind and FlowGuard's own time, then only lines of the
# kinds, in KINDS order, within the budget of design 4.7; `show --last` prints every line with its detail. A run
# that has findings of its own gives them to `delivery` (Issues, and lines already of their kind); `collect`
# turns them, with the static findings, into lines (`deliver`); `title` and `render_block` print them, and the run
# keeps them with `cache.save_last`. The pytest plugin does so for a session (`Observations.report`); a check that
# runs pytest in batches finds each batch's delivery in `plugin.collect_signals().deliveries` and passes them, with
# its own (`finding`, `copies_issue`, `not_compared`) and the static findings, to one `collect`; the vitest report
# builds its delivery from its judged points the same way (`changed_line`, `copy_says` through `copy_partition`).

MORE = 'python -m flowguard show --last'
WIDTH = 200                 # characters of one line, its paths not counted
PLACES = 3                  # places one line names; more are counted
SHOWN = {'changed': 3, 'impact': 2}        # lines of these kinds shown; the others are counted in `+N more`
OLD = 2                     # before and known lines shown; the others are one count line
NOT_COMPARED_STEP = 'not a failure'
CHANGED_STEP = 'if you meant it, say so'
LEDGER_STEP = 'python -m flowguard ledger check prints what to change'


def version():
    """FlowGuard's MAJOR.MINOR, as the first line names it."""
    from flowguard import __version__
    return '.'.join(__version__.split('.')[:2])


def baseline_label(baseline, kind, ahead=None, option='--flowguard-base'):
    """What the first line says a run compared with: the task start (`since 99f025e`, and how many commits HEAD
    lies after it), HEAD standing in (`since HEAD 99f025e`), an explicit baseline by the option that named it
    (`since --base release/task-start`), a recorded start this repository lacks, or none. A full commit id is
    shortened to its first seven characters; anything else (a branch, a tag, HEAD~1, an abbreviated id) is printed
    as it was given."""
    if not baseline:
        return 'no baseline: nothing compared'
    short = baseline[:7] if SHA.fullmatch(baseline) else baseline
    if kind == 'missing':
        return f'since {short}, not in this repository: nothing compared; run python -m flowguard new-task'
    if kind == 'base':
        return f'since {option} {short}'
    if kind == 'HEAD':
        return f'since HEAD {short}'
    if ahead:
        return f'since {short}, {ahead} commit{"" if ahead == 1 else "s"} before HEAD'
    return f'since {short}'


def title(lines, *, baseline, kind, ahead=None, option='--flowguard-base', seconds):
    """The first line of a run: `FlowGuard 4.3 (since 99f025e): 1 red, 2 known; 3.4 s`. Every kind is counted before
    the budget, red always, the others when there are any; `seconds` is FlowGuard's own work in the run."""
    counts = Counter(line.kind for line in lines)
    told = [f'{counts["red"]} red', *(f'{counts[kind]} {kind}' for kind in KINDS[1:] if kind != 'deprecated' and counts[kind])]
    return f'FlowGuard {version()} ({baseline_label(baseline, kind, ahead, option)}): {", ".join(told)}; {seconds:.1f} s'


def render_block(lines, *, title, everything=False, files=()):
    """The block a run prints: `title`, then the lines in KINDS order. red, loosened and known fixed? are listed in
    full; of the others at most ten: changed 3, before and known 2 (known lines first) and one line counting the rest, impact 2, not
    compared one line summing every such line up, and one `+N more` for the changed and impact lines left out. One
    line keeps at most 200 characters besides its paths (the middle of its text gives way, never its subject, places
    or step) and names at most three places; a place's path is its file name (the shortest unique end of the path
    where another path has that name, of the block or of the repository's file list `files`, read once per run).
    `everything` (`--all`): every line, uncut. `deprecated` lines are never part of it."""
    lines = sorted((line for line in lines if line.kind != 'deprecated'), key=lambda line: KINDS.index(line.kind))
    names = _short_paths((path for line in lines for path in map(_path_of, line.places) if path), files)
    out = [title]
    if everything:
        return '\n'.join(out + [_said(line, names, cap=False) for line in lines])
    by = {kind: [line for line in lines if line.kind == kind] for kind in KINDS}
    out += [_said(line, names) for line in by['red']]
    # known lines first (each is an owner's entry, whose step may be to ask the owner), then before lines; printed in
    # the order of the kinds, the count line after the shown lines of its own kind
    known = by['known'][:OLD]
    before = by['before'][:OLD - len(known)]
    count = []
    left = (len(by['known']) - len(known), len(by['before']) - len(before))       # (known, before) left out
    if sum(left):
        counted = ', '.join(f'{number} {kind}' for number, kind in zip(left, ('known', 'before')) if number)
        count = [('known' if left[0] > left[1] else 'before') + f': {sum(left)} more ({counted}) -> {MORE}']
    out += [_said(line, names) for line in before] + [line for line in count if line.startswith('before')]
    out += [_said(line, names) for line in known] + [line for line in count if line.startswith('known')]
    out += [_said(line, names) for line in by['known fixed?']]
    out += [_said(line, names) for line in by['changed'][:SHOWN['changed']]]
    out += [_said(line, names) for line in by['impact'][:SHOWN['impact']]]
    out += [_said(line, names) for line in by['loosened']]
    if by['not compared']:
        out.append(_cap(_summary(by['not compared'], names)))
    if more := sum(max(0, len(by[kind]) - shown) for kind, shown in SHOWN.items()):
        out.append(f'+{more} more: {MORE}')
    return '\n'.join(out)


def _summary(lines, names):
    """The one `not compared` line: what was not compared (one by name; up to three named after their count, more
    counted as functions, or items when not every one is a function) and why, the most common reason first (each
    line's reasons are its detail)."""
    reasons = Counter()
    for line in lines:
        for reason in dict.fromkeys(_reason(reason) for reason in line.detail or ('no reason recorded',)):
            reasons[reason] += 1
    ranked = [reason for reason, _ in sorted(reasons.items(), key=lambda item: -item[1])]
    noun = 'function' if all(line.function for line in lines) else 'item'
    if len(ranked) == 1:
        said = ranked[0]
    elif len(ranked) == 2:
        said = f'{ranked[0]}, or {ranked[1]}'
    else:
        said = f'{ranked[0]}, {ranked[1]}, or {len(ranked) - 2} other reason{"s" * (len(ranked) > 3)}'
    subjects = [_shorten(_unarrowed(line.text), line.places, names) for line in lines]
    if len(lines) == 1:
        what = subjects[0]
    elif len(lines) <= PLACES:
        what = f'{len(lines)} {noun}s: ' + ', '.join(subjects[:-1]) + ' and ' + subjects[-1]
    else:
        what = f'{len(lines)} {noun}s'
    return f'not compared: {what} ({said}) -> {NOT_COMPARED_STEP}'


def _reason(text):
    """A reason as the not compared line sums it up: its head, before a parenthesis or a semicolon, at most 80
    characters, its own next step after a colon (the whole reason is the line's detail in `show --last`)."""
    head = re.split(r' \(|; ', _unarrowed(text).removeprefix('not compared: '), maxsplit=1)[0].strip()
    return head if len(head) <= 80 else head[:77] + '...'


def _unarrowed(text):
    """Project text on one line whose `a -> b` reads `a: b`: in a line only its step follows ' -> '."""
    return re.sub(r'\s*->\s*', ': ', _one_line(text))


def _one_line(text):
    """Project text on one line: a line break would start a line of the block that is none of its kinds."""
    return re.sub(r'\s*[\r\n]+\s*', ' ', str(text))


def _path_of(place):
    """The path of a place `path:symbol`, `path:line` or `path` (repository-relative, POSIX)."""
    return str(place).partition(':')[0].strip()


def _ends(path):
    """The ends of a repository path, its file name first and the whole path last (a folder's keep their '/')."""
    folder = '/' if path.endswith('/') else ''
    parts = path.removesuffix('/').split('/')
    return ['/'.join(parts[-size:]) + folder for size in range(1, len(parts) + 1)]


def _short_paths(paths, files=()):
    """{path: what the block prints}: its file name (a folder's name with its '/'), or the shortest end of it that no
    other path has, of the block or of the repository (`files`, its file list): an end that is another file's whole
    path, or that another file's path ends with, would name that file too. Without `files` only the block's own
    paths count."""
    paths = sorted(set(paths))
    counts = dict.fromkeys((end for path in paths for end in _ends(path)), 0)
    for other in set(paths) | set(files):
        for end in _ends(other):
            if end in counts:
                counts[end] += 1
    shown = {}
    for path in paths:
        ends = _ends(path)
        shown[path] = next((end for end in ends if counts[end] == 1), ends[-1])
    return shown


def _said(line, names, *, cap=True):
    """One line of the block: `{kind}: {text} -> {step}`, its places' paths shortened, at most three places (the text's
    first, then its step's; each one cut is counted, `(+2 places)`) and 200 characters besides its paths (`cap`)."""
    text, step = _one_line(line.text), _one_line(line.step)
    named = [place for place in dict.fromkeys(line.places) if place and place in text]
    if cap and len(named) > PLACES:
        text = _cut(text, named[PLACES:]) + ' ' + _more_places(len(named) - PLACES)
    shown = named[:PLACES]
    stepped = sorted((place for place in dict.fromkeys(line.places) if place and place in step and place not in shown), key=step.find)
    if cap and len(stepped) > PLACES - len(shown):
        room = PLACES - len(shown)
        step = _cut(step, stepped[room:], _more_places(len(stepped) - room))
    said = _shorten(f'{line.kind}: {text}' + (f' -> {step}' if step else ''), line.places, names)
    if not cap:
        return said
    return _cap(said, [names.get(path, path) for path in map(_path_of, line.places) if path],
                [_shorten(place, (place,), names) for place in line.places if place])


def _more_places(number):
    return f'(+{number} place{"s" * (number != 1)})'


def _cut(text, places, counted=''):
    """`text` without the mentions of `places` (with the comma or `and` that joins each to the one before); `counted`
    takes the place of the first one cut."""
    for number, place in enumerate(places):
        for joined in (', ' + place, ' and ' + place, '  ' + place, ' ' + place, place):
            if joined in text:
                text = text.replace(joined, (' ' + counted) if counted and not number else '', 1)
                break
    return text


def _shorten(text, places, names):
    """`text` with the path of each of `places` as the block prints it (`_short_paths`)."""
    for path in sorted((path for path in map(_path_of, places) if path), key=len, reverse=True):
        text = re.sub(r'(?<![\w./-])' + re.escape(path) + r'(?![\w/-])', lambda _, path=path: names.get(path, path), text)
    return text


def _cap(said, paths=(), places=()):
    """`said` within WIDTH characters besides the paths and places (`path:symbol`) it names: the longest stretch of its
    text that is neither the head up to the first ': ' (kind and subject, and the input `on ...: ` a line is about),
    one of its `places`, nor the step after the last ' -> ' gives way in its middle."""
    spans = sorted({piece for piece in (*places, *paths) if piece}, key=len, reverse=True)
    def width(text):
        for piece in spans:
            text = text.replace(piece, '')
        return len(text)
    if width(said) <= WIDTH:
        return said
    head, _, body = said.partition(': ')
    subject, colon, body = body.partition(': ') if ': ' in body[:80] else ('', '', body)
    body, arrow, step = body.rpartition(' -> ') if ' -> ' in body else (body, '', '')
    head = head + ': ' + subject + colon
    if witness := re.match(r'on .*?: ', body):        # the input a same-name line is about
        head, body = head + witness[0], body[witness.end():]
    kept = {piece for piece in (*places, *paths) if piece}
    pattern = '(' + '|'.join(re.escape(piece) for piece in sorted(kept, key=len, reverse=True)) + ')' if kept else None
    pieces = [piece for piece in (re.split(pattern, body) if pattern else [body]) if piece]
    while width(head + ''.join(pieces) + arrow + step) > WIDTH:
        free = [index for index, piece in enumerate(pieces) if piece not in kept and len(piece) > 7]
        if not free:
            break
        index = max(free, key=lambda index: len(pieces[index]))
        piece = pieces[index]
        excess = width(head + ''.join(pieces) + arrow + step) - WIDTH
        keep = max(4, len(piece) - excess - 3)
        pieces[index] = piece[:(keep + 1) // 2] + '...' + piece[len(piece) - keep // 2:]
        if len(pieces[index]) >= len(piece):
            break
    return head + ''.join(pieces) + arrow + step


def finding(family, name, subject, whats, step, *, function='', places=(), files=(), detail=(), fresh=True):
    """A finding of one member as `deliver` reads it (a `health.Issue`): its first `what`, and how many more it has,
    after the subject (`{subject}: {what}`, `places` the paths the line names), the others in its detail. `fresh`:
    this change added it (findings judged without a baseline, as an intent test's red, always are). A line has one
    ` -> `, before its step: without a `step`, the first `what`'s own next step after its last ` -> ` is the step;
    any other ` -> ` of the words reads `: ` (`days=4 -> rule False, code True` is `days=4: rule False, code True`)."""
    from .health import Issue, LINES_ONLY
    whats = list(dict.fromkeys(_one_line(what) for what in whats)) or ['']
    if not step:
        said, own = split_step(whats[0])
        if own and not own.startswith('rule '):         # `inputs -> rule X, code Y` is no step
            whats[0], step = said, own
    whats = list(dict.fromkeys(what.replace(' -> ', ': ') for what in whats))
    what = whats[0] + (f' (+{len(whats) - 1} more)' if len(whats) > 1 else '')
    return Issue(name, LINES_ONLY, subject, f'{subject}: {what}', step, files=frozenset(files), new=fresh, family=family,
                 subject=subject, parts=((function, tuple(places), what, step),), fresh=frozenset({function}) if fresh else frozenset(),
                 detail=tuple(whats[1:]) + tuple(detail))


def not_compared(subject, reasons, *, function='', places=()):
    """A `not compared` line: what was not compared (its function, or '' for another item) and why (its detail),
    which the block sums up in one line."""
    return Line('not compared', 'not compared:' + (function or subject), function, subject, NOT_COMPARED_STEP,
                tuple(places), tuple(dict.fromkeys(reasons)) or ('no reason recorded',))


def delivery(issues=(), lines=(), *, touched_functions=(), touched_files=(), ran=()):
    """What one run (one pytest session, a vitest report, a check batch) gives the block: its own findings (Issues of
    the families that need no map: rule, flow, same, test, input, ledger, source), lines already of their kind
    (changed, not compared), what it knows the change touches and what its checks judged in full (`ran`, families or
    finding names, as `deliver` reads them). `collect` merges several."""
    return dict(issues=list(issues), lines=list(lines), touched_functions=frozenset(touched_functions),
                touched_files=frozenset(touched_files), ran=frozenset(ran))


def collect(deliveries, found=None, *, everything=False):
    """(lines, ignored) of the deliveries of a run and its static findings (`owners.static_findings`, or None when the
    map checks did not run): every finding, the lines of their kind, the known entries, the families that ran and
    what the change touches, through `deliver`; the families and names that ran are those of the deliveries and the
    static findings together. `ignored` adds the issues a `[structure]` decision closed."""
    issues, extra, functions, files, ran = [], [], set(), set(), set()
    for part in deliveries:
        issues += part['issues']
        extra += part['lines']
        functions |= part['touched_functions']
        files |= part['touched_files']
        ran |= part['ran']
    known, decided = (), 0
    if found is not None:
        issues += found.issues
        extra += found.lines
        functions |= found.touched_functions
        files |= found.touched_files
        known, decided = found.known, len(found.decided)
        ran |= found.ran
    lines, ignored = deliver(issues, touched_functions=functions, touched_files=files, known=known, ran=ran,
                             everything=everything, extra=extra)
    return lines, ignored + decided


def last_run(lines, ignored, *, run, stamp, baseline, kind, title, seconds, deprecated=(), hidden=(), compared=()):
    """What `cache.save_last` keeps of a run for `show --last`, in one shape for every run ('pytest', 'check',
    'check --static', 'vitest'): its first line and seconds, every line, the ignored count, the deprecated features
    it used, the 5.0-deprecated leads that got no line ({feature, text}) and the unchanged points it compared."""
    from dataclasses import asdict
    return dict(stamp=stamp, run=run, baseline=baseline, baseline_kind=kind, title=title, seconds=seconds,
                lines=[asdict(line) for line in lines], ignored=ignored, deprecated=list(deprecated), hidden=list(hidden),
                compared=list(compared))


def changed_line(name, target, file, line, changes, compared, *, cause=None, unanchored=False):
    """The `changed` line of a function whose sealed run answers its recorded inputs differently than at the baseline
    (`changed: {function} ({file}:{line}): ...`, `name` the function's own name, also of a `same NAME` copy):
    `changes` [(inputs, old, new)], the first of the smallest inputs shown (all of them in the detail), `compared` the
    number of inputs compared."""
    rows = [dict(inputs=inputs, before=old, after=new) for inputs, old, new in changes]
    first = rows[0]
    if all(row['inputs'] for row in rows):
        points = {key: _ordered(row['inputs'][key] for row in rows if key in row['inputs']) for key in first['inputs']}
        least = C.smallest([row['inputs'] for row in rows], points)
        first = next((row for row in rows if row['inputs'] == least), first)
    def said(row):
        return f'({", ".join(f"{key}={value_text(value)}" for key, value in row["inputs"].items())}) was {value_text(row["before"])}, now {value_text(row["after"])}'
    place = f'{file}:{line}' if line else file
    detail = [said(row) for row in rows]
    if isinstance(cause, dict):
        detail.append(f'cause: {cause.get("name", "code")} {_shown(cause.get("before"))} -> {_shown(cause.get("after"))}'
                      f' ({cause["file"]}:{cause["line"]})')
    elif cause:
        detail.append(f'cause: {cause}')
    if unanchored:
        detail.append('no flowguard comment: compared because its code changed')
    return Line('changed', f'changed:{target}', target, f'{name} ({place}): {said(first)}; {len(rows)}/{compared} inputs differ',
                CHANGED_STEP, (place,), tuple(_one_line(text) for text in detail))


def value_text(value):
    """A recorded JSON value as Python spells it: 'text', True, None, 3; a raised exception as `raises ...`. A ` -> `
    inside it is written ` -\\u003e ` (the same value in Python and JSON), as ` -> ` is where a line puts its step."""
    if type(value) is dict and set(value) == {'raises'}:
        text = f'raises {value["raises"]}'
    elif type(value) in (dict, list):
        import json
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = repr(value)
    return text.replace(' -> ', ' -\\u003e ')


def split_step(text):
    """(what, step) of a message that ends in its own next step after ` -> `, split at the last one (the words before it
    may quote project text); (text, '') without one."""
    what, arrow, step = text.rpartition(' -> ')
    return (what, step) if arrow else (text, '')


def ascii_text(text):
    """A FlowGuard text written before 4.3 with its full-width punctuation and arrows in ASCII."""
    from .owners import _ascii
    return _ascii(str(text))


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


def copy_says(answers, same, show, owner=None, total=None, apart=(), limit=PLACES):
    """(what, step) of one input of same-name copies in the words of the 4.3 lines, without choosing which copy is
    right: `a.py:f returns 52, b.py:g returns 53`; copies with one answer are listed together (`a and b return 52`),
    the reference first when `owner` names it, whose step is then to make the others agree with it. `apart` and
    `total` as in `copy_answers`. At most `limit` copies are named (None: all), as a line names at most three
    places: the others are counted in the group of their answer (`c and 2 other copies return 53`), never cut out
    of it, and the step names only the copies the text names (`copies_issue` keeps every copy in the detail)."""
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
    room = len(answers) + len(aside) if limit is None else limit
    named = set()
    def name(places):
        nonlocal room
        shown = places[:room]
        room -= len(shown)
        named.update(shown)
        return shown, len(places) - len(shown)
    def others(count):
        return f'{count} other cop{"y" if count == 1 else "ies"}'
    def who(places):
        shown, hidden = name(places)
        names = [('the reference ' if place == owner else '') + place for place in shown] + ([others(hidden)] if hidden else [])
        return names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]
    text = ', '.join(f'{who(places)} {"returns" if len(places) == 1 else "return"} {show(value)}' for value, places in groups)
    if aside:
        shown, hidden = name(list(aside))
        text += '; ' + ', '.join([*(f'{place} differs from the reference on {aside[place]}' for place in shown),
                                  *([f'{others(hidden)} differ{"s" * (hidden == 1)} from the reference on other inputs'] if hidden else [])])
    missing = (total or len(answers)) - len(answers)
    if missing:
        text += f'; {missing} other cop{"y has" if missing == 1 else "ies have"} no result for this input'
    if owner is not None:
        wrong = [place for value, places in groups if owner not in places for place in places]
        listed = [place for place in wrong if place in named]
        hidden = len(wrong) - len(listed)
        listed = ', '.join(listed) + (' and ' if listed and hidden else '') + (others(hidden) if hidden else '')
        return text, f'make {listed} agree with the reference'
    return text, 'decide which copy is right, then make the ' + ('other agree' if len(answers) == 2 else 'others agree')


def copies_issue(name, fresh, old, *, places, files=()):
    """The `same:NAME` finding (`deliver`) of same-name copies from the `copy_partition` lines worded by `copy_says`:
    one member per line, the pairs of copies it shows to differ (`a|b`, sorted), new where this change broke them
    (`fresh`), else old. Its places are the copies the line names; it is touched where a copy's file is. Of more than
    three copies, which a line names three of (`copy_says`), every copy is named in the detail."""
    from .health import Issue, LINES_ONLY
    parts, new = [], set()
    for lines, added in ((fresh, True), (old, False)):
        for where, text, step, pairs in lines:
            function = ';'.join(sorted('|'.join(sorted(pair)) for pair in pairs))
            named = tuple(sorted((place for place in set(places) if place in text), key=text.find))
            parts.append((function, named, f'on {_one_line(where)}: {_one_line(text)}', step))
            if added:
                new.add(function)
    every = list(dict.fromkeys(places))
    return Issue(f'same:{name}', LINES_ONLY, f'same {name}', f'same {name}: copies disagree', parts[0][3] if parts else '',
                 files=frozenset(files), new=bool(new), family='same', subject=f'same {name}', parts=tuple(parts),
                 fresh=frozenset(new), detail=(f'copies: {", ".join(every)}',) if len(every) > PLACES else ())


def copy_lines(inputs, same, show, owner=None, total=None, *, only=None, words=None):
    """The lines of one same-name red, in the same words in pytest and `check`: [(input, text, step, pairs)].

    `inputs` [(input, [(place, value)])] is what the copies answered each input, in the order to report. A line
    is kept on an input where it first shows a copy that differs from the owner (`owner`, its place), so each
    such copy is named, with its step, on its own first input that differs; without an owner that answers, where
    it first shows two copies that differ. `pairs` holds the pairs of places the line shows to differ. On another
    line a copy that answers as the owner but differs from it elsewhere is set apart (`copy_answers`). `only`, one
    set of pairs per input, keeps each input to those of its pairs. `words` words each line (`copy_answers` when
    None, the 4.2 lines `check` and vitest still print; `copy_says` for the 4.3 block)."""
    owned = owner is not None and any(place == owner for _, answers in inputs for place, _ in answers)
    kept, seen = [], set()
    for number, (where, answers) in enumerate(inputs):
        pairs = _differing(answers, same, owner if owned else None)
        if only is not None:
            pairs &= only[number]
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
        text, step = (words or copy_answers)(answers, same, show, owner=owner if owned else None, total=total, apart=apart)
        lines.append((where, text, step, pairs))
    return lines


def _differing(answers, same, owner=None):
    """The pairs of places one input shows to differ: each copy that differs from the owner, or without one
    every two copies that differ. An input the owner does not answer shows none."""
    if owner is not None:
        values = dict(answers)
        return {frozenset((owner, place)) for place, value in answers
                if owner in values and not same(values[owner], value)}
    return {frozenset((place, other)) for number, (place, value) in enumerate(answers)
            for other, theirs in answers[number + 1:] if not same(value, theirs)}


def copy_partition(rows, same, show, owner=None, total=None, *, words=None):
    """Each input judged on its own against the copies' versions at the baseline (design 4.5): neither an old
    disagreement nor an input whose baseline could not run hides a pair of copies newly broken on another input.

    `rows` [(input, now, old, unknown)]: what the copies answer the input now ([(place, value)]), what they answered
    it at the baseline ({place: (value, raised)}) and the places whose baseline could not run on it; a place in
    neither did not exist at the baseline. A pair that differs now is red where it agreed at the baseline (or one
    of its copies is new), before where it already differed on this input, and not compared where a baseline of
    it could not run or both raised the same exception there. Returns the `copy_lines` of each, in that order,
    worded by `words` (`copy_lines`)."""
    inputs = [(where, now) for where, now, _, _ in rows]
    owned = owner if owner is not None and any(place == owner for _, now in inputs for place, _ in now) else None
    split = ([], [], [])
    for where, now, old, unknown in rows:
        kinds = (set(), set(), set())
        for pair in _differing(now, same, owned):
            first, second = pair
            if pair & unknown:
                kind = 2
            elif first in old and second in old:
                (value, raised), (theirs, raised_too) = old[first], old[second]
                kind = 2 if raised and raised_too and same(value, theirs) else 0 if same(value, theirs) else 1
            else:
                kind = 0
            kinds[kind].add(pair)
        for lines, pairs in zip(split, kinds):
            lines.append(pairs)
    return tuple(copy_lines(inputs, same, show, owner, total, only=pairs, words=words) for pairs in split)


def copy_inputs(recorded, numbers, limit=64):
    """The inputs same-name copies are compared on (design 4.5), at most `limit`, and what that cut left out.

    In this order: the recorded inputs; the first recorded input that has a number, with each numeric field set to
    each number the copies use, so that every number is tried; each recorded input with each number in each numeric
    field; the neighbours (+1 and -1) of the numeric fields of all of these. Up to half of the inputs are kept for
    the numbers before the recorded inputs are cut, so neither many recorded calls nor a long table pushes the other
    out. Equal JSON is kept once and a non-finite number never enters; an int and a float stay apart (1 is not 1.0),
    and a bool or None is no number. Rows are made one at a time until `limit` are kept. `recorded` and the inputs
    are {field: value}; the cut is {'recorded': recorded inputs left out, 'numbers': numbers that no input tries}."""
    import itertools
    import json
    import math
    finite = lambda row: not any(type(value) is float and not math.isfinite(value) for value in row.values())
    encode = lambda row: json.dumps(row, sort_keys=True, allow_nan=False)
    numeric = lambda row: [key for key, value in row.items() if type(value) in (int, float)]
    numbers = list({(type(number), number): number for number in numbers
                    if type(number) in (int, float) and math.isfinite(number)}.values())
    recorded = list({encode(row): row for row in recorded if finite(row)}.values())
    def spread(rows):
        return ({**row, key: number} for row in rows for key in numeric(row) for number in numbers)
    def neighbours(rows):
        return ({**row, key: row[key] + step} for row in rows for key in numeric(row) for step in (-1, 1))
    first = next(([row] for row in recorded if numeric(row)), [])
    reserved = {}
    for row in spread(first):
        if len(reserved) == limit // 2:
            break
        reserved.setdefault(encode(row), row)
    room = limit - len(reserved)
    inputs, seen = [], set()
    for row in itertools.chain(recorded[:room], reserved.values(), recorded[room:], spread(recorded),
                               neighbours(recorded), neighbours(spread(recorded))):
        if len(inputs) == limit:
            break
        encoded = encode(row) if finite(row) else None
        if encoded is not None and encoded not in seen:
            seen.add(encoded)
            inputs.append(row)
    tried = {(type(value), value) for row in inputs for value in row.values() if type(value) in (int, float)}
    # a number no input has a field for (no recorded number) is not tried, but the cut did not leave it out
    return inputs, dict(recorded=sum(encode(row) not in seen for row in recorded),
                        numbers=sum((type(number), number) not in tried for number in numbers) if first else 0)


def copy_cut(name, limit, left):
    """The grey line that names what the `limit` of a same-name comparison left out (`copy_inputs`), or None."""
    parts = ([f'{left["recorded"]} recorded inputs'] if left['recorded'] else []) + (
        [f'{left["numbers"]} numbers the copies use'] if left['numbers'] else [])
    return f'{name}: compared on {limit} inputs; {" and ".join(parts)} left out' if parts else None


def copy_red(name, lines):
    """The one red of same-name copies `name` from its `copy_lines`: each input with its step, then the way out."""
    return (f'same-name anchor {name}：' + '；'.join(f'{where}，{text} -> {step}' for where, text, step, _ in lines)
            + '; if intentionally different, use different anchor names and declare distinct')


def rule_steps(rule_id, homes, where, messages=()):
    """The next step of a violated rule by what its red `messages` say, in the same words in pytest, `check` and
    the vitest report (no messages: the code disagrees). The code disagrees with the rule (`-> rule X, code Y`):
    correct the code at `homes`, the places where it disagrees (`change the code so a.py:f follows rule R`, `so
    a.py:f and b.py:g follow rule R`). The rule disagrees with its own regression rows (`self:`, `row`): correct the rows
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
        ('code', f'change the code so {_listed(homes)} {"follows" if len(set(homes)) == 1 else "follow"} rule {rule_id}; '),
        ('rows', f'correct regression rows or rule {where} so the rule and its regression rows agree; '),
        ('gap', f'add rules or regression rows at {where} so undecided cells have a rule result; '),
        ('other', f'inspect rule {where} and correct its source, binding or regression rows; ')) if kind in kinds]
    if conflicts:
        steps.append(f'when the owner decides, first store the exact owner words with python -m flowguard req add, then update rule {where}')
    elif steps:
        steps.append(f'if requirements changed, first store the new owner words with python -m flowguard req add, then update rule {where}')
    return steps


def _listed(places):
    """`a`, `a and b`, `a, b and c`: the places, each once, in their order."""
    places = list(dict.fromkeys(places))
    return places[0] if len(places) == 1 else ', '.join(places[:-1]) + ' and ' + places[-1]


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
