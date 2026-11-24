"""Small, bounded views over comparison facts; never runs application code."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from decimal import Decimal, InvalidOperation

from . import cells as C
from .sources import ACTS, SHA


def _shown(value):
    return C.show(value)


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


# ---- the eight kinds of line (5.0) -----------------------------------------------------------------
# Every finding reaches the agent as `Line`s of these kinds, in this order. `deliver` gives each member of a
# finding its kind from the finding's family, whether this change added it (`Issue.fresh`), what this change
# touches and the entries of `.flowguard/known.toml`; it reads no map, no Git and no file.

KINDS = ('red', 'before', 'known', 'known fixed?', 'changed', 'impact', 'loosened', 'not compared')


@dataclass(frozen=True)
class Line:
    """One line of the end-of-run block, `{kind}: {text} -> {step}`; (kind, name, function) is its identity."""
    kind: str                   # one of KINDS
    name: str                   # the finding's name (Issue.name), 'known.<id>', 'changed:<function>', ...
    function: str = ''          # the finding's member; '' for a file-level one
    text: str = ''              # between '{kind}: ' and ' -> ', paths relative to the repository
    step: str = ''              # after ' -> '
    places: tuple = ()          # the repository-relative places `text` names; a copies line's also those of the
                                # finding's other copies, which its text may leave unnamed (`deliver`)
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
# What a before line says of an old member, unless its finding says it (`Issue.broken`); else 'was broken at task start'.
# A structural resemblance breaks nothing.
BROKEN = {'same': 'disagreed at task start', 'copies': 'differed from its same-named copies at task start'}
IMPACT_STEP = 'fix it, or say why in your report'
# The family whose members are copies of one another. Its finding's own step says how they resemble and who decides
# (`health.copies_step`, R101): its impact line states it in place of IMPACT_STEP, and its before line, whose step is
# BEFORE_STEP, keeps it in its detail. A member's line also holds the places of the finding's other members, which its
# text need not name, so that `known add` records every copy's site (PEMEL23-15a).
COPIES = 'copies'
# The families whose impact line states its finding's own step in place of IMPACT_STEP: a new writer has nothing to
# fix, only a design matter; copies say how they resemble and who decides (COPIES); a table no code FlowGuard reads
# creates rows of may be filled elsewhere, and `fix it` would ask for a creation path no one asked for (PTWF-V116a).
OWN_STEP = ('writers', COPIES, 'uncreated')
# The steps of known lines say what is known and who decides (R101): FlowGuard orders no question to the owner; the
# agent decides when to raise one.
KNOWN_STEPS = {'leave': 'left as it is on purpose; yours to change only if your task is about it',
               'fix': 'marked to fix when its code changes, as this change does'}
FIXED_STEPS = {'leave': 'it was left on purpose: if you meant to fix it, remove known.{id} and say so in your report',
               'ask': 'the owner has not answered known.{id}: if this change settles it, say so in your report',
               'fix': 'if you fixed it, remove known.{id} and say so in your report',
               'ignore': 'if it is fixed, remove known.{id} and say so in your report'}
LOOSENED_STEP = "name it in your report; loosening an agreement is the owner's decision"


def family_of(name):
    """The family of a finding name by its prefix ('pair:A>B' -> 'pair'); '' when the prefix is none."""
    head = name.partition(':')[0]
    return head if head in FAMILIES else ''


def ignore_covers(issue, entries):
    """Whether known.toml's `act = "ignore"` entries cover the finding `issue`: its family may be ignored, an ignore
    entry names it and no entry of another act does. `deliver` counts its members without a line, and the session
    brief leaves it out of its count of open structure problems (`health.assess`)."""
    acts = [entry.act for entry in entries if entry.finding == issue.name]
    return FAMILIES[issue.family][2] and bool(acts) and all(act == 'ignore' for act in acts)


def _known_step(entry):
    if entry.act == 'ask':
        return f'asked the owner on {entry.asked}; no answer yet' if entry.asked else 'an open question for the owner, not asked yet'
    return KNOWN_STEPS[entry.act]


def _asked(entry):
    """What a known line says after its places: an ask entry's question (`: Which scale ...?`), else nothing."""
    return f': {entry.ask}' if entry.act == 'ask' and entry.ask else ''


def _known_sites(entry, touched_functions, touched_files):
    """(text, places) of a known line of `entry` itself: the sites this change touches (`Known.resolved`), with how
    many sites the entry has when it has others (`at capacity.service.ts:capacityService.updateCalendarEntry (1 of
    12 sites)`); every site when it touches none (`--all`)."""
    touched = [site for site, (nodes, files) in zip(entry.sites, entry.resolved)
               if nodes & touched_functions or files & touched_files]
    named = touched or list(entry.sites)
    counted = f' ({len(named)} of {len(entry.sites)} sites)' if len(named) < len(entry.sites) else ''
    return f'known.{entry.id} at {", ".join(named)}{counted}{_asked(entry)}', tuple(named)


def _finding_places(entry, places, touched_functions, touched_files):
    """(places, count) of a known line that an entry's finding gives (code-1): the finding's places this change
    touches, a place being touched when it is one of the entry's sites and this change touches that site
    (`Known.resolved`), with how many places the finding names when it names others (`at fees.py:preview_fee (1 of 2
    places)`), as `_known_sites` names the touched sites; every place when it touches none (`--all`, or a site of the
    entry that is no place of the finding)."""
    sites = dict(zip(entry.sites, entry.resolved))
    touched = [place for place in places if place in sites and (sites[place][0] & touched_functions
                                                                or sites[place][1] & touched_files)]
    named = tuple(touched) or tuple(places)
    return named, f' ({len(named)} of {len(places)} places)' if len(named) < len(places) else ''


def _known_detail(entry):
    return tuple(f'{key}: {getattr(entry, key)}' for key in ('why', 'ask', 'fix', 'source') if getattr(entry, key))


def deliver(issues, *, touched_functions, touched_files, known=(), ran=frozenset(), everything=False, extra=()):
    """(lines, ignored): the findings as `Line`s in KINDS order, and the number of members an `act = "ignore"`
    entry of known.toml covers (counted, never a line).

    A member this change added (in `Issue.fresh`) is red when its family can be red, also when a known entry
    names its finding (the entry goes into the line's detail: an entry never silences a new finding); otherwise
    it gets its family's new kind (impact), unless an ignore entry covers it. Every other member counts when this
    change touches it (its function; for a file-level member, one of the finding's files, as for the parameters of
    same-name copies, PARAMETERS, which their files hold), and with `everything`
    always: a known entry naming its finding gives a `known` line when the change also touches the entry's sites
    (else nothing: `known` needs the entry's sites touched, `before` no entry), naming the finding's places this
    change touches with their count (`_finding_places`), an ignore entry alone counts it,
    and without an entry it is `before`. An ignore entry covers only a family that may be ignored, and an entry
    of another act beside it keeps the member shown. Fields several files write without an agreement (family 'writers')
    have no line of their own except with `everything`. A known entry whose finding belongs to a family that ran
    (`ran`: a family whose checks judged the whole project, or a finding name whose own check ran, as a pytest
    session's sealed comparison of the copies of one same name) and is not among the findings is `known fixed?`
    (`copies of NAME now agree` for same-name copies); any other entry, except an ignore entry, whose
    sites this change touches (`Known.nodes` in `touched_functions` or `Known.files` in `touched_files`, every
    entry with `everything`) and that has no line yet is `known`, naming the sites this change touches (every site
    when it touches none) and how many sites the entry has. A known line of an ask entry gives its question after
    its places. `extra` are lines already of their kind
    (changed, impact, loosened, not compared). Lines are unique by (kind, name, function), the first one kept.
    A part's place is one 'path:symbol' (the line reads `{subject}: {place} {what}`, before `{subject} at {place} was
    broken at task start`) or a tuple of them that `what` names itself (`{subject}: {what}`; before: `{subject}
    disagreed at task start {what}` for same-name copies, `was broken at task start` otherwise). A finding that
    breaks no agreement states its `held` fact instead (pt-smoke-3, a field several files write without a writers
    agreement): `Job.status has no writers agreement and 4 files write it, cancel.py:cancel among them; so at task
    start`. An impact line takes the part's step in the families OWN_STEP names, IMPACT_STEP in any other. The `copies`
    family (COPIES): a before line keeps the part's step in its detail
    (`copies _literal at model_source.py:_literal differed from its same-named copies at task start`), every line of a
    member holds the other members' places too, and a finding that gives `Issue.joint` and whose members this change
    all added is one impact line, `{subject}: {joint}`, holding every member's place, its members still counted one by
    one when an ignore entry covers it.
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
        red, new, _ = FAMILIES[issue.family]
        shown = issue.family != 'writers' or everything
        naming = [entry for entry in entries if entry.finding == issue.name]
        speaking = [entry for entry in naming if entry.act != 'ignore']
        ignoring = ignore_covers(issue, entries)
        names.add(issue.name)
        verb = issue.broken or BROKEN.get(issue.family, 'was broken at task start')
        copies = issue.family == COPIES
        members = tuple(dict.fromkeys(part[1] for part in issue.parts if part[1] and isinstance(part[1], str))) if copies else ()
        # one impact line for a finding this change added every member of, when it gives the text naming them all
        joint = bool(issue.joint) and issue.fresh == {part[0] for part in issue.parts}
        for function, place, what, step in issue.parts:
            # A tuple of places is named by `what` itself, which reads on after the subject (and after the verb of a
            # before line: `same N disagreed at task start on year=2025: ...`).
            many = isinstance(place, tuple)
            places = tuple(place) if many else (place,) if place else ()
            text = f'{issue.subject}: {place} {what}' if place and not many else f'{issue.subject}: {what}'
            where = ', '.join(places)
            held = places + tuple(other for other in members if other not in places)   # a line's places
            if function in issue.fresh and red:
                lines.append(Line('red', issue.name, function, text, step, places,
                                  issue.detail + tuple(f'known.{entry.id} names this finding; this change added it, '
                                                       'so it stays red' for entry in naming)))
                said.update(entry.id for entry in naming)
            elif function in issue.fresh:
                if ignoring:
                    ignored.add((issue.name, function))
                elif shown and joint:
                    if function == issue.parts[0][0]:
                        lines.append(Line(new or 'impact', issue.name, function, f'{issue.subject}: {issue.joint}',
                                          step if issue.family in OWN_STEP else IMPACT_STEP, held, issue.detail))
                elif shown:
                    lines.append(Line(new or 'impact', issue.name, function, text,
                                      step if issue.family in OWN_STEP else IMPACT_STEP, held, issue.detail))
            elif ignoring:
                ignored.add((issue.name, function))
            elif shown and (everything or (function in touched_functions if function and function != PARAMETERS
                                           else bool(issue.files & touched_files))):
                for entry in speaking:
                    if everything or entry.nodes & touched_functions or entry.files & touched_files:
                        named, counted = _finding_places(entry, places, touched_functions, touched_files)
                        lines.append(Line('known', f'known.{entry.id}', function, f'known.{entry.id}'
                                          + (f' at {", ".join(named)}{counted}' if named else '') + _asked(entry),
                                          _known_step(entry), named, _known_detail(entry)))
                        said.add(entry.id)
                if not speaking and issue.held:     # a fact that held, not an agreement that was broken
                    lines.append(Line('before', issue.name, function,
                                      f'{issue.held}: {what}; so at task start' if many else
                                      f'{issue.held}, {place} among them; so at task start' if place else
                                      f'{issue.held}; so at task start', BEFORE_STEP, places, issue.detail))
                elif not speaking:
                    # `same N disagreed at task start on x=3: ...`; a copies line of no input reads on after a colon
                    colon = ': ' if issue.family in BROKEN and not what.startswith('on ') else ' '
                    lines.append(Line('before', issue.name, function,
                                      f'{issue.subject} {verb}{colon}{what}' if many else
                                      f'{issue.subject} at {place} {verb}' if place else f'{issue.subject} {verb}',
                                      BEFORE_STEP, held, issue.detail + ((step,) if copies else ())))
    for entry in entries:
        if entry.id in said:
            continue
        if entry.finding and (family_of(entry.finding) in ran or entry.finding in ran) and entry.finding not in names:
            gone = (f'copies of {entry.finding.partition(":")[2]} now agree' if family_of(entry.finding) == 'same'
                    else f'{entry.finding} no longer found')
            lines.append(Line('known fixed?', f'known.{entry.id}', '', f'known.{entry.id}: {gone}',
                              FIXED_STEPS[entry.act].format(id=entry.id), (), _known_detail(entry)))
        elif entry.act != 'ignore' and (everything or entry.nodes & touched_functions or entry.files & touched_files):
            text, places = _known_sites(entry, touched_functions, touched_files)
            lines.append(Line('known', f'known.{entry.id}', '', text, _known_step(entry), places, _known_detail(entry)))
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
# The reason of the one not compared item a vitest run gives when its package's static test did not report to it (a
# filtered run): the map checks (every agreement, known entry and ledger entry) did not run, so the block prints it on
# a line of its own (`render_block`), never summed up with the reasons of the other items.
MAP_CHECKS_NOT_RUN = 'map checks did not report to this vitest run'
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


def title(lines, *, baseline, kind, ahead=None, option='--flowguard-base', seconds, note=''):
    """The first line of a run: `FlowGuard 4.3 (since 99f025e): 1 red, 2 known; 3.4 s`. Every kind is counted before
    the budget, red always, the others when there are any; `seconds` is FlowGuard's own work in the run. `note` says
    what the run did not cover before the time, for a pytest session that ended before its selected tests had all run
    (`plugin.ended_early`: `0 red; run ended early (exit 3): 2 of 3 selected tests ran, the rest not checked; 0.1 s`),
    or, for a vitest run, how long its preparation waited for another FlowGuard run's write to the cache
    (`common.waited_note`: `0 red; waited 9 s for .flowguard/cache/map.sqlite (another FlowGuard run was writing it);
    8.5 s`); '' for a run that finished without either."""
    counts = Counter(line.kind for line in lines)
    told = [f'{counts["red"]} red', *(f'{counts[kind]} {kind}' for kind in KINDS[1:] if counts[kind])]
    return (f'FlowGuard {version()} ({baseline_label(baseline, kind, ahead, option)}): {", ".join(told)}'
            + (f'; {_one_line(note)}' if note else '') + f'; {seconds:.1f} s')


def render_block(lines, *, title, everything=False, files=()):
    """The block a run prints: `title`, then the lines in KINDS order. red, loosened and known fixed? are listed in
    full; of the others at most eleven: changed 3, before and known 2 (known lines first) and one line counting the rest, impact 2, not
    compared the item whose map checks did not report to a vitest run (MAP_CHECKS_NOT_RUN) on a line of its own and one
    line summing every other such line up, and one `+N more` for the changed and impact lines left out. One
    line keeps at most WIDTH (200) characters besides its paths as far as its words allow (`_cap`: the middle of its
    text gives way, never its subject, places or step; a line of copies that take different parameters gives way by
    whole return types, then parameter lists, `_cap_parameters`; an impact line of writes moved to a helper, or
    written by one only under a condition, by its other callers and counts, then by counting its field lists, and
    by its counts alone where no form fits, `_cap_moved`), and is longer where they do not: a copies line whose step
    alone passes WIDTH keeps its words, and those two lines are longer than WIDTH where what they keep is. It names
    at most three places; a place's path is its file name (the shortest unique end of the path where another path
    has that name, of the block or of the repository's file list `files`, read once per run).
    `everything` (`--all`): every line, uncut."""
    lines = sorted(lines, key=lambda line: KINDS.index(line.kind))
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
    # whether the map checks ran decides what `0 red` covers: their item is never one of the summed reasons
    alone, summed = [], []
    for line in by['not compared']:
        (alone if MAP_CHECKS_NOT_RUN in line.detail else summed).append(line)
    out += [_summary([line], names) for line in alone]
    if summed:
        out.append(_summary(summed, names))
    if more := sum(max(0, len(by[kind]) - shown) for kind, shown in SHOWN.items()):
        out.append(f'+{more} more: {MORE}')
    return '\n'.join(out)


REASONS_KEPT = 40           # characters the reasons of the not compared line keep at least before its items are counted


def _summary(lines, names):
    """The one `not compared` line: what was not compared (one by name, a function by its own (`_function_named`); up
    to three named after their count, more counted as functions, or items when not every one is a function) and why,
    the most common reason first (each line's reasons are its detail). It keeps WIDTH characters besides its paths and
    places (`_width`), and an item is never cut: the reasons give way in their middle, down to REASONS_KEPT characters,
    and when the named items leave less room than that they are counted (`3 items`). A single item keeps its name and
    place: its reasons give way first, then its own text before its place, in its middle (`_fit`)."""
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
    subjects = [_shorten(_unarrowed(_function_named(line)), line.places, names) for line in lines]
    counted = f'{len(lines)} {noun}{"s" * (len(lines) != 1)}'
    named = [subjects[0]] if len(lines) == 1 else \
        [f'{counted}: ' + ', '.join(subjects[:-1]) + ' and ' + subjects[-1]] if len(lines) <= PLACES else []
    kept = [*(names.get(path, path) for line in lines for path in map(_path_of, line.places) if path),
            *(_shorten(place, (place,), names) for line in lines for place in line.places if place)]
    if len(lines) == 1:
        fixed = _width(f'not compared:  () -> {NOT_COMPARED_STEP}', kept)
        reason = _middle(said, max(WIDTH - fixed - _width(subjects[0], kept), min(len(said), REASONS_KEPT)))
        return f'not compared: {_fit(subjects[0], WIDTH - fixed - len(reason), kept)} ({reason}) -> {NOT_COMPARED_STEP}'
    for what in [*named, counted]:
        room = WIDTH - _width(f'not compared: {what} () -> {NOT_COMPARED_STEP}', kept)
        if room >= min(len(said), REASONS_KEPT) or what == counted:
            return f'not compared: {what} ({_middle(said, max(room, REASONS_KEPT))}) -> {NOT_COMPARED_STEP}'


def _function_named(line):
    """The subject of a not compared line as the block's summary names it: a function's line (`{name} ({place})`) by
    the function's own name, which an agreement's copies share no name of (`can_view (scope.py:2)`, not `PROJECT_SCOPE
    (scope.py:2)`); any other line by its text."""
    place = line.places[0] if line.function and line.places else ''
    if place and line.text.endswith(f' ({place})'):
        return f'{line.function.rpartition(":")[2] or line.function} ({place})'
    return line.text


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


_WRITTEN = re.compile(r'(?:#|//) flowguard: ')       # where a step's comment to write begins


def _said(line, names, *, cap=True):
    """One line of the block: `{kind}: {text} -> {step}`, its places' paths shortened, at most three places (the text's
    first, then its step's; each one cut is counted, `(+2 places)`) and WIDTH characters besides its paths as far as
    `_cap` cuts it (`cap`). A comment the step tells the user to write (from its `# flowguard: ` or `// flowguard: `
    on) is printed as written: its positions (`except=pkg/fees.py:move(...)`) name their files by the whole path a
    comment needs."""
    text, step = _one_line(line.text), _one_line(line.step)
    named = [place for place in dict.fromkeys(line.places) if place and place in text]
    if cap and len(named) > PLACES:
        text = _cut(text, named[PLACES:]) + ' ' + _more_places(len(named) - PLACES)
    shown = named[:PLACES]
    stepped = sorted((place for place in dict.fromkeys(line.places) if place and place in step and place not in shown), key=step.find)
    if cap and len(stepped) > PLACES - len(shown):
        room = PLACES - len(shown)
        step = _cut(step, stepped[room:], _more_places(len(stepped) - room))
    # a comment the step tells the user to write keeps its paths whole: a shortened one would name no file
    written = step[found.start():] if (found := _WRITTEN.search(step)) else ''
    said = _shorten(f'{line.kind}: {text}' + (f' -> {step[:len(step) - len(written)]}' if step else ''),
                    line.places, names) + written
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


_CHANGED = re.compile(r'(\(.*?\))( was )(.*)(, now )(.*)(; \d+/\d+ inputs differ)', re.S)    # `changed_line`'s words
_KEYED = re.compile(r'(\(.*?\))( now )((?:adds|removes|changes) .*)(; \d+/\d+ inputs differ)', re.S)    # `_keys_said`'s
_GIVE = ((0, 36), (1, 4), (0, 4))      # (rank, characters kept at least) in the order the text gives way


def _cap(said, paths=(), places=()):
    """`said` within WIDTH characters besides the paths and places (`path:symbol`) it names. Its head up to the first
    ': ' (kind and subject), its places and the step after the last ' -> ' stay whole; the rest gives way in the middle
    of its longest stretches, cut to one length together: first the input the line is about (a changed line's inputs,
    a same-name line's `on ...:`), down to 36 characters, then the other stretches, then that input further. A
    changed line keeps the words between its values: `(inputs) was X, now Y; k/n inputs differ`, and between its
    inputs and the keys that changed: `(inputs) now adds K=V (3 other keys equal); k/n inputs differ`. An impact line of
    writes moved to a helper, or of a helper it calls that writes them only under a condition, keeps what went where
    (`_cap_moved`). A line that would still be longer than WIDTH with every stretch cut as far as it goes keeps its
    words (a copies line, whose step names who decides and the route that records it): cutting would leave it neither
    within WIDTH nor readable. A line of copies that take different
    parameters whose signatures `_signatures` reads is never cut inside one (`_cap_parameters`); one it cannot read (a
    copy its places leave unknown, a return type that names another copy) gives way in its middle as other lines do."""
    def width(text):
        return _width(text, (*places, *paths))
    if width(said) <= WIDTH:
        return said
    if said.startswith('impact: ') and any(kind in ('moved', 'via') for kind, _, _ in
                                           _clauses(said.rpartition(' -> ')[0][len('impact: '):])):
        return _cap_moved(said, width)
    if (signatures := _signatures(said, places)) is not None:
        return _cap_parameters(signatures, width)
    head, _, body = said.partition(': ')
    subject, colon, body = body.partition(': ') if ': ' in body[:80] else ('', '', body)
    body, arrow, step = body.rpartition(' -> ') if ' -> ' in body else (body, '', '')
    head = head + ': ' + subject + colon
    kept = {piece for piece in (*places, *paths) if piece}
    pattern = '(' + '|'.join(re.escape(piece) for piece in sorted(kept, key=len, reverse=True)) + ')' if kept else None
    def stretches(text, rank):
        """[text, rank] of the stretches of `text` between its places (rank None: a place, never cut)."""
        return [[piece, None if piece in kept else rank] for piece in (re.split(pattern, text) if pattern else [text]) if piece]
    pieces = []
    if body.startswith('on '):
        # the input a same-name line is about ends at the last ': ' before the first copy the line names
        first = min((body.find(piece) for piece in kept if piece in body), default=-1)
        end = body.rfind(': ', 0, first) if first > 0 else body.find(': ')
        if end > 3:
            pieces, body = [['on ', None], *stretches(body[3:end], 0), [': ', None]], body[end + 2:]
    changed = (_CHANGED.fullmatch(body) or _KEYED.fullmatch(body)) if head.startswith('changed: ') else None
    if changed:
        # its inputs, then its words (never cut) and its values or the keys that changed, in turn
        parts = changed.groups()
        pieces += stretches(parts[0], 0)
        for number, part in enumerate(parts[1:]):
            pieces += stretches(part, 1) if number % 2 else [[part, None]]
    else:
        pieces += stretches(body, 1)
    def total():
        return width(head + ''.join(piece for piece, _ in pieces) + arrow + step)
    shortest = min(least for _, least in _GIVE) + 3          # what a stretch that gives way keeps at last
    if width(head + ''.join(piece if own is None else piece[:shortest] for piece, own in pieces) + arrow + step) > WIDTH:
        return said
    for rank, least in _GIVE:
        _give(pieces, rank, least, total() - WIDTH)
    return head + ''.join(piece for piece, _ in pieces) + arrow + step


def _give(pieces, rank, least, excess):
    """The longest stretches of `rank` among `pieces` ([text, rank]) give way in their middle together, to one length,
    until `excess` characters are gone or each keeps `least`."""
    free = [index for index, (piece, own) in enumerate(pieces) if own == rank and len(piece) > least + 3]
    if excess <= 0 or not free:
        return
    level = max(len(pieces[index][0]) for index in free)
    while level > least + 3 and sum(max(0, len(pieces[index][0]) - level) for index in free) < excess:
        level -= 1
    for index in free:
        pieces[index][0] = _middle(pieces[index][0], level)


def _cap_moved(said, width):
    """An impact line of writes moved to a helper, or of writes a helper it calls makes only under a condition
    (`owners.field_impact`; its clauses, joined by '; ', read by `_clauses`), in its least shortened form within WIDTH
    (PTWF-V125, PEMEL17-18, 5.1 review). Each `F's writes of FIELDS moved to G, which it calls (place)`, each `it calls
    G (place), which writes them only under a condition` (or `in a callback`, and `G (place), which it calls only
    under a condition, writes them`) and every other clause of what the function changed stay: `F now writes`, `no
    longer writes` and `writes M.? where it wrote`, each at least as a count, and `now deletes M (place)` whole. What
    gives way, in this order and only while the line is longer than WIDTH: each list of G's other callers becomes a
    count, the longest first (`other callers of G: 2`); then the writer and reader counts go, then the callers counts,
    and `...` at the end says that something went; then the field lists are counted, the longest first and those of
    the moved and conditional clauses last, each where that is shorter (`no longer writes 1 field`, `writes of 2
    fields moved to G`); a list that holds the field of the step's `show NAME` keeps that one (`writes of
    ProjectMember.projectId and 1 more moved to G`), so the step names a field the line names. Once the line fits,
    what now fits comes back: the callers counts, then the writer and reader counts. Where no form fits WIDTH (with
    Planning Tool's and PEMEL's names the kept clauses and the step alone pass it), counting names would buy nothing:
    the line keeps every field name and the callers counts and drops only the writer and reader counts, as `_cap`
    keeps a line's words. `show --last` keeps the whole line."""
    body, arrow, step = said.rpartition(' -> ')
    named = re.search(r'python -m flowguard show (\S+?)\)?\Z', step)
    shown = named[1] if named else None
    clauses = [[kind, parts, text] for kind, parts, text in _clauses(body[len('impact: '):])]

    def line(clauses):
        went = any(kind in ('callers', 'counts') and not text for kind, _, text in clauses)
        return 'impact: ' + '; '.join([text for _, _, text in clauses if text] + ['...'] * went) + arrow + step

    def longest(kinds):
        """The indexes of the clauses of `kinds`, the longest first, as long as the line is longer than WIDTH."""
        for index in sorted(range(len(clauses)), key=lambda index: -len(clauses[index][2])):
            if clauses[index][0] in kinds and width(line(clauses)) > WIDTH:
                yield index
    for index in longest(('callers',)):
        head, names, more = clauses[index][1]
        clauses[index][2] = f'{head}{len(names.split(", ")) + int(more or 0)}'
    gone = {}
    for index in longest(('counts',)):
        gone[index], clauses[index][2] = clauses[index][2], ''
    named_form = line(clauses)              # every field name and the callers counts kept
    for index in longest(('callers',)):
        gone[index], clauses[index][2] = clauses[index][2], ''
    for kinds in (('change', 'hidden'), ('moved', 'via')):
        for index in longest(kinds):
            kind, (head, model, fields, tail), text = clauses[index]
            if fields != 'them':
                counted = head + _fields_counted(fields, shown, model) + (' (fields not visible)' if kind == 'hidden' else tail)
                clauses[index][2] = min(text, counted, key=len)
    if width(line(clauses)) > WIDTH:
        return named_form
    for index in sorted(gone, key=lambda index: clauses[index][0] != 'callers'):
        clauses[index][2] = gone[index]
        if width(line(clauses)) > WIDTH:
            clauses[index][2] = ''
    return line(clauses)


# the clauses of `owners.field_impact`'s impact line that `_cap_moved` reads, by their words; of each that names
# fields a count may stand for, (head, model, fields, tail)
_CLAUSES = (('moved', re.compile(r"((?:\S+'s|its) writes of )()(.+?)( moved to \S+, which it calls \(.*\))\Z")),
            ('via', re.compile(r'(it calls \S+ \(.*?\), which writes )()(.+?)( only under a condition| in a callback)\Z')),
            ('via', re.compile(r'(\S+ \(.*?\), which it calls (?:only under a condition|in a callback), writes )()(.+)()\Z')),
            ('callers', re.compile(r'(other callers of \S+: )(.+?)(?: and (\d+) more)?\Z')),
            ('counts', re.compile(r'\d+ other writers?\b.*\Z')),
            ('hidden', re.compile(r'((?:\S+ )?writes (\S+)\.\? where it wrote )([^()]+?)( \(fields not visible\b.*\))\Z')),
            ('change', re.compile(r'((?:\S+ )?(?:now|no longer) writes )()(.+)()\Z')))


def _clauses(body):
    """[(kind, groups, text)] of the clauses of an impact line's words, split at each '; ' outside parentheses: kind
    `moved`, `callers`, `counts`, `hidden` or `change` (`_CLAUSES`), `kept` for any other (`now deletes M (place)`)."""
    parts, depth, start = [], 0, 0
    for index, character in enumerate(body):
        depth += {'(': 1, ')': -1}.get(character, 0)
        if not depth and body.startswith('; ', index):
            parts.append(body[start:index])
            start = index + 2
    parts.append(body[start:])
    found = []
    for part in parts:
        kind, match = next(((kind, match) for kind, pattern in _CLAUSES if (match := pattern.match(part))), ('kept', None))
        found.append((kind, match.groups() if match else (), part))
    return found


def _fields_counted(fields, shown, model=''):
    """A field list (`M.a, M.b`, of `model` when its names are bare) as a count, `2 fields`; one that holds `shown`
    keeps it, `M.a and 1 more`."""
    names = fields.split(', ')
    keys = [f'{model}.{name}' if model else name for name in names]
    if shown in keys:
        return f'{names[keys.index(shown)]} and {len(names) - 1} more' if len(names) > 1 else fields
    return f'{len(names)} field{"s" * (len(names) != 1)}'


# the end of `copies_parameters`' words, after the last copy it names
_APART = re.compile(r'(?:(?:, | and )\d+ other cop(?:y|ies))? take different parameters\Z')
# a copy (`path:function(`) after the words that join two, inside what would read as a return type
_COPY = re.compile(r'(?:, | and )[^\s(),:]+:[^\s(),:]+\(')


def _signatures(said, places):
    """[head, [place, (parameters), ': return type' or '', joint]..., tail] of a line of copies that take different
    parameters (`copies_parameters`: `red: same NAME: a.ts:f(x): boolean and b.ts:g(xs): X[] take different parameters
    -> step`), each copy at a place of `places` followed by its parameter list (`joint`: the ', ' or ' and ' before the
    next copy), which ends at the parenthesis that closes it (`_closed`: one inside a quoted default is no
    parenthesis); the tail from the words after the last copy on, its step too. None for any other line, and where
    `places` leave a copy the words name unknown (it would read as part of a return type)."""
    body, arrow, step = said.rpartition(' -> ')
    end = _APART.search(body) if arrow else None
    if end is None:
        return None
    at = []
    for place in {place for place in places if place}:
        start = body.find(place + '(')
        while start >= 0:
            if start == 0 or body[start - 1] == ' ':
                at.append((start, place))
            start = body.find(place + '(', start + 1)
    at.sort()
    if len(at) < 2 or at[0][0] > end.start():        # the words name two copies at least
        return None
    parts = [body[:at[0][0]]]
    for number, (start, place) in enumerate(at):
        opened = start + len(place)
        close = _closed(body, opened, end.start())
        if close is None:
            return None         # no parameter list closes before the next copy
        stop = at[number + 1][0] if number + 1 < len(at) else end.start()
        rest = body[close:stop]
        joint = next((joint for joint in (' and ', ', ') if rest.endswith(joint)), '') if number + 1 < len(at) else ''
        returned = rest[:len(rest) - len(joint)]
        if (number + 1 < len(at) and not joint) or (returned and not returned.startswith(': ')) or _COPY.search(returned):
            return None
        parts.append([place, body[opened:close], returned, joint])
    return [*parts, body[end.start():] + arrow + step]


def _closed(text, opened, stop):
    """The end of the parameter list that opens at `text[opened]` (its `(`), before `stop`; None where none closes
    there. A parenthesis inside a quoted default (`label=')'`, as `ast.unparse` spells a Python one, or a JS/TS
    string or template) is no parenthesis: a quote opens a string that runs to its next quote of the same kind not
    escaped by a backslash, as the Python and JS/TS readers' tokens read one."""
    depth, quote, index = 0, '', opened
    while index < stop:
        char = text[index]
        if quote:
            if char == '\\':
                index += 1          # the escaped character is the string's
            elif char == quote:
                quote = ''
        elif char in '\'"`':
            quote = char
        elif char in '()':
            depth += 1 if char == '(' else -1
            if not depth:
                return index + 1
        index += 1
    return None


def _cap_parameters(signatures, width):
    """A line of copies that take different parameters (as `_signatures` reads it) within WIDTH, never cut inside a
    signature or a return type: the return types give way first, each whole, the longest first, then the parameter
    lists, all of them; each copy's `path:function` and the words around them stay. Where even that leaves the line
    longer than WIDTH it is longer. `show --last` keeps the whole line."""
    head, *copies, tail = signatures
    def line():
        return head + ''.join(place + parameters + returned + joint for place, parameters, returned, joint in copies) + tail
    for index in sorted(range(len(copies)), key=lambda index: (-len(copies[index][2]), -index)):
        if width(line()) <= WIDTH or not copies[index][2]:
            break
        copies[index][2] = ''
    if width(line()) > WIDTH:
        for copy in copies:
            copy[1] = ''
    return line()


def _width(text, pieces):
    """The characters of `text` that count toward WIDTH: those besides the paths and places (`pieces`) it names."""
    for piece in sorted({piece for piece in pieces if piece}, key=len, reverse=True):
        text = text.replace(piece, '')
    return len(text)


def _fit(text, size, pieces):
    """`text` in at most `size` characters besides the paths and places (`pieces`) it names (`_width`): what comes
    before the first of them gives way in its middle, so the places stay whole."""
    over = _width(text, pieces) - size
    if over <= 0:
        return text
    at = min((text.find(piece) for piece in pieces if piece and piece in text), default=len(text))
    return _middle(text[:at], max(at - over, len('...') + 2)) + text[at:]


def _middle(text, size):
    """`text` in at most `size` characters, its middle given way to '...'."""
    if len(text) <= size:
        return text
    keep = size - 3
    return text[:(keep + 1) // 2] + '...' + text[len(text) - keep // 2:]


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
    return Issue(name, LINES_ONLY, subject, f'{subject}: {what}', step, files=frozenset(files), family=family,
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
    static findings together."""
    issues, extra, functions, files, ran = [], [], set(), set(), set()
    for part in deliveries:
        issues += part['issues']
        extra += part['lines']
        functions |= part['touched_functions']
        files |= part['touched_files']
        ran |= part['ran']
    known = ()
    if found is not None:
        issues += found.issues
        extra += found.lines
        functions |= found.touched_functions
        files |= found.touched_files
        known = found.known
        ran |= found.ran
    lines, ignored = deliver(issues, touched_functions=functions, touched_files=files, known=known, ran=ran,
                             everything=everything, extra=extra)
    return lines, ignored


def last_run(lines, ignored, *, scope, run, stamp, baseline, kind, title, seconds, compared=(), pytest=None):
    """What `cache.save_last` keeps of a run for `show --last` and the brief, in one shape for every run ('pytest',
    'check', 'check --static', 'vitest'): its slot (`cache.REPO`, or `cache.vitest_scope` of its package), the full
    version of the FlowGuard that ran it, its first line and seconds, every line, the ignored count, the unchanged
    points it compared and, for a pytest session, pytest's own outcome (`plugin.session_outcome`: exit, failed, errors,
    stopped), None for the others."""
    from dataclasses import asdict
    from flowguard import __version__
    return dict(scope=scope, version=__version__, stamp=stamp, run=run, baseline=baseline, baseline_kind=kind, title=title,
                seconds=seconds, lines=[asdict(line) for line in lines], ignored=ignored, compared=list(compared),
                pytest=pytest)


KEYS = 3                    # keys a changed line names of a dict result that changed; more are counted


def changed_line(name, target, file, line, changes, compared, *, cause=None, why=''):
    """The `changed` line of a function whose sealed run answers its recorded inputs differently than at the baseline
    (`changed: {function} ({file}:{line}): ...`, `name` the function's own name, also of a `same NAME` copy):
    `changes` [(inputs, old, new)], the first of the smallest inputs shown, `compared` the number of inputs compared.
    An input says what it was and is now (`(days=5) was False, now True`); a dict result, or a list of dicts as long as
    before, says which keys changed (`_keys_said`: `(text='{"version":4}') now adds demandPeriodConvention=
    'legacy-half-open' (3 other keys equal)`), as its whole JSON would lose the difference where the block cuts its
    middle. The detail holds every other input, a keyed one with its full values (`; in full: was {...}, now {...}`),
    and of the input shown only the full values a keyed one leaves out (`in full: was {...}, now {...}`): each input's
    values are printed once. `why` a function without a flowguard comment was compared (`its code changed`, `a
    constant it reads changed: LIMIT`) is the detail's last line."""
    rows = [dict(inputs=inputs, before=old, after=new) for inputs, old, new in changes]
    first = rows[0]
    if all(row['inputs'] for row in rows):
        points = {key: _ordered(row['inputs'][key] for row in rows if key in row['inputs']) for key in first['inputs']}
        least = C.smallest([row['inputs'] for row in rows], points)
        first = next((row for row in rows if row['inputs'] == least), first)
    def said(row):
        inputs = ', '.join(f'{key}={value_text(value)}' for key, value in row['inputs'].items())
        return f'({inputs}) {row["keys"] or row["whole"]}'
    for row in rows:
        row.update(keys=_keys_said(row['before'], row['after']),
                   whole=f'was {value_text(row["before"])}, now {value_text(row["after"])}')
    place = f'{file}:{line}' if line else file
    detail = [f'in full: {first["whole"]}'] if first['keys'] else []
    detail += [said(row) + (f'; in full: {row["whole"]}' if row['keys'] else '') for row in rows if row is not first]
    if isinstance(cause, dict):
        detail.append(f'cause: {cause.get("name", "code")} {_shown(cause.get("before"))} -> {_shown(cause.get("after"))}'
                      f' ({cause["file"]}:{cause["line"]})')
    elif cause:
        detail.append(f'cause: {cause}')
    if why:
        detail.append(f'no flowguard comment: compared because {why}')
    return Line('changed', f'changed:{target}', target, f'{name} ({place}): {said(first)}; {len(rows)}/{compared} inputs differ',
                CHANGED_STEP, (place,), tuple(_one_line(text) for text in detail))


def value_text(value):
    """A recorded JSON value as Python spells it: 'text', True, None, 3; a raised exception as `raises ...`. A ` -> `
    inside it is written ` -\\u003e ` (the same value in Python and JSON), as ` -> ` is where a line puts its step."""
    if type(value) is dict and set(value) == {'raises'}:
        return f'raises {value["raises"]}'.replace(' -> ', ' -\\u003e ')
    return _spelled(value)


def _spelled(value):
    """A JSON value as `value_text` spells it, a dict of the one key `raises` as data too (only a result is raised)."""
    import json
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if type(value) in (dict, list) else repr(value)
    return text.replace(' -> ', ' -\\u003e ')


def _keyed(before, after):
    """Whether two values are read key by key (`_differences`): two dicts, or two lists of dicts of one length."""
    if type(before) is dict and type(after) is dict:
        return True
    return (type(before) is list and type(after) is list and len(before) == len(after) > 0
            and all(type(item) is dict for item in (*before, *after)))


def _differences(before, after, path=''):
    """(added [(path, value)], removed [path], changed [(path, old, new)], equal) of two values `_keyed` reads, key by
    key in JSON's key order and item by item: a nested pair it reads too is read the same way (`summary.total`,
    `rows[1].b`, `[0].value` of a list), any other pair is compared whole by its JSON as `value_text` spells it (one
    key order, NaN equal to NaN, 1 apart from 1.0 and from True); `equal` counts the keys found equal."""
    import json
    def same(left, right):
        return json.dumps(left, sort_keys=True, ensure_ascii=False) == json.dumps(right, sort_keys=True, ensure_ascii=False)
    added, removed, changed, equal = [], [], [], 0
    if type(before) is list:
        pairs = [(f'{path}[{index}]', True, old, True, new) for index, (old, new) in enumerate(zip(before, after))]
    else:
        def named(key):
            return (f'{path}.{key}' if path else key) if re.fullmatch(r'[\w$-]+', key) else \
                f'{path}[{json.dumps(key, ensure_ascii=False)}]'
        pairs = [(named(key), key in before, before.get(key), key in after, after.get(key))
                 for key in sorted(set(before) | set(after))]
    for where, was, old, now, new in pairs:
        if not now:
            removed.append(where)
        elif not was:
            added.append((where, new))
        elif same(old, new):
            equal += 1
        elif _keyed(old, new):
            more = _differences(old, new, where)
            added, removed, changed, equal = added + more[0], removed + more[1], changed + more[2], equal + more[3]
        else:
            changed.append((where, old, new))
    return added, removed, changed, equal


def _keys_said(before, after):
    """What changed between a dict result and its baseline (or a list of dicts as long), key by key (`_differences`):
    `now adds demandPeriodConvention='legacy-half-open', removes legacy, changes reportVersion from 1 to 2 (3 other
    keys equal)`, at most KEYS keys named and the others counted (`(2 more keys differ, 3 other keys equal)`); '' for
    any other pair (a raised exception too), and for one whose values differ only where `value_text` spells them
    alike."""
    raised = any(type(value) is dict and set(value) == {'raises'} for value in (before, after))
    if raised or not _keyed(before, after):
        return ''
    added, removed, changed, equal = _differences(before, after)
    named = [*(('adds', f'{where}={_spelled(new)}') for where, new in added), *(('removes', where) for where in removed),
             *(('changes', f'{where} from {_spelled(old)} to {_spelled(new)}') for where, old, new in changed)]
    if not named:
        return ''
    verbs = {}
    for verb, said in named[:KEYS]:
        verbs.setdefault(verb, []).append(said)
    more = len(named) - KEYS
    counted = [*([f'{more} more key{"s" * (more != 1)} differ{"s" * (more == 1)}'] if more > 0 else []),
               *([f'{equal} other key{"s" * (equal != 1)} equal'] if equal else [])]
    said = 'now ' + ', '.join(f'{verb} {_listed(items)}' for verb, items in verbs.items())
    return (said + (f' ({", ".join(counted)})' if counted else '')).replace(' -> ', ' -\\u003e ')


def split_step(text):
    """(what, step) of a message that ends in its own next step after ` -> `, split at the last one (the words before it
    may quote project text); (text, '') without one."""
    what, arrow, step = text.rpartition(' -> ')
    return (what, step) if arrow else (text, '')


def load_step(message):
    """(what, step) of the red line of an intent file the loader refused (`load FILE:LINE`): a name 5.0 removed says
    what to do instead (`api.removed`), any other refusal to correct the declaration; until then none of the file is
    checked. A removed name the file reaches only when it runs (`api.distinct(...)`, `flow(**options)`) comes as the
    loader's `IntentError: [line N: ]` text and reads as the static refusal's line."""
    from .api import REMOVED
    text = ascii_text(message)
    what, step = split_step(re.sub(r'\AIntentError: (?:line \d+: )?', '', text))
    if step and what.endswith(' was removed in 5.0') and what.removesuffix(' was removed in 5.0') in REMOVED:
        return what, step + '; until then none of its file is checked'
    return text, 'correct this declaration; until then none of its file is checked'


def ascii_text(text):
    """A FlowGuard text written before 4.3 with its full-width punctuation and arrows in ASCII."""
    from .owners import _ascii
    return _ascii(str(text))


# ---- same-name copies -----------------------------------------------------------------------------
# The words of one input of same-name copies: `copy_says` for the 4.3 lines, `copy_answers` for the reason a pytest
# session or `check` gives a pair it could not compare at the baseline (`plugin.compare_copies`).

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
        return text, f'make {", ".join(others)} agree with the reference'
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


def parameters_differ(was, now):
    """The not compared reason of a function whose recorded inputs its baseline version takes as other parameters
    (`plugin.baseline_call`, `vitest.shifted`): one head for every function, which the block's summary counts as one
    reason, both versions after it (`was f(record), now f(kind, record)`, in `show --last`)."""
    return f'parameters differ from the baseline (was {was}, now {now})'


PARAMETERS_STEP = 'check whether these are copies of one decision, then correct the code or the marks'
# What is true of JS/TS copies whose parameter names differ (`anchors._parameters_issue`, in the detail): a `//` comment
# maps no names, as a Python copy's `# flowguard: same NAME(days=overdue_days)` does.
FOREIGN_PARAMETERS = ('FlowGuard gives JS/TS copies each input by position and reads a parameter of another name as '
                      'another input; // flowguard: same names no parameters, so JS/TS copies are compared only where '
                      'their parameters have the same names')


def copies_parameters(signatures, limit=PLACES):
    """(what, step) of same-name copies that take different parameters, so that one input cannot be given to every one
    of them (`plugin.compare_copies`, the vitest report): `signatures` [(place, parameters)] in plan order, each
    `place(parameters)` (`scope.py:can_view(user, project) and scope.py:visible_projects(user, projects) take different
    parameters`). At most `limit` copies are named, the others counted. Copies of one decision take the same inputs;
    the step leaves open whether these are copies at all, as a boolean check and a list projection marked with one name
    are not."""
    shown = [f'{place}{parameters}' for place, parameters in signatures[:limit]]
    hidden = len(signatures) - len(shown)
    if hidden:
        shown.append(f'{hidden} other cop{"y" if hidden == 1 else "ies"}')
    named = shown[0] if len(shown) == 1 else ', '.join(shown[:-1]) + ' and ' + shown[-1]
    return f'{named} take different parameters', PARAMETERS_STEP


PARAMETERS = 'parameters'       # the member of a `same:NAME` finding whose copies take different parameters


def parameters_finding(name, what, step, places, *, old, detail=()):
    """The `same:NAME` finding of copies that take different parameters (`copies_parameters`) that the flowguard
    comments show (`anchors._index`, an issue of code 'parameters') or `check` finds where no comment does: one member
    (PARAMETERS) naming each copy (`places`, `path:function`), so check --static, pytest, check and vitest give it as
    one line. It is judged against the task start as every same-name finding is (`deliver`), by one route in every
    runner: `old` is whether the copies took these parameters at the task start (`anchors.parameters_then`, from the
    baseline's facts of the copies' files, `owners.Findings.old_parameters`). It is this change's, red, where the
    change adds or changes a copy's parameters or its comment, and without a baseline; else it is old, whatever else the
    change edits in a copy's file: `before` (or `known` where a known entry naming `same:NAME` speaks for it) in a run
    that touches a copy's file, no line in one that touches none of them, `before` with --all. The brief counts a red
    of it as before once new-task has moved the baseline past it (`cli._last_reds`). A comparison that runs the copies
    says nothing more of a group the comments name so."""
    files = frozenset(place.rpartition(':')[0] for place in places)
    return finding('same', f'same:{name}', f'same {name}', [what], step, function=PARAMETERS, places=places,
                   files=files, detail=detail, fresh=not old)


def copies_issue(name, fresh, old, *, places, files=()):
    """The `same:NAME` finding (`deliver`) of same-name copies from the `copy_partition` lines worded by `copy_says`:
    one member per line, the pairs of copies it shows to differ (`a|b`, sorted), new where this change broke them
    (`fresh`), else old. Its places are the copies the line names; it is touched where a copy's file is. Of more than
    three copies, which a line names three of (`copy_says`), every copy is named in the detail. A line of no input
    (`where` '': copies that take different parameters, `copies_parameters`) says its text alone."""
    from .health import Issue, LINES_ONLY
    parts, new = [], set()
    for lines, added in ((fresh, True), (old, False)):
        for where, text, step, pairs in lines:
            function = ';'.join(sorted('|'.join(sorted(pair)) for pair in pairs))
            named = tuple(sorted((place for place in set(places) if place in text), key=text.find))
            parts.append((function, named, f'on {_one_line(where)}: {_one_line(text)}' if where else _one_line(text), step))
            if added:
                new.add(function)
    every = list(dict.fromkeys(places))
    return Issue(f'same:{name}', LINES_ONLY, f'same {name}', f'same {name}: copies disagree', parts[0][3] if parts else '',
                 files=frozenset(files), family='same', subject=f'same {name}', parts=tuple(parts),
                 fresh=frozenset(new), detail=(f'copies: {", ".join(every)}',) if len(every) > PLACES else ())


def copy_lines(inputs, same, show, owner=None, total=None, *, only=None, words=None):
    """The lines of one same-name red, in the same words in pytest and `check`: [(input, text, step, pairs)].

    `inputs` [(input, [(place, value)])] is what the copies answered each input, in the order to report. A line
    is kept on an input where it first shows a copy that differs from the owner (`owner`, its place), so each
    such copy is named, with its step, on its own first input that differs; without an owner that answers, where
    it first shows two copies that differ. `pairs` holds the pairs of places the line shows to differ. On another
    line a copy that answers as the owner but differs from it elsewhere is set apart (`copy_answers`). `only`, one
    set of pairs per input, keeps each input to those of its pairs. `words` words each line (`copy_answers` when
    None, the reason of a pair whose baseline could not run; `copy_says` for the 4.3 block)."""
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


# The two routes of rule 7 of the FlowGuard rules block by which the owner's decision is stored before a rule changes.
STORE_ROUTES = ('typed words with python -m flowguard req add - --id R<n>, or his pick among options you offered with '
                'python -m flowguard req add REPLY --id R<n> --offer FILE --picked "TEXT"')


def rule_steps(rule_id, homes, where, messages=()):
    """The next step of a violated rule by what its red `messages` say, in the same words in pytest, `check` and
    the vitest report (no messages: the code disagrees). The code disagrees with the rule (`-> rule X, code Y`):
    correct the code at `homes`, the places where it disagrees (`change the code so a.py:f follows rule R`, `so
    a.py:f and b.py:g follow rule R`). The rule disagrees with its own regression rows (`self:`, `row`): correct the rows
    or the rule at `where`; it leaves cells undecided (`gap in`): add the rule or rows. Two rules decide a cell
    differently (`conflict A vs B`): one of them stays, which only the owner can choose; his decision is stored first,
    by either route of the FlowGuard rules block (his typed words, or his pick among options the agent offered), then
    the rule changes. Any other red without a step of its own: correct the rule's source, binding or rows. When the
    need changed, the owner's new decision is stored first, by either route (STORE_ROUTES), then the rule changes."""
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
            conflicts.append(f'rules {pair[1]} and {pair[2]} conflict; only the owner can choose which holds; ')
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
        steps.append(f'when the owner decides, first store his {STORE_ROUTES}, then update rule {where}')
    elif steps:
        steps.append(f"if requirements changed, first store the owner's new {STORE_ROUTES}, then update rule {where}")
    return steps


def _listed(places):
    """`a`, `a and b`, `a, b and c`: the places, each once, in their order."""
    places = list(dict.fromkeys(places))
    return places[0] if len(places) == 1 else ', '.join(places[:-1]) + ' and ' + places[-1]


def _grey(text):
    """(subject, reason) of a grey line written as `NAME: reason` (a FlowGuard text in ASCII, `ascii_text`)."""
    head, found, rest = text.partition(': ')
    if found and head and len(head) <= 80 and '=' not in head and ' ' not in head.strip('[]:.'):
        return head, rest
    return '', text


def missing_start(commit):
    """The one line of a run whose recorded task start this repository lacks (a shallow clone, collected history,
    another clone's cache): it compares nothing, and new-task records HEAD."""
    return f'FlowGuard(recorded task baseline {commit[:7]} is not in this repository: old/new comparison is off; first run python -m flowguard new-task)'


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
            parts.append(f'{expression}={_shown(low[0])}..{_shown(high[0])}' if integer else
                         f'{_shown(low[0])} {"<=" if low[1] else "<"} {expression} {"<=" if high[1] else "<"} {_shown(high[0])}')
        elif low:
            parts.append(f'{expression}{">=" if low[1] else ">"}{_shown(low[0])}')
        elif high:
            parts.append(f'{expression}{"<=" if high[1] else "<"}{_shown(high[0])}')
        for op, value in conditions:
            if op == '!=' and not (low and value < low[0] or high and value > high[0]):
                parts.append(f'{expression}!={_shown(value)}')
    for (left, right), operators in relations.items():
        if '=' in operators or {'<=', '>='} <= operators:
            parts.append(f'{left}={right}')
        else:
            parts.extend(f'{left}{op}{right}' for op in sorted(operators))
    parts.extend(f'{name}={_shown(witness[name])}' for name, kind in kinds.items()
                 if kind.name in ('bool', 'enum', 'str') or witness[name] is None)
    return ', '.join(dict.fromkeys(parts + other)) or C.show_cell(witness)
