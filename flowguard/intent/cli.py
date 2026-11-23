"""A short screen and one pytest check route over generated structure and intent."""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing
import fnmatch
import io
import json
import os
from pathlib import Path
import posixpath
import re
import shlex
import sys
import time
import tomllib
import typing

from flowguard import __version__
from flowguard.map.common import MapError, document_text, git_files
from flowguard.map.requests import (owner_word, owner_words, read_offer_bytes, read_request_bytes, retire_request,
                                    store_choice, store_request)
from flowguard.structure import build
from flowguard.structure.query import may_share, tokens
from . import cache
from .config import INIT_MARK, RECORDED_PYTHON, find_root, load_config


SENTINEL = '''"""Fail when declared FlowGuard intent was not collected."""
def test_flowguard_intent(request):
    from flowguard.intent.plugin import sentinel
    sentinel(request.config)
'''

PROJECT_RULES = '''<!-- flowguard:start -->
## FlowGuard rules for the project agent
1. Start each task with `python -m flowguard new-task`; read its brief (owner rules, open items) before you change code.
2. Run the project's tests. FlowGuard prints last; its first line counts each kind. `python -m flowguard show NAME` explains any name.
3. `red` means your change broke a recorded agreement: fix the code. An `except=`, a removed flowguard comment or a `.flowguard/known.toml` edit that clears it loosens the agreement, which is the owner's decision.
4. `known` and `before` were there before your task; after `->` each line says what is known and who decides. You choose when to raise an open question with the owner.
5. `changed` means a function returns something else for the input shown: if you meant it, say so in your report; if not, fix it. `impact` and `not compared` are not failures.
6. When you find two places that must agree, mark each with `flowguard: same NAME` in the same change; record a problem only the owner can decide in `.flowguard/known.toml` with `act = "ask"` (`known add` writes one).
7. Store the owner's own words once with `python -m flowguard req add - --id R<n>`, never your own text; when he picks one of options you offered, store his reply with them (`--offer FILE --picked TEXT`), the options as your words and the pick as his. Keep `.flowguard/rules.toml` current, each rule's source quoting those words.
<!-- flowguard:end -->
'''


# The commands and the line `--help` gives each.
COMMANDS = {
    'show': 'Find agreements, writers, readers, copies and rules of a name or of "what it decides"',
    'check': 'Recheck the affected rules and tests with pytest; --static runs the map checks without tests',
    'init': 'Wire FlowGuard into this project: pytest plugin, sentinel, CI fragment, rules block, npm test files',
    'new-task': 'Start the next task: record HEAD as the task baseline, then print the brief',
    'ledger': 'The fallback ledger: handlers that may end without raising',
    'req': "Store, list or retire the owner's own words, byte for byte",
    'docs': 'Rewrite the generated regions of Markdown files (<!-- flowguard: generate ... -->) from the map',
    'known': 'Record an open matter in .flowguard/known.toml: known add FINDING --act ACT --why TEXT',
}

# The commands 5.0 removed, by their first word, each with the name its usage line gave it; what a project used them
# for is done by NEW_COMMANDS (`Removed`). The removed options are `_RemovedOption`s of their command's parser.
NEW_COMMANDS = 'python -m flowguard new-task, check or show NAME'
REMOVED_COMMANDS = {'anchor': 'anchor draft', 'model': 'model draft', 'try': 'try', 'watch': 'watch',
                    'compare': 'compare'}
# The top-level commands of FlowGuard 0.70 to 1.4: the releases that had each (`ERAS`, which init names in an AGENTS.md
# that still asks for one), the release that removed it, and the command that now does what a project used it for.
# `main` refuses each as it refuses REMOVED_COMMANDS (PEMEL17-22: a skill bundled with 0.7x told agents to run
# `read --find`); 5.0.1 gave argparse's `invalid choice` for most, and `status` and `where` exited 0 with a note.
EARLIER_COMMANDS = {
    'read': ('0.70-0.75', '1.0', 'python -m flowguard show "words"'),
    'change': ('0.70-0.75', '1.0', 'python -m flowguard check'),
    'map': ('0.70-0.75', '1.0', 'python -m flowguard show NAME or check --static'),
    'target': ('0.70-0.75', '1.0', 'python -m flowguard new-task or check'),
    'template': ('0.70-1.4', '2.0', 'python -m flowguard init'),
    'release': ('0.70-1.4', '2.0', 'python -m flowguard check --all'),
    'status': ('0.71-1.4', '2.0', 'python -m flowguard, which prints the brief'),
    'where': ('0.71-1.4', '2.0', 'python -m flowguard show "words"'),
    'decide': ('0.75-1.4', '2.0', 'python -m flowguard req add FILE --id R<n>'),
    'draft': ('1.2-1.4', '2.0', 'python -m flowguard show NAME'),
}


class Removed(ValueError):
    """A command or option a FlowGuard release removed (5.0, or for EARLIER_COMMANDS 1.0 or 2.0): `main` exits 2 with
    the one line `flowguard: <what> was removed in <release> -> <replacement>` on stderr. The removed command never
    runs: its use is neither ignored nor read as another command."""
    def __init__(self, what, replacement, release='5.0'):
        super().__init__(f'{what} was removed in {release} -> {replacement}')


class _RemovedOption(argparse.Action):
    """An option 5.0 removed (hidden from --help): naming it, with or without a value, raises `Removed`, whatever
    else the command line holds. `what` may hold `{value}`, the value given."""
    def __init__(self, option_strings, dest, *, what, replacement, nargs='?', **options):
        super().__init__(option_strings, dest, nargs=nargs, help=argparse.SUPPRESS, **options)
        self.what, self.replacement = what, replacement

    def __call__(self, parser, namespace, values, option_string=None):
        raise Removed(self.what.format(value=values if isinstance(values, str) else '').strip(), self.replacement)


class _KindOption(_RemovedOption):
    """`req add --kind KIND` (hidden): 4.3 announced only `glossary` and `adoption` for removal, which raise `Removed`;
    `request`, the 4.3 default and the only kind 5.0 stores, is accepted and changes nothing. Any other value is no
    kind, as in 4.3."""
    def __init__(self, option_strings, dest, **options):
        super().__init__(option_strings, dest, nargs=None, **options)

    def __call__(self, parser, namespace, values, option_string=None):
        if values in ('glossary', 'adoption'):
            super().__call__(parser, namespace, values, option_string)
        elif values != 'request':
            parser.error(f"argument --kind: invalid choice: {values!r} (choose from 'request')")


def _spelled(word):
    """One word of a printed command: bare when every shell reads it as it is, else in double quotes, which
    cmd.exe, PowerShell and POSIX shells all read (README: `show "what it decides"`); single quotes are not
    quotes in cmd.exe."""
    return word if re.fullmatch(r'[\w.:/@=,+%-]+', word) else json.dumps(word, ensure_ascii=False)


def _limit(lines, budget, more='show RULE for the complete result'):
    """The first `budget` lines; the last says how many lines and red lines (a line that starts as one)
    are left out and the command `more` that prints them."""
    if len(lines) <= budget:
        return lines
    kept = lines[:max(0, budget - 1)]
    hidden = lines[len(kept):]
    reds = sum(line.startswith(('red ', 'red: ')) for line in hidden)
    return kept + [f'... {len(hidden)} more lines' + (f' ({reds} red)' if reds else '') + ': ' + more]


def _rule_colour(item, result):
    if item.get('superseded_by'):
        return 'superseded'
    values = list(result.get('items', {}).values())
    if not values:
        return 'grey'
    if any(value.get('verdict') == 'red' for value in values):
        return 'red'
    if any(value.get('verdict') == 'grey' for value in values):
        return 'grey'
    return 'green*' if any(value.get('provisional') for value in values) else 'green'


def _map_notice(graph):
    coverage = graph.capabilities()
    foreign = {name: row for name, row in coverage.get('languages', {}).items() if name != 'python'}
    unsupported = coverage.get('unsupported_files', [])
    if not foreign and not unsupported:
        return ''
    parts = [f'{name} {row["parsed"]}/{row["files"]} parsed' for name, row in sorted(foreign.items())]
    if unsupported:
        parts.append(f'{len(unsupported)} unsupported source files (first: {unsupported[0]})')
    return 'Map: ' + '; '.join(parts) + '; static facts, foreign native-home execution not verified.'


BRIEF_LINES = 8            # design 4.7: the one FlowGuard output an agent surely reads before it writes code
BRIEF_RULES = 4
BRIEF_KNOWN = 2
BRIEF_WIDTH = 200
# The findings whose red is judged against the task's baseline: after new-task they are before, unless a file of
# theirs is still dirty. Intent, test and input reds stay red under any baseline (D3, D4).
BASELINE_FAMILIES = frozenset({'pair', 'writer', 'values', 'same', 'changed-alone', 'source', 'ledger'})


def _brief_line(text, more=0, tail=''):
    """A rule or known line of the brief or of `show`: at most BRIEF_WIDTH characters with `tail` (show's place to
    read the whole entry) kept whole; in the brief the last of its kind ends with the count of the entries `show
    rules` lists besides."""
    if more:
        tail, text = f'; +{more} more: python -m flowguard show rules', text.removesuffix('.')
    width = BRIEF_WIDTH - len(tail)
    return (text if len(text) <= width else text[:width - 3] + '...') + tail


KNOWN_ORDER = {'ask': 0, 'fix': 2, 'leave': 3, 'ignore': 4}     # an asked question is still open: after those not asked
KNOWN_WORDS = {'fix': 'to fix when its code changes', 'leave': 'left as it is', 'ignore': 'ignored, not reported'}


def _known_order(entries):
    """known.toml entries in the order the brief and `show` list them: questions not asked yet, asked ones, fix,
    leave, then ignore (which the brief leaves out); file order within each act."""
    return sorted(entries, key=lambda entry: 1 if entry.act == 'ask' and entry.asked else KNOWN_ORDER[entry.act])


def _known_brief(entry):
    """The words of a known.toml entry, one line in the brief and in `show`."""
    if entry.act == 'ask':
        return (f'known.{entry.id}: asked the owner on {entry.asked}, no answer yet: {entry.ask}' if entry.asked
                else f'known.{entry.id}: open question for the owner: {entry.ask}')
    return f'known.{entry.id}: {KNOWN_WORDS[entry.act]}: {entry.why}'


def _brief_reds(cfg, data):
    """(reds, failed) the last checks left that no baseline moves, the one source of the brief's counts of them and of
    the list `show --last` gives: `reds` are intent load errors (the static scan), a failed verification or collection
    and red intent results, one per message; `failed` the failed tests of pytest's scope as (test id, reading), each
    reading the outcome of the last run that ran its test, the most recent first (an ordinary failed test is no red)."""
    from .deps import test_scope
    summary, attempt = data['summary'], data['attempt'] or {}
    reds = [f'load {error["file"]}:{error["line"]}: {error["msg"]}' for error in summary['errors']]
    reds += ['verification: ' + message for message in attempt.get('errors', [])]
    for result in data['results'].values():
        for value in result['items'].values():
            if value.get('kind') == 'load':
                reds.extend('load: ' + message for message in value.get('red', []))
    for rid, item in summary['rules'].items():
        result = data['results'].get(rid, {})
        if _rule_colour(item, result) == 'red':        # a red colour has items
            messages = [message for value in result['items'].values() for message in value.get('red', [])]
            reds.extend(f'{rid}: {message}' for message in messages or ['reported red'])
    if attempt.get('missing') or (attempt.get('collected') and attempt.get('sentinel') != 'ok'):
        reds.append('collection incomplete')
    in_scope = test_scope(cfg)
    failed = sorted(((test, reading) for test, reading in data['tests'].items()
                     if reading['outcome'] == 'failed' and in_scope(test.partition('::')[0])),
                    key=lambda item: (-item[1]['stamp'], item[0]))
    return list(dict.fromkeys(reds)), failed


def _dirty(cfg):
    """The files of the working tree that differ from HEAD, untracked ones too."""
    from flowguard.map.common import git_run
    listed = git_run(cfg.root, 'diff', '--name-only', '-z', '--relative', 'HEAD', '--').stdout
    listed += git_run(cfg.root, 'ls-files', '--others', '--exclude-standard', '-z').stdout
    return {os.fsdecode(name) for name in listed.split(b'\0') if name}


def _recounted(cfg, line):
    """Is this red of the last run one the brief counts from where it is read now: an intent rule's or a test's
    (the intent cache and the test readings, `_brief_reds`), or an input problem of an intent file or a catalog file
    (the static scan and `sources.catalog`)? `check`'s own red that pytest failed with no finding to say why
    (`test:pytest`) is no test's reading: it counts as a red of that run."""
    from .signals import family_of
    from .sources import CATALOG_FILES
    family = family_of(line['name'])
    if family == 'rule' or family == 'test' and line['name'] != 'test:pytest':
        return True
    intent = cfg.rel(cfg.intent)
    files = [place.rpartition(':')[0] for place in line['places']]
    return family in ('input', '') and bool(files) and all(
        file in CATALOG_FILES or file == intent or file.startswith(intent + '/') for file in files)


def _package(run):
    """The folder of a vitest slot's package as the lines name it (`web/`), '' for the repository's top folder, for the
    `repo` slot and for a vitest run 5.0 recorded without its package."""
    folder = run['scope'].partition('vitest:')[2]
    return '' if folder in ('', '.') else folder + '/'


def _slot_label(run):
    """What the brief calls a slot's last run: a vitest package's by its folder (`web/`, `vitest` for the top folder), the
    `repo` slot's by its run (`pytest`, `check`, `check --static`)."""
    return _package(run) or run['run']


def _last_reds(cfg, baseline, runs):
    """(now before, {slot label: still red}) of the reds of each slot's last run (`cache.read_runs`), newest first, but
    those the brief counts where they are read now (`_recounted`). When a slot's run compared with another commit than
    `baseline` (new-task has moved it since), a red of a baseline-judged family whose places' files are all clean
    against HEAD is before now (D26); one that names no place, one with a dirty file and every red of another family
    still count."""
    from .signals import family_of
    before, still, dirty = 0, {}, None
    for run in runs:
        reds = [line for line in run['lines'] if line['kind'] == 'red' and not _recounted(cfg, line)]
        judged = [line for line in reds if family_of(line['name']) in BASELINE_FAMILIES]
        moved = 0
        if judged and baseline is not None and run['baseline'] not in (None, baseline):
            dirty = _dirty(cfg) if dirty is None else dirty
            moved = sum(bool(line['places']) and not any(place.rpartition(':')[0] in dirty for place in line['places'])
                        for line in judged)
        before += moved
        if len(reds) > moved:
            still[_slot_label(run)] = still.get(_slot_label(run), 0) + len(reds) - moved
    return before, still


def _red_tail(still, runs, reds):
    """The brief's count of the reds that still stand (`_last_reds`, and the intent results' `reds` of `_brief_reds`,
    which are pytest's and count with the `repo` slot): `2 red in the last run: python -m flowguard show --last`, naming
    the runs once a vitest package's holds some (`1 red in the last run of web/`, `3 red in the last runs of
    check --static and web/`); '' for none."""
    repo = next((_slot_label(run) for run in runs if run['scope'] == cache.REPO), 'pytest')
    if reds:
        still = dict(still, **{repo: still.get(repo, 0) + len(reds)})
    if not still:
        return ''
    where = '' if list(still) == [repo] else f'{"s" * (len(still) > 1)} of {" and ".join(still)}'
    return f'{sum(still.values())} red in the last run{where}: python -m flowguard show --last'


def _failed_tail(failed):
    """The brief's count of the failed tests it keeps from their last runs (`_brief_reds`), never called red, with the
    most recent: `1 test failed when last run and has not run since: tests/test_a.py::test_x`; '' for none."""
    if not failed:
        return ''
    count = len(failed)
    more = f' and {count - 1} more: python -m flowguard show --last' if count > 1 else ''
    return (f'{count} test{"s" * (count != 1)} failed when last run and {"have" if count != 1 else "has"} not run since: '
            f'{failed[0][0]}{more}')


def _brief(cfg, data, baseline, note='', *, structure=()):
    """The brief (design 4.7, at most BRIEF_LINES lines, no map, no project code): the baseline with its note; the
    first rules of .flowguard/rules.toml in file order; the open matters of .flowguard/known.toml (ask, not asked yet;
    ask, asked; fix; leave; never ignore); the last check's lines (`health.brief_lines`: one count of the open
    structure problems, one of the generated regions out of date); and what
    the last runs left (`cache.read_runs`, one per slot): the reds new-task's moved baseline turned into before, the
    reds that still stand (`_red_tail`), the failed tests kept from their last runs (`_failed_tail`), and invalid
    entries of the two files; then one line when AGENTS.md or CLAUDE.md holds a FlowGuard rules block other than
    the one `init` writes now (`_stale_rules`), never a line of the block, and one line naming each of those files
    that is no UTF-8 or UTF-16 text, with the decoder's error."""
    from .sources import catalog
    version = '.'.join(__version__.split('.')[:2])
    first = f'FlowGuard {version} brief, baseline {baseline[:12] if baseline else "none (no Git commit)"}'
    head = [first + ('; ' + note.removeprefix('baseline: ') if note else '')]
    found = catalog(cfg)
    waiting = _known_order(entry for entry in found.known.values() if entry.act != 'ignore')
    runs = cache.read_runs(cfg)
    before, still = _last_reds(cfg, baseline, runs)
    reds, failed = _brief_reds(cfg, data)
    tail = [f'{before} red from the previous task are now before'] if before else []
    tail += [text for text in (_red_tail(still, runs, reds), _failed_tail(failed)) if text]
    if found.issues:
        tail.append(f'{len(found.issues)} invalid entries in .flowguard/rules.toml or known.toml: python -m flowguard show rules')
    # The project's copy of the rules may still say what this FlowGuard no longer does.
    stale, unreadable = _stale_rules(cfg)
    fixed = [*structure, *(['; '.join(tail)] if tail else []),
             *([f'{" and ".join(stale)} {"hold FlowGuard rules blocks" if len(stale) > 1 else "holds a FlowGuard rules block"} '
                f'that differ{"s" * (len(stale) == 1)} from the one FlowGuard {version} writes: python -m flowguard init '
                f'rewrites {"them" if len(stale) > 1 else "it"}'] if stale else []),
             *(f'{error}; its FlowGuard rules block is not compared' for error in unreadable)]
    known = [_brief_line(_known_brief(entry), len(waiting) - BRIEF_KNOWN if index == BRIEF_KNOWN - 1 else 0)
             for index, entry in enumerate(waiting[:BRIEF_KNOWN])]
    slots = min(BRIEF_RULES, BRIEF_LINES - len(head) - len(fixed) - len(known))
    rules = list(found.rules.values())
    shown = [_brief_line(f'rule.{rule.id}: {rule.text}', len(rules) - slots if index == slots - 1 else 0)
             for index, rule in enumerate(rules[:slots])]
    return [*head, *shown, *known, *fixed]


def screen(cfg, *, new_task=False):
    """The brief. It keeps the task baseline while HEAD descends from it, and on a detached HEAD moves or records
    none; `new_task` (`new-task`) starts the next task at HEAD, a detached one too."""
    from .health import brief_lines
    baseline, note = cache.remember_baseline(cfg, new_task=new_task)
    data = cache.read(cfg)
    from .differences import display
    structure = brief_lines(cfg)        # the last check's counts; the brief builds no map
    display('\n'.join(_brief(cfg, data, baseline, note, structure=structure)))
    return int(bool(data['summary']['errors']))


def _candidate(candidate, full):
    if full:
        return json.dumps(candidate, ensure_ascii=False)
    return f'{candidate["id"]} {candidate.get("file", "")}:{candidate.get("line", "?")}: {candidate.get("reason", "source similarity only")}'


def _candidate_lines(found, full, prefix):
    candidates = found['candidates']
    visible = candidates if full else candidates[:3]
    result = [prefix + _candidate(candidate, full) + (' [lead]' if not full else '') for candidate in visible]
    if len(visible) < len(candidates):
        result.append(f'{len(candidates) - len(visible)} more source candidates; show --full for all pointers')
    return result


def _anchor_targets(index, references, graph=None):
    found = {}
    for reference in references:
        canonical = graph.canonical(reference) if graph is not None and ':' in reference else reference
        for anchor in index.entries:
            if reference == anchor.name or anchor.target in (reference, canonical):
                found[anchor.name, anchor.target, anchor.kind] = anchor
    return sorted(found.values(), key=lambda a: (a.name, a.file, a.target_line, a.kind))


AGREEMENT_KINDS = ('sensor', 'owner')      # the anchors a flowguard agreement comment makes: same (and ref), writers, together


def _field_agreement(anchor):
    """Whether a source anchor is a writers or together agreement on a field: it marks no function."""
    return anchor.kind == 'owner' and not anchor.qual


def _source_pointers(index, references, graph, *, full=False):
    anchors = _anchor_targets(index, references, graph)
    lines = []
    for anchor in anchors:
        # A writers or together agreement marks no function: its place alone, not the map's module id with an empty
        # symbol (`typescript/backend/src/services/x.ts: backend/src/services/x.ts:205`).
        target = '' if _field_agreement(anchor) else anchor.target + ' '
        lines.append(f'anchor {anchor.name} -> {target}{anchor.file}:{anchor.target_line or anchor.line}'
                     + (f'; calibrated_by={anchor.calibrated_by}' if anchor.calibrated_by else ''))
        if full:
            lines.append(f'  {anchor.kind}; source comment L{anchor.line}; '
                         + ', '.join(f'{p.name}: {p.source_type} [{p.unit}]' for p in anchor.parameters))
    for reference in references:
        if reference.startswith('unresolved:'):
            lines.append('navigation unknown: ' + reference)
        elif not _anchor_targets(index, [reference], graph):
            lines.append(f'anchor {reference}: not found in the current source index')
    names = {a.name for a in anchors}
    issues = [i for i in index.issues if i.name in names] + [i for a in anchors for i in a.issues]
    lines.extend(dict.fromkeys(f'{issue.level} anchor {issue.name}: {issue.message}' for issue in issues))
    return anchors, lines


def _copy_pointers(graph, index, anchors, homes, results, words, full):
    excluded = set(homes) | {a.target for a in anchors}
    targets = list(dict.fromkeys([*homes, *(a.target for a in anchors
                 if a.source_role == 'production' and a.kind in {'sensor', 'event'})]))
    candidates, lines = {}, []
    for target in targets:
        live = next((result for result in results if result.get('target') == target and result.get('kind') == 'live'), None)
        scope = [(site.get('where') or target, site['line'], site['text']) for site in live.get('sites', []) if site.get('realized')] if live else None
        # An anchor's target is bound already: its reason not to search names no binding step (a rule's home keeps it).
        found = graph.search_homes(target, sites=scope, not_same=excluded, words=words, k=None,
                                   bound=target in {anchor.target for anchor in anchors})
        if not found['searched']:
            lines.append(found['reason'])
        from .owners import look_alikes      # static copy candidates, the same ones check runs for an owner
        registered = {a.target for a in index.entries if a.kind == 'sensor'}
        for candidate in [*found['candidates'], *look_alikes(load_config(graph.root), graph, target, excluded | registered)]:
            node = graph.node(candidate['id'])
            if node:
                candidate = dict(candidate, file=node['file'], line=node['line'])
            old = candidates.get(candidate['id'])
            rank = lambda row: (row.get('strength') == 'strong', row.get('score', 0))   # a site match over a look-alike
            if old is None or rank(candidate) > rank(old):
                candidates[candidate['id']] = candidate
    found = dict(candidates=sorted(candidates.values(), key=lambda row: (-row.get('score', 0), row['id'])))
    return _unsearched(lines) + _candidate_lines(found, full, 'lead unbound candidate ')


UNREAD_SITES = re.compile(r'copies not searched: the map reads no decision sites in (\S+) code')


def _unsearched(reasons):
    """The copy search's reasons, each once, those of the languages whose decision sites the map does not read as one
    line that names them all (gate-6: `copies not searched: the map reads no decision sites in typescript and tsx
    code` for an agreement on a TS and a TSX copy), where the first of them stood."""
    languages = list(dict.fromkeys(found[1] for reason in reasons if (found := UNREAD_SITES.fullmatch(reason))))
    named = ', '.join(languages[:-1]) + ' and ' + languages[-1] if len(languages) > 1 else ''.join(languages)
    said = f'copies not searched: the map reads no decision sites in {named} code'
    return list(dict.fromkeys(said if UNREAD_SITES.fullmatch(reason) else reason for reason in reasons))


def _unmodelled(index, summary, *, root=None):
    references = {ref for item in summary['rules'].values() for ref in item.get('anchors', [])}
    def identity(anchor):
        return (anchor.name, anchor.target, anchor.file, anchor.source_digest,
                anchor.kind, anchor.target_line, anchor.parameters)
    used = {identity(a) for a in _anchor_targets(index, references)}
    return sorted({a.name for a in index.entries if a.source_role == 'production' and identity(a) not in used})


def _silent_lines(cfg, index, rid, full, limit=10):
    """The case classes a rule gives no result for, from the current rules (never the code). Where no rule
    of its decision decides and a rule there says total=True, they are red."""
    from .engine import Engine
    from .loader import load
    model = load(cfg, anchor_index=index)
    if model.errors or rid not in model.rules:
        return []           # the load errors are printed by show and the load item
    rule = model.rules[rid]
    key = Engine(model).check_key(rule.decides)
    silent, gaps = key['silent'].get(rid, []), key['gaps'] or {}
    if not silent:
        return []
    def listed(values):
        shown = values if full else values[:limit]
        return '; '.join(shown) + (f'; plus {len(values) - len(shown)} classes: show --full {rid} lists all' if len(shown) < len(values) else '')
    lines = [f'undecided: rule {rid} has no result for {len(silent)} classes (total {key["cells"]} classes): {listed(silent)}']
    undecided = [cell for cell in gaps.get('cells', ()) if cell in silent]
    if undecided and gaps.get('total'):
        lines.append(f'red: {", ".join(gaps["total"])} declares total=True, but {len(undecided)} classes have no rule result: {listed(undecided)}'
                     f' -> give these cases a result in the rules, or remove total=True')
    elif undecided and len(undecided) < len(silent):
        lines.append(f'of these, {len(undecided)} classes also have no result from another rule: {listed(undecided)}')
    return lines


def _when(stamp):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stamp))


def _pytest_line(outcome):
    """pytest's own outcome of a session (`plugin.session_outcome`) as `show --last` prints it beside FlowGuard's lines:
    `pytest: exit 1, 1 failed, stopped early (-x)`."""
    errors = outcome['errors']
    return (f'pytest: exit {outcome["exit"]}, {outcome["failed"]} failed' + (f', {errors} error{"s" * (errors != 1)}' if errors else '')
            + (f', {outcome["stopped"]}' if outcome['stopped'] else ''))


def _run_lines(run):
    """One slot's last run as `show --last` prints it: which run it was, with the full version of the FlowGuard that
    ran it and when (`FlowGuard 5.1.0 last run: vitest web/ at 2026-11-23 08:21:55`, local time; a record of 5.0 names
    no version), a later start of the slot that did not report, pytest's own outcome, the run's first line, then every
    one of its lines (no budget, no cut, full paths) with its detail indented under it; how many members an
    `act = "ignore"` entry of known.toml covered, when any did; and the unchanged points an explicit comparison
    compared."""
    from .signals import family_of
    who = f'FlowGuard {run["version"]}' if run.get('version') else 'FlowGuard'
    package = _package(run)
    name = f'{run["run"]} {package}' if package else run['run']
    started = run.get('started') and (f'a {run["run"]} run' + (f' of {package}' if package else '')
                                      + f' started at {_when(run["started"])} did not report')
    if run['stamp'] is None:        # a start note alone (`cache.stamp_start`)
        return [f'{who}: {started}; no earlier run' + (f' of {package}' if package else '') + ' is recorded']
    lines = [f'{who} last run: {name} at {_when(run["stamp"])}']
    if started:
        lines.append(f'{started}; the lines below are from the run at {_when(run["stamp"])}')
    if run.get('pytest'):
        lines.append(_pytest_line(run['pytest']))
    lines.append(run['title'])
    for line in run['lines']:
        lines.append(f'{line["kind"]}: {line["text"]}' + (f' -> {line["step"]}' if line['step'] else ''))
        lines.extend('    ' + detail for detail in line['detail'])
        if family_of(line['name']) not in ('', 'input'):          # the name known add takes
            lines.append(f'    finding {line["name"]}')
    if run['ignored']:
        lines.append(f'ignored: {run["ignored"]} (act = "ignore")')
    if run.get('compared'):
        lines.append('compared, unchanged:')
        lines.extend('    ' + text for text in run['compared'])
    return lines


def _kept_lines(cfg, data):
    """What the brief counts besides the runs' own lines (`_brief_reds`), as `show --last` lists it after them: the
    intent results' reds, and each failed test kept from its last run with its outcome, phase and reason, when it ran
    and whether the last pytest run selected it (a test that run did not select is not known to pass now)."""
    reds, failed = _brief_reds(cfg, data)
    lines = []
    if reds:
        lines.append('red in the intent results and the last pytest attempt (the brief counts these):')
        lines.extend('    ' + red for red in reds)
    if failed:
        last = (data['attempt'] or {}).get('stamp')
        lines.append('tests that failed when last run and have not run since (the brief counts these):')
        for test, reading in failed:
            why = ', '.join(part for part in (reading['phase'], reading['reason']) if part)
            selected = '' if last is None else '; the last pytest run selected it' if reading['stamp'] == last else \
                f'; not selected by the last pytest run, at {_when(last)}'
            lines.append(f'    {test}: {reading["outcome"]}' + (f' ({why})' if why else '') + f' at {_when(reading["stamp"])}{selected}')
    return lines


def show_last(cfg, full=False):
    """`show --last`: the last run of each slot (`cache.read_runs`: pytest, check and check --static share the `repo`
    slot, each vitest package has its own), newest first, each as `_run_lines` prints it, then what the brief counts
    besides their lines (`_kept_lines`). Read from the cache (`cache.read_runs`, `cache.read`), without building the
    map."""
    from .differences import display
    runs, kept = cache.read_runs(cfg), _kept_lines(cfg, cache.read(cfg))
    if not runs and not kept:
        print('FlowGuard: no last run recorded')
        return 0
    display('\n'.join([*(['FlowGuard: no last run recorded'] if not runs else []),
                       *(line for run in runs for line in _run_lines(run)), *kept]))
    return 0


def _holds(text):
    """What `show rules` says of a catalog source that holds; words of a picked option say whose words they are."""
    from .sources import CHOICE_NOTE, parse
    return f'(holds: {CHOICE_NOTE})' if parse(text, strict=True).kind == 'picked' else '(holds)'


def _finding_state(runs, entry):
    """What the last runs (`cache.read_runs`, one per slot) said of a known entry's finding."""
    if not runs:
        return 'no run recorded'
    names = {(line['kind'], line['name']) for run in runs for line in run['lines']}
    if ('known fixed?', f'known.{entry.id}') in names:
        return 'not found in the last run (known fixed?)'
    return 'found in the last run' if any(name == entry.finding for _, name in names) else 'not reported in the last run'


def show_catalog(cfg, query, full=False):
    """`show rules`: every rule of .flowguard/rules.toml (its text, its source and whether it holds now, the intent
    declarations that cite it), every entry of .flowguard/known.toml (act, why, ask, fix, its sites resolved on the
    map, its finding and what the last run said of it, its source), then the input problems of both files; `show
    rule.<id>` and `show known.<id>` one entry. Exit 1 when an input problem is listed (or the entry is missing)."""
    from .differences import display
    from .sources import KNOWN, RULES, catalog, catalog_authority, citing, known_sites, parse, shared_archive
    found = catalog(cfg)
    resolved, unresolved = [], []
    if found.known:                     # only a known entry's sites need the map
        with closing(build(cfg.root, roots=cfg.roots)) as graph:
            resolved, unresolved = known_sites(graph, found.known.values())
    sites = {entry.id: entry for entry in resolved}
    problems = [*found.issues, *unresolved]
    archive, cited, runs = shared_archive(cfg.root), citing(cfg), cache.read_runs(cfg)
    table, _, wanted = query.partition('.')
    rules = [rule for rule in found.rules.values() if query == 'rules' or table == 'rule' and rule.id == wanted]
    entries = [entry for entry in found.known.values() if query == 'rules' or table == 'known' and entry.id == wanted]
    if query != 'rules':     # the entry's own problem, and its file's (an entry of an invalid file is not read)
        problems = [issue for issue in problems if issue.subject in (query, RULES if table == 'rule' else KNOWN)]
    cited_words = [parse(item.source, strict=True) for item in [*rules, *entries] if item.source]
    archive.read([source.rids[0] for source in cited_words if source.kind in ('request', 'picked')])  # one listing
    lines = [f'FlowGuard rules: {len(found.rules)} in {RULES}, {len(found.known)} known in {KNOWN}, '
             f'{len(problems)} input problems'] if query == 'rules' else []
    for rule in rules:
        valid, reason = catalog_authority(parse(rule.source, strict=True), cfg, archive)
        lines.append(f'rule.{rule.id}: {rule.text}')
        lines.append(f'    source: {rule.source} ' + (_holds(rule.source) if valid else f'(does not hold: {reason})'))
        lines.extend(f'    cited by {place}' for place in cited.get(rule.id, ()))
    for entry in entries:
        act = (f'ask, asked on {entry.asked}' if entry.asked else 'ask, not asked yet') if entry.act == 'ask' else entry.act
        lines.append(f'known.{entry.id}: act {act}')
        lines.extend(f'    {key}: {getattr(entry, key)}' for key in ('why', 'ask', 'fix') if getattr(entry, key))
        for site in entry.sites:
            lines.append(f'    site {site}' + ('' if entry.id in sites else ' (see the input problem below)'))
        if entry.finding:
            lines.append(f'    finding {entry.finding}: {_finding_state(runs, entry)}')
        if entry.source:
            valid, reason = catalog_authority(parse(entry.source, strict=True), cfg, archive)
            lines.append(f'    source: {entry.source} ' + (_holds(entry.source) if valid else f'(does not hold: {reason})'))
    for issue in problems:
        _, (place,), what, step = issue.parts[0]
        lines.append(f'input {issue.name}: {place} {what} -> {step}')
    if query != 'rules' and not rules and not entries and not problems:
        lines.append(f'{query} is not in {RULES if table == "rule" else KNOWN}: python -m flowguard show rules lists every entry')
        display('\n'.join(lines))
        return 1
    display('\n'.join(lines))
    return int(bool(problems))


def _named(symbol, query, spellings):
    """How `symbol` (a site's symbol, an agreement's field or NAME, a finding's subject, an anchor's name) names the
    casefolded `query`: 'exact' when it is the query or a member of it in any spelling the map gives it
    (`owners.field_spellings`: `ProjectRequest.status` names `ProjectRequest.status`, `project_requests.status`,
    `ProjectRequest` and `project_requests`; `ProjectMember.*` names every field of `ProjectMember`), 'part' when
    only its last dotted part is the query (`capacityService.updateCalendarEntry` for `updatecalendarentry`), else ''.
    Names compare casefolded, as the facts branch of `show` ranks them."""
    names = {name.casefold() for name in spellings.get(symbol.casefold(), ())} or {symbol.casefold()}
    if any(name == query or name.startswith(query + '.') or name.endswith('.*') and query.startswith(name[:-1])
           and '.' not in query[len(name) - 1:] for name in names):
        return 'exact'
    return 'part' if any('.' in name and name.rpartition('.')[2] == query for name in names) else ''


FINDINGS_SHOWN = 5          # the last run's lines the first block of `show` lists without --full


KNOWN_ADD = 'python -m flowguard known add '
RECORDING_RUN = 'python -m flowguard check --static --all'      # the run whose last lines `known add` reads every finding of


def _structure_line(cfg, issue):
    """A `structure:` line of `show NAME`: a finding's text and its step; when a known.toml entry names the finding,
    the step that entry gives it, as the block's known line says (`known.role-abbreviations: left as it is on purpose;
    ...`), not the step that would record one (H3-2). Show computes the finding now, and `known add` reads the
    finding from the last run, which an ordinary run leaves without an old finding (R99): a step that records one
    first names the run that reports it (pt-smoke-5: `after python -m flowguard check --static --all, python -m
    flowguard known add labels:... --act leave --why TEXT records that`)."""
    from .signals import _known_step
    from .sources import catalog
    def step(entry):
        if entry.act == 'fix':          # the block's fix step adds `as this change does`: show is no change
            return 'marked to fix when its code changes'
        return KNOWN_WORDS['ignore'] if entry.act == 'ignore' else _known_step(entry)
    naming = [entry for entry in catalog(cfg).known.values() if entry.finding == issue.name]
    if not naming:
        return f'structure: {issue.text} -> ' + issue.step.replace(KNOWN_ADD, f'after {RECORDING_RUN}, {KNOWN_ADD}')
    return f'structure: {issue.text} -> ' + '; '.join(f'known.{entry.id}: {step(entry)}' for entry in naming)


def _known_line(entry):
    """A known.toml entry as `show` lists it: the brief's line with the command that prints the whole entry."""
    return _brief_line(_known_brief(entry), tail=f' (python -m flowguard show known.{entry.id})')


def _concerning(cfg, data, graph, index, query, *, path, node=None, anchored=(), symbol=None, also=(), full=False,
                hidden=None, described=()):
    """The first lines of `show NAME` and `show PATH` (`path` is the query's file or folder when it names one, else
    None; `node` the map node of a site query `path:symbol`, `symbol` the symbol of one that names no node, compared
    in its place; `also` a rule's anchors, whose known entries its view lists too), the ids of the intent rules
    among them and the ids of the known entries among them.

    A site query whose symbol names no node answers only for that file and symbol (K2-0): a site, an agreement's
    function or a last run's place counts only in that file, and a name written without a file (a field, a finding's
    subject, an anchor's name, a why or ask) only when that file declares the symbol (`_declares`: the Prisma schema
    of `schema.prisma:PspElement.hierarchyLevel`), never a function of that name in another file
    (`absence.service.ts:create` lists nothing of `project.service.ts:create`). An agreement with a comment in that
    file concerns the query whenever it names the symbol as its field, a partner or a `same` copy's NAME, each of its
    lines listed (Z-0: `show demand.service.ts:Demand.projectId` lists the together agreement written there, `show
    calendar-iso.ts:ISO_WEEKS_IN_YEAR` the three `same ISO_WEEKS_IN_YEAR` copies), and so do an intent rule anchored
    on such a `same` agreement and a known entry with a site in that file whose finding names the symbol
    (`known.iso-weeks`, `same:ISO_WEEKS_IN_YEAR`).

    First the `.flowguard/known.toml` entries that concern the query, in the brief's order and words (`_known_order`,
    `_known_brief`), each with the command that prints it whole: an entry concerns it when one of its sites names it,
    when its finding does (the name after the family, `same:ISO_WEEKS_IN_YEAR`) or, for a PATH query, when its source
    quotes a document in that file or folder. A site `path:symbol` names the query when it is the query, its symbol
    names it (`_named`), its path and symbol are those of the query's map node (`module:qual`, a class's methods too)
    or, for a PATH query, its path is that file or lies under that folder. An entry named only through the last dotted
    part of a site or its finding says which, besides the brief's words: `known.raw-sql (site backend/src/services/
    employee.service.ts:employeeService.findAll): ...`. After those, the entries whose why or ask holds the query
    as a whole token, case and spelling as the production code declares it: an exact `Model.field` or `table.column`
    (`owners.model_known`, in each spelling of a Prisma field), a constant a file other than a test file declares, or
    for a PATH query the path as written (a path under a folder too). The sites are read as written, not resolved on
    the map. Right after the entries the lines of `described`: the texts whose about marker names the query, its file
    or a folder holding it (`docs.described_by`, a module's from `docs.module_lines`).

    Then the intent rules (the static scan's) whose homes or anchors name it, `rule ID: decides`; a rule's home
    `module:Class.field` is read as the site of its module's file, an anchor by its name or by the site of a source
    anchor of that name (its file and target function). Then the `.flowguard/rules.toml` rules those cite and, for a
    PATH query, those whose source quotes a document there, in file order. Then the flowguard comment agreements
    (`owners.agreement_heads`) as `show_lines` spells them: for a PATH query those written there, otherwise those
    that name the query as a field or partner, as a writers or except= function, or as the function they mark, one
    named only through the last dotted part of such a function with that function (`(site path:symbol)`); the
    agreements of the names in `anchored` (the query's own, which the anchor or rule view lists whole) are left out.
    Last the lines of the last run (`cache.read_last`) placed at the query's function (its node, the functions its
    name names) or file, one each with its kind, at most FINDINGS_SHOWN without `full` and a count of the others
    (that count is appended to the list `hidden` when one is given); a known line of that run is left out, its entry
    being listed by its own words."""
    from flowguard.map.common import is_test_file
    from .owners import agreement_heads, field_spellings, model_known
    from .signals import family_of
    from .sources import RULE_FORM, catalog, parse
    node = node or (graph.node(graph.canonical(query) or query) if ':' in query else None)
    folder = path                   # `_repository_path`: './app/' is 'app'
    name = symbol or query          # what a site's symbol, a finding or an agreement's name is compared with
    folded, spellings = name.casefold(), field_spellings(graph)
    every = (folded, *(item.casefold() for item in also))
    at = query.rpartition(':')[0] if symbol is not None else None     # the file of a site query that names no node
    bare = at is None or _declares(graph, at, symbol)        # does a name written without a file name its symbol?

    def under(file):
        return folder is not None and (folder == '.' or file == folder or file.startswith(folder + '/'))

    def named(symbol, names=(folded,)):
        if folder is not None:
            return ''
        found = {_named(symbol, item, spellings) for item in names}
        return 'exact' if 'exact' in found else 'part' if 'part' in found else ''

    def unplaced(symbol, names=(folded,), placed=False):  # a name written without a file: a field, a finding's
        return named(symbol, names) if bare or placed else ''   # subject, an anchor; `placed`: written in the file

    def in_file(site):          # a site of the queried file of a site query that names no node
        return at is not None and (site.rpartition(':')[0] if ':' in site else site) == at

    def site_names(site, names=(folded,)):
        spot, colon, symbol = site.rpartition(':')
        file = spot if colon else site          # a document site is its path alone
        if site == query or under(file):
            return 'exact'
        if node is not None and colon and file == node['file'] and (symbol == node['qual'] or symbol.startswith(
                node['qual'] + '.') or symbol.rpartition('.')[2] == node['qual']):
            return 'exact'
        return named(symbol, names) if colon and at in (None, file) else ''

    def quoted(source):         # a known entry's or a rules.toml rule's source quotes a document of the PATH query
        cited = parse(source, strict=True) if folder is not None and source else None
        return cited is not None and cited.kind == 'doc' and under(posixpath.normpath(cited.path))

    # What a why or ask must hold as a whole token, in the case the code declares it (H2-0: an everyday word that only
    # a test declares as a constant is no exact name; `STATUS` is not `status`).
    if folder is not None:
        texts, after = ([folder] if folder != '.' else []), (r'(?![\w$-]|\.[\w$])' if (cfg.root / folder).is_dir()
                                                              else r'(?![\w$/-]|\.[\w$])')
    elif FIELD_QUERY.fullmatch(name) and model_known(graph, name.partition('.')[0]):
        texts, after = sorted(spellings.get(folded) or {name}), r'(?![\w$]|\.[\w$])'
    else:
        declared = graph.con.execute("SELECT file FROM node WHERE kind = 'const' AND qual = ?", (name,)).fetchall()
        texts, after = ([name] if any(not is_test_file(file) for (file,) in declared) else []), r'(?![\w$]|\.[\w$])'
    token = re.compile('|'.join(r'(?<![\w$./-])' + re.escape(text) + after for text in texts)) if texts and bare else None
    found = catalog(cfg)
    by_site, by_text, through = [], [], {}
    for entry in found.known.values():
        sites = {site: site_names(site, every) for site in entry.sites}
        family = family_of(entry.finding) if entry.finding else ''
        finding = unplaced(entry.finding[len(family) + 1:], every, any(map(in_file, entry.sites))) if family else ''
        if 'exact' in sites.values() or finding == 'exact' or quoted(entry.source):
            by_site.append(entry)
        elif 'part' in sites.values() or finding == 'part':
            parts = [site for site, how in sites.items() if how == 'part']
            through[entry.id] = '; '.join([*([f'site{"s" * (len(parts) > 1)} {", ".join(parts)}'] if parts else []),
                                           *([f'finding {entry.finding}'] if finding == 'part' else [])])
            by_site.append(entry)
        elif token is not None and any(token.search(text or '') for text in (entry.why, entry.ask)):
            by_text.append(entry)

    def known_line(entry):          # the brief's line; one named through a last part says which site, kept whole
        line = _known_line(entry)
        head, _, rest = line.partition(': ')
        return f'{head} ({through[entry.id]}): {rest}' if entry.id in through else line
    listed = [*_known_order(by_site), *_known_order(by_text)]
    lines = [known_line(entry) for entry in listed] + list(described)
    modules = dict(graph.con.execute('SELECT module, path FROM file'))
    heads = agreement_heads(graph, index)
    # The `same NAME` agreements with a copy in the queried file: each copy is a line of one agreement, and a rule
    # anchored on it concerns the query too.
    copied = {agreement for agreement, line, file, _ in heads if line.startswith('same ') and in_file(file)}
    rules, cited = [], set()
    for rid, item in data['summary']['rules'].items():
        names = [name for name in item.get('anchors', ()) if not name.startswith('unresolved:')]   # states have none
        homes = [modules[module] + ':' + symbol
                 for module, _, symbol in (home.partition(':') for home in item['homes']) if module in modules]
        anchored_at = [f'{anchor.file}:{anchor.target.partition(":")[2]}' for anchor in _anchor_targets(index, names, graph)]
        if any(unplaced(name, placed=name in copied) for name in names) \
                or any(map(site_names, [*item['homes'], *homes, *anchored_at])):
            rules.append(rid)
            match = RULE_FORM.fullmatch(item['source'].strip()) if isinstance(item['source'], str) else None
            if match:
                cited.add(match[1])
    lines += [f'rule {rid}: {data["summary"]["rules"][rid]["decides"]}' for rid in rules]
    lines += [_brief_line(f'rule.{rule.id}: {rule.text}', tail=f' (python -m flowguard show rule.{rule.id})')
              for rule in found.rules.values() if rule.id in cited or quoted(rule.source)]
    for agreement, line, file, names in heads:
        if agreement in anchored:
            continue
        placed = in_file(file) or line.startswith('same ') and agreement in copied
        how = {item: site_names(item) if ':' in item else unplaced(item, placed=placed) for item in names}
        if under(file) if folder is not None else 'exact' in how.values():
            lines.append(line)
        elif folder is None and 'part' in how.values():     # a generic name (`show create`): which function it is
            parts = [item for item, said in how.items() if said == 'part']
            lines.append(f'{line} (site{"s" * (len(parts) > 1)} {", ".join(parts)})')
    if folder is None or (cfg.root / folder).is_file():         # a function or a file; never a folder
        lines += _last_run_lines(cfg, graph, query, name, site_names, held=node is None and folder is None and at is None,
                                 full=full, hidden=hidden)
    return list(dict.fromkeys(lines)), set(rules), {entry.id for entry in listed}


def _declares(graph, file, symbol):
    """Does `file` declare `symbol`, as a site query `file:symbol` that names no function spells it: a node of that
    file with that qual that is no function (a constant, class, interface, enum, Prisma model or SQL table), a model,
    `@@map` table, field or `@map` column of a Prisma schema there (`PspElement.hierarchyLevel` in `schema.prisma`),
    or a table or column a SQL file there creates or adds? A function is named by its site, which `_concerning`
    compares in that file (`absence.service.ts:create` of the method `absenceService.create`)."""
    if graph.con.execute("SELECT 1 FROM node WHERE file = ? AND kind NOT IN ('module', 'function', 'method', 'test') "
                         'AND qual = ? LIMIT 1', (file, symbol)).fetchone():
        return True
    owner, dot, member = symbol.casefold().rpartition('.')
    owner, member = (owner, member) if dot else (member, None)
    for schema in graph.schemas():
        if schema['file'] != file:
            continue
        if schema['kind'] == 'prisma':
            for item in schema.get('models', ()):
                if owner in (item['name'].casefold(), (item.get('table') or '').casefold()) and (member is None or any(
                        member in (field['name'].casefold(), (field.get('column') or '').casefold())
                        for field in item.get('fields', ()))):
                    return True
            continue
        for item in [*schema.get('tables', ()), *schema.get('changes', ())]:
            if (item.get('name') or item.get('table') or '').casefold() == owner and (member is None or any(
                    column['name'].casefold() == member for column in [*(item.get('columns') or ()), *item.get('add', ())])):
                return True
    return False


def _last_run_lines(cfg, graph, query, name, site_names, *, held, full, hidden=None):
    """The lines of the last run (`cache.read_last`) placed at the function of a `show` query or at its file, as
    `_concerning` lists them last: `before (last run): together Project.leaderId at backend/src/services/project.
    service.ts:create was broken at task start -> leave it unless your task is about it`. A line is placed there when
    one of its places names the query (`site_names`: the node's file and symbol, the file, a symbol the name names)
    or, with `held`, its member is a function that the query `object.method` names (`_held_methods`). None without
    a recorded run. The number of lines left out without `full` is appended to `hidden` when it is a list. The lines
    come from every slot's last run (`cache.read_runs`), a line two slots gave once."""
    runs = cache.read_runs(cfg)
    if not runs:
        return []
    methods = _held_methods(graph, name) if held else set()
    found = list({(line['kind'], line['text'], line['step']): line for run in runs for line in run['lines']
                  if not line['name'].startswith('known.')
                  and (line['function'] in methods or any(site_names(place) for place in line['places']))}.values())
    shown = found if full else found[:FINDINGS_SHOWN]
    lines = [f'{line["kind"]} (last run): {line["text"]}' + (f' -> {line["step"]}' if line['step'] else '') for line in shown]
    if len(shown) < len(found):
        if hidden is not None:
            hidden.append(len(found) - len(shown))
        lines.append(f'... {len(found) - len(shown)} more lines of the last run there: '
                     f'python -m flowguard show {_spelled(query)} --full lists them all')
    return lines


FIELD_QUERY = re.compile(r'[A-Za-z_]\w*\.[A-Za-z_]\w*')     # Model.field or table.column
AT_START = ' at the task start'     # a `show Model.field` line of the task-start code that no function has now, for a
                                    # field no code writes now


def _write_line(row, mark=''):
    """A `show Model.field` line of one write (`MapHandle.writes` row), with what `_test_marks` says of its test file
    (`mark`) as a `test ... reaches a writer` line says it."""
    where = f'{row["file"]}:{row["line"]}' + (f' (call line {row["call_line"]})' if row['call_line'] != row['line'] else '')
    unclear = f'; unclear: {row["reason"]}' if row['unclear'] else ''
    return (f'writes {row["model"] or row["table"]}.{row["field"] or row["db_column"]} {where} {row["function"]} '
            f'({row["kind"]}{unclear})' + (f' ({mark})' if mark else ''))


def _write_lines(cfg, rows):
    """`_write_line` of each write, a write in a test file that the project's test scope leaves out, or in a folder its
    scripts run as a suite that reaches real databases and services, marked so (gate-5: Planning Tool's `show
    Assignment.fteShare` listed `writes ... backend/tests/integration/dashboard.routes.test.ts:146 ... ensureFixtures
    (create)` among the production writers, while only the `test ... reaches a writer` lines, which the default view
    cuts, said that PT's agents may not run that suite)."""
    from flowguard.map.common import is_test_file
    marks = _test_marks(cfg, sorted({row['file'] for row in rows if is_test_file(row['file'])}))
    return [_write_line(row, marks.get(row['file'], '')) for row in rows]


def _unknown_model(graph, query):
    """The `not on the map` line of `show Model.field` for a model the map does not know (`owners.model_known`), or
    one whose Prisma models, SQL tables and TS types it knows have no such field (`owners.field_absent`), then the
    model's field nearest to a misspelt one (`owners.nearest_field`: `CapacityCalendarEntry.valeu` names
    `CapacityCalendarEntry.value`): zod keys of that name and the fields of other Prisma models are not facts about
    this field; '' otherwise, and for an unknown model whose field name the map does not know either."""
    from .owners import field_absent, model_known, nearest_field, zod_bounds
    model, _, field = query.partition('.')
    known = model_known(graph, model)
    absent = field_absent(graph, model, field) if known else []
    if known and not absent:
        return ''
    models = sorted({item['name'] for schema in graph.schemas() if schema['kind'] == 'prisma'
                     for item in schema.get('models', ()) if any(column['name'] == field for column in item.get('fields', ()))})
    keys = zod_bounds(graph, field)
    if not absent and not models and not keys:
        return ''
    if absent:
        tables = sum(item.startswith('database table ') for item in absent)
        noun = 'column' if tables == len(absent) else 'field or column' if tables else 'field'
        what = (', '.join(absent[:-1]) + ' and ' + absent[-1] if len(absent) > 1 else absent[0]) + \
            f' {"have" if len(absent) > 1 else "has"} no {noun} {field}'
        if near := nearest_field(graph, model, field):        # a misspelt field: the one of that model it may mean
            what += f', the nearest {noun + " " if noun != "field or column" else ""}is {model}.{near}'
    else:
        what = f'no Prisma model, database table, TS type or class {model}'
    objects = len({(file, schema) for file, schema, *_ in keys})
    return (f'not on the map: {what}'
            + (f'; the zod keys {field} of {objects} schema object{"s" if objects != 1 else ""} are not listed, as a key matches by its name alone' if keys else '')
            + (f'; Prisma models with a field {field}: {", ".join(models)}' if models else ''))


NODE_NAMES = 3          # the fields a node view names and the callers it names without --full
NODE_VIEWS = 3          # the functions an exact name names that `show NAME` prints the node view of


def _described_places(graph, query, name, *, site, target, file):
    """([(file, names, node)], models) of what a `show NAME` names, for the texts that describe it
    (`docs.described_by`): the functions, methods and constants, a site query's node or, naming none, its file and
    symbol (no node); a map id's node; else each one whose qual or declared name (`anchors._declared_name`,
    `service.save`) is the query or, for a name without a dot, ends in it, when there are at most NODE_VIEWS of them (a
    generic name's texts would be every file's); for a `Model.field` or `table.column`, each Prisma schema that
    declares the field it names (`owners.mapped_fields`) with that field's spelling, no node. `models` holds the
    Prisma models whose `generate fields` region describes the query: the model of each such field, or the model the
    query names."""
    from .anchors import _declared_name
    from .owners import mapped_fields
    from ..structure import store
    fields = {spelled: (model, field) for spelled, (model, field) in mapped_fields(graph, name).items()}
    declaring = [(schema['file'], f'{item["name"]}.{entry["name"]}') for schema in graph.schemas() if schema['kind'] == 'prisma'
                 for item in schema.get('models', ()) for entry in item.get('fields', ())
                 if fields.get(f'{item["name"]}.{entry["name"]}') == (item['name'], entry['name'])]
    if site and target is None:
        here = [spelled for path, spelled in declaring if path == file]
        return [(file, {name, *here}, None)], {spelled.partition('.')[0] for spelled in here}
    if fields:
        return [(path, {spelled}, None) for path, spelled in declaring], {model for model, _ in fields.values()}
    models = {name} if any(item['name'] == name for schema in graph.schemas() if schema['kind'] == 'prisma'
                          for item in schema.get('models', ())) else set()
    node = target or graph.node(graph.canonical(query) or query)
    rows = graph.con.execute("SELECT id, file, qual, kind, raw FROM node WHERE id = ? AND kind IN ('function', 'method', 'const')",
                             (node['id'],)).fetchall() if node else graph.con.execute(
        "SELECT id, file, qual, kind, raw FROM node WHERE (short = ? OR short LIKE ?) AND kind IN ('function', 'method', 'const')",
        (query.rpartition('.')[2], query.rpartition('.')[2] + '@%')).fetchall()     # `save@12`: a name used twice
    found = []
    for ident, path, qual, kind, raw in rows:      # a constant is declared by its qual
        names = {qual, qual if kind == 'const' else _declared_name(path, qual, store.unpack(raw) if raw else {})}
        if node or query in names or '.' not in query and any(item.rpartition('.')[2] == query for item in names):
            found.append((path, names, ident))
    return (found if len(found) <= NODE_VIEWS else []), models


def _node_lines(graph, node, header, *, full, again, writes=None, callers=None):
    """The node view of one map function, method or class (`show module:qual`, `show path:symbol`, and each of the
    few functions an exact name names): `header file:line`, its signature, its doc when it has one, then the fields
    it writes (the `MapHandle.writes` rows of it and of the functions nested in it, `Model.field`, an unclear write as
    `Model (fields not visible)`) and, for a function or method, the functions that call it through a call the map
    resolved (`MapHandle.resolved_calls`: an import or a lexical binding, a member call on an imported object whose
    module defines that member, the store's links; a JS/TS call matched by a name alone is not counted), production
    code before test files, and for a method the functions that read it as an attribute of its class
    (`MapHandle.field_reads`: a property's readers, through self, cls, an annotated name or a declared field; a
    property no such function reads says so): each a count and the first NODE_NAMES, all of
    them with `full`, and the view that lists more (`show MODEL.FIELD`, `show AGAIN --full` for the query `again`).
    `writes` and `callers` are `MapHandle.writes()` and the callers map of `resolved_calls()` when the caller holds
    them already."""
    from ..structure import store
    from .owners import _counted
    ident = node['id']
    lines = [f'{header} {node["file"]}:{node["line"]}', node['sig'], *([node['doc']] if node['doc'] else [])]
    rows = [row for row in (graph.writes() if writes is None else writes)
            if row['node'] == ident or row['node'].startswith(ident + '.')]
    fields = sorted({f'{row["model"] or row["table"]} (fields not visible)' if row['unclear']
                     else f'{row["model"] or row["table"]}.{row["field"] or row["db_column"]}' for row in rows})
    rest = f'python -m flowguard show {_spelled(again)} --full names them all'

    def named(items):
        shown = items if full else items[:NODE_NAMES]
        return ', '.join(shown) + (f' and {len(items) - len(shown)} more' if len(shown) < len(items) else '')
    if fields:
        lines.append(f'writes {_counted(len(fields), "field")}: {named(fields)} (python -m flowguard show MODEL.FIELD '
                     'lists the writes and reads of one' + (f'; {rest}' if not full and len(fields) > NODE_NAMES else '') + ')')
    if node['kind'] in ('function', 'method'):
        up = graph.resolved_calls()[1] if callers is None else callers
        found = [caller for caller in up.get(ident, ()) if caller != ident and not caller.startswith(ident + '.')]
        places = {row[0]: row[1:] for row in graph.con.execute(
            f"SELECT id, qual, file, line FROM node WHERE id IN ({','.join('?' * len(found))})", found)} if found else {}
        tests = {path for (path,) in graph.con.execute('SELECT path FROM file WHERE is_test = 1')} if found else set()
        found.sort(key=lambda caller: (caller in places and places[caller][1] in tests, caller))
        spelled = [f'{places[caller][0]} ({places[caller][1]}:{places[caller][2]})' if caller in places else caller
                   for caller in found]
        if not found:
            lines.append('called by no function through a call the map resolved (a call matched by its name alone is not counted)')
        else:
            lines.append(f'called by {_counted(len(found), "function")} through '
                         f'{"a resolved call" if len(found) == 1 else "resolved calls"}: {named(spelled)}'
                         + (f' ({rest})' if not full and len(found) > NODE_NAMES else ''))
    if node['kind'] == 'method' and node['cls']:
        # A property is read, not called (PEMEL23-5b: `show PaneHandle.highlighted` said only `called by no function`):
        # the functions that read a method as an attribute of its class, as `MapHandle.field_reads` types a read.
        first = {}
        for row in graph.field_reads(node['qual']):
            if row['field'] != '*' and row['owner'] == node['module']:
                first.setdefault(row['function'], (row['file'], row['line']))
        raw = graph.con.execute('SELECT raw FROM node WHERE id = ?', (ident,)).fetchone()
        getter = bool(raw and raw[0] and store.unpack(raw[0]).get('property'))
        tests = {path for (path,) in graph.con.execute('SELECT path FROM file WHERE is_test = 1')} if first else set()
        readers = sorted(first, key=lambda function: (first[function][0] in tests, function))
        if readers:
            lines.append(f'read as an attribute by {_counted(len(readers), "function")} (untyped reads not counted): '
                         + named([f'{function} ({first[function][0]}:{first[function][1]})' for function in readers])
                         + (f' ({rest})' if not full and len(readers) > NODE_NAMES else ''))
        elif getter:
            lines.append('read as an attribute by no function through self, cls, an annotated name or a declared field '
                         '(untyped reads not counted)')
    return lines


def _map_knows(graph, name, written=None):
    """Does the map hold anything named `name`, so that `show NAME` prints no `not on the map` line for it: a node of
    that qual or name (a function, method, class, interface, constant, enum, Prisma model, SQL table or test), a JS/TS
    module-level object or option list of that name (`const cookieOptions = {...}`, which gives no table line unless the
    labels check reads it), an object literal or class whose methods the map holds (`owners.method_holders`: `export
    const capacityService = {`), a JS/TS module-level declaration of that name whatever its value (`const TPL = ...`
    holding a template string, which the reader does not read: no const line, Z-9), a model the map knows
    (`owners.model_known`), a column of a SQL table as the columns check reads them (`sql.describe`), a write of that
    model, table or field (`MapHandle.writes`; `written` when the caller read them already), a Python read of that
    class field (`MapHandle.field_reads`) or a zod object key of that name (`owners.zod_bounds`)? A dotted name is
    asked only for its node, its writes and its reads: its model and field have their own `not on the map` line
    (`_unknown_model`), and a Prisma field its own line."""
    from ..structure.readers.registry import ECMA, language_for
    from ..structure.readers.sql import describe
    from .owners import method_holders, model_known, zod_bounds
    if graph.con.execute("SELECT 1 FROM node WHERE kind != 'module' AND (qual = ? OR short = ?) LIMIT 1", (name, name)).fetchone():
        return True
    if any(row['name'] == name for _, _, facts in graph._kinds('const_tables', 'option_lists')
           for rows in facts.values() for row in rows) or method_holders(graph, name):
        return True
    if any(row['target'] == name and row['form'] == 'declarator' and ':' not in row['node']
           for path, _, facts in graph._kinds('assignments') if language_for(path) in ECMA
           for row in facts.get('assignments', ())):
        return True
    if '.' in name or model_known(graph, name):
        return '.' not in name or bool(graph.writes(name) if written is None else written) or bool(graph.field_reads(name))
    for description in describe(graph.schemas()):
        if any(name.casefold() in columns for columns in [*(table['columns'] or {} for table in description['tables'].values()),
                                                         *description['altered'].values()]):
            return True
    return bool(graph.writes(name) if written is None else written) or bool(zod_bounds(graph, name))


def _repository_path(cfg, query):
    """The query as a path of the repository when it names a file or a folder there, normalized (`./app/` is `app`,
    `.\\app` too), else None: a file at the repository's root (`fees.py`) is a PATH query as well."""
    path = posixpath.normpath(query.replace('\\', '/'))
    if path.startswith(('/', '../')) or path == '..' or re.match(r'[A-Za-z]:', path):
        return None
    return path if (cfg.root / path).is_dir() or (cfg.root / path).is_file() else None


def _held_methods(graph, name):
    """The ids of the functions an `object.method` query names by holder and name, as `MapHandle.call_index` keys
    them (the node's holder, else its qual's prefix; its name, else its qual's last part), compared casefolded: `show
    employeeService.update` ranks `employee.service.ts:update` first among the methods named update. A member the
    reader names only through its holder (`member`: an arrow function or function expression that is a property or
    a class field, `getAll: (params) => ...`, whose node is `<anonymous@33,11>`) is named by that member's name, so
    each member a holder line counts is found (`owners.method_holders`). So is a member whose name a module function
    of that file has too, which the map names by its line (`sliceDateRangeByMonth@490`: gate-0, `show
    capacityService.sliceDateRangeByMonth`, as a generated functions region writes it, was not on the map)."""
    from flowguard.structure import store
    holder, dot, method = name.casefold().rpartition('.')
    if not dot or not holder or '.' in holder or not method:
        return set()
    held = set()
    for ident, qual, raw in graph.con.execute(
            "SELECT id, qual, raw FROM node WHERE kind IN ('function', 'method') AND (short = ? COLLATE NOCASE "
            "OR short LIKE ? OR qual LIKE '%<anonymous@%')", (method, method + '@%')):
        data = store.unpack(raw) if raw else {}
        own = data.get('holder') or (qual.rpartition('.')[0] if '.' in qual else '')
        spelled = data.get('member') or data.get('name') or qual.rpartition('.')[2]
        if own.casefold() == holder and spelled.casefold() == method:
            held.add(ident)
    return held


def _stored_text(name, raw):
    """The text of stored owner-archive bytes (a request, a choice's reply or its offer) as `show` prints it, read as
    the archive's checks read them (`document_text`: UTF-8, or UTF-16 by its byte order mark); bytes that are no such
    text raise ValueError with the decoder's own text, nothing is replaced."""
    decoded, problem = document_text(name, raw)
    if problem:
        raise ValueError(problem)
    return decoded[0]


def _choice_view(cfg, identifier, row):
    """`show R106` of a choice: the owner's reply (or that he selected with no words of his own), the options the agent
    offered as the agent's words, and the option text each pick is."""
    def block(name, raw):
        text = _stored_text(name, raw)
        return text if text.endswith(('\n', '\r')) else text + '\n'
    said = ("the owner selected, with no words of his own:" if row['reply'] == 'selected' else "the owner's reply:")
    return (f'OWNER {identifier} chose among options the agent offered\n{said}\n'
            + block(f'.flowguard/requests/{identifier}.md', read_request_bytes(cfg.root, identifier))
            + f"options the agent offered (the agent's words, not the owner's) {row['offer']}:\n"
            + block(row['offer'], read_offer_bytes(cfg.root, identifier))
            + '\n'.join(f'picked: {json.dumps(text, ensure_ascii=False)}' for text in row['picked']))


def show(cfg, query=None, *, full=False, last=False):
    if last:
        if query:
            raise ValueError('show --last takes no NAME: python -m flowguard show --last')
        return show_last(cfg, full)
    from .sources import catalog, catalog_files
    if query and (query == 'rules' or query.startswith(('rule.', 'known.'))) and catalog_files(cfg):
        return show_catalog(cfg, query, full)      # without a catalog file these names are looked up as before
    if query:
        request = cfg.root / '.flowguard/requests' / (query + '.md')
        if request.is_file():
            row = owner_word(cfg.root, query)
            if row and not row.get('edited') and not row.get('invalid'):
                if row.get('retired'):
                    print(f'RETIRED {query}: not the owner\'s words; original bytes remain in the archive.')
                    return 0
                if row['kind'] == 'choice':
                    print(_choice_view(cfg, query, row))
                    return 0
                print(f'OWNER {query}\n' + _stored_text(f'.flowguard/requests/{query}.md', request.read_bytes()))
                return 0
            raise ValueError(f'{query}: stored original is not verified')
    data = cache.read(cfg)
    rules = data['summary']['rules']
    if not query:
        raise ValueError('show needs a rule, function, request id or words')
    if query not in rules and catalog_files(cfg) and query in catalog(cfg).known:
        return show_catalog(cfg, 'known.' + query, full)        # a known entry's bare id: `show known.<id>`
    errors = [e for e in data['summary']['errors']
              if (query in rules and e['file'] == rules[query]['file'])
              or query in (cfg.root / e['file']).read_text(encoding='utf-8-sig')]
    if errors:
        for error in errors:
            print(f'red load {error["file"]}:{error["line"]}: {error["msg"]} -> fix the intent file')
        return 1
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        from .anchors import collect
        index = collect(graph)
        notice = _map_notice(graph)
        if query in rules:          # a rule's or a flow's view begins with what concerns its id and its anchors, its
            anchored = rules[query].get('anchors', ())      # own line and the copies of its anchors (listed below) left out
            concerning = [line for line in _concerning(cfg, data, graph, index, query, path=None, anchored=set(anchored),
                                                       also=[name for name in anchored if name != query], full=full)[0]
                          if line != f'rule {query}: {rules[query]["decides"]}']
        if query in rules and rules[query].get('kind') == 'flow':
            from .debug import show_observation
            from .differences import display
            item = rules[query]
            _, pointers = _source_pointers(index, item.get('anchors', ()), graph, full=full)
            view = show_observation(cfg, query, index, cache.observations(cfg).get('events', ()))
            display('\n'.join([f'FLOW {query}', *([notice] if notice else []), *concerning, f'source: {item["source"]}',
                               f'{item["file"]}:{item["line"]}', *pointers, *view['lines']]))
            return int(view['status'] == 'red')
        if query in rules:
            item = rules[query]
            lines = [f'RULE {query}: {item["decides"]}', item.get('doc', '') if full else '', f'source: {item["source"]}',
                     f'{item["file"]}:{item["line"]}; {item.get("rows", 0)} literal rows']
            lines[1:1] = [*([notice] if notice else []), *concerning]
            for home in item.get('homes', []) if item.get('kind') == 'rule' else []:
                lines.append('home ' + home)
                if full:
                    lines.extend(f'  site L{s["line"]}: {s["field"]} {s["op"]} {s["const"]}' for s in graph.sites(home))
            for result in data['results'].get(query, {}).get('items', {}).values():
                lines.extend(result.get('red', []) + result.get('grey', []) + (result.get('info', []) if full else []))
            if item.get('kind') == 'rule':
                lines.extend(_silent_lines(cfg, index, query, full))
            anchors, pointers = _source_pointers(index, item.get('anchors', []), graph, full=full)
            lines.extend(pointers)
            if item.get('flows'):lines.append('via flow ' + ', '.join(dict.fromkeys(item['flows'])))
            lines.extend('navigation unknown: ' + value for value in item.get('navigation_unknown', []))
            lines.extend(_copy_pointers(graph, index, anchors, item.get('homes', []),
                         list(data['results'].get(query, {}).get('items', {}).values()),
                         item.get('doc', '') + ' ' + item['decides'], full))
            from .deps import Now, stale
            if data['results'].get(query) and (not data['deps'].get(query) or stale(data['deps'][query], Now(cfg, graph))):
                lines.insert(1, 'cached results are stale or unverified -> run check')
            from .differences import display      # copy pointers carry project names: escape what the console cannot show
            display('\n'.join(line for line in lines if line))
            return int(bool(data['summary']['errors']))
        if data['summary']['errors'] and any(query in (cfg.root / e['file']).read_text(encoding='utf-8-sig') for e in data['summary']['errors']):
            for error in data['summary']['errors']:
                print(f'red load {error["file"]}:{error["line"]}: {error["msg"]} -> fix the intent file')
            return 1
        # A file or folder of the repository is a PATH query: the module's lines, and the known sites under it.
        path = _repository_path(cfg, query)
        # A site as known.toml writes it, `path:symbol` with a file of the repository: the symbol's facts, or the node
        # branch for the function it names (one position of that file, as `sources.site_resolver` reads it).
        spot, colon, name = query.rpartition(':')
        site = bool(path is None and colon and _repository_path(cfg, spot) == spot and (cfg.root / spot).is_file())
        target = None
        if site:
            from .anchors import _agreement_positions
            module = graph.con.execute('SELECT module FROM file WHERE path = ?', (spot,)).fetchone()
            found = _agreement_positions(graph, {spot: module[0]})[module[0]].get(name, ()) if module else ()
            target = graph.node(found[0]) if len(found) == 1 else None
        else:
            name = query
        anchors, pointers = _source_pointers(index, [query], graph, full=full)
        hidden = []         # the number of last-run lines `concerning` leaves out without --full
        from .docs import described_by, module_lines
        # A module's view and the texts that describe it (R98); a function's, method's or constant's texts (5.0 gate).
        module = module_lines(graph, path + '/' if (cfg.root / path).is_dir() else path) if path is not None else None
        described = module[1] if module else described_by(graph, *_described_places(graph, query, name, site=site,
                                                                                     target=target, file=spot))
        concerning, listed, known = _concerning(cfg, data, graph, index, query, path=path, node=target,
                                                anchored={query} if anchors else (),
                                                symbol=name if site and target is None else None, full=full, hidden=hidden,
                                                described=described)
        from .differences import display        # a known entry's words may hold what the console cannot show
        # Every view begins with its header, the map notice and what concerns the query (gate-6: an anchor's view; gate-4:
        # a site query, a map id and a module or document view began with their node or module line, the Map line in
        # their middle).
        opening = [f'show {query}', *([notice] if notice else []), *concerning]
        if anchors:
            display('\n'.join(opening))
            print('\n'.join(pointers))
            from .owners import agreement_writes, declaration_lines, show_lines
            if owned := show_lines(cfg, graph, index, query):     # writes outside its writers, look-alikes
                display('\n'.join(owned))
            if FIELD_QUERY.fullmatch(query):        # what the map read about the field and who writes it, as the facts
                agreed = agreement_writes(cfg, graph, index, query)      # branch says; a write listed above once only
                facts = [*filter(None, [_unknown_model(graph, query)]), *declaration_lines(graph, query),
                         *_write_lines(cfg, [row for row in graph.writes(query)
                                             if (row['file'], row['line'], row['function'], row['kind']) not in agreed])]
                facts = [line for line in dict.fromkeys(facts) if line not in owned]
                if facts:
                    display('\n'.join(facts if full else _limit(
                        facts, cfg.screen_lines, f'python -m flowguard show {_spelled(query)} --full lists them all')))
            from .debug import show_observation
            from types import SimpleNamespace
            model = SimpleNamespace(rules={rid: SimpleNamespace(id=rid, anchors=value.get('anchors', ()))
                                         for rid, value in rules.items()})
            view = show_observation(cfg, query, index, cache.observations(cfg).get('events', ()), model=model)
            if view['lines']:
                print('\n'.join(view['lines']))
            # An agreement (`same`, `same NAME ref`, writers, together) is checked by the same-name comparison or
            # statically, by no model: no `not referenced` line for it (gate-6).
            unused = set(_unmodelled(index, data['summary'], root=cfg.root)) & {
                a.name for a in anchors if a.kind not in AGREEMENT_KINDS}
            if unused:print('info: not referenced by a current model: ' + ', '.join(sorted(unused)))
            from .differences import display
            if copies := _copy_pointers(graph, index, anchors, [], [], query, full):
                display('\n'.join(copies))
            return 0
        if module is not None:          # R98: a module's contracts and connections, the texts right after its entries
            display('\n'.join([*opening, *module[0], *module[2]]))
            return 0
        node = target or (None if site else graph.node(graph.canonical(query) or query))
        if node:
            display('\n'.join([*opening, *_node_lines(graph, node, query, full=full, again=query)]))
            # A function an anchor marks is bound already: its reason not to search names no binding step.
            found = graph.search_homes(node['id'], k=None,
                                       bound=any(anchor.target == node['id'] for anchor in index.entries))
            if not found['searched']:
                print(found['reason'])
            if candidates := _candidate_lines(found, full, 'candidate '):
                print('\n'.join(candidates))
            return 0
        words = tokens(name)
        from .owners import _counted, declaration_lines, field_models_line, holder_lines, model_lines   # read first
        read = declaration_lines(graph, name)
        if not FIELD_QUERY.fullmatch(name):          # a model or table, a field of Prisma models, a method holder
            read += [*model_lines(graph, name), *filter(None, [field_models_line(graph, name)]),
                     *holder_lines(graph, name, full=full)]
        ranked = [(3000 - order, line) for order, line in enumerate(read)]
        knows = bool(read)          # the map read the name itself: names that share a word with it wait for --full
        named = False               # a rule or an import names it too: no `not on the map` line
        unknown, written = '', None
        if FIELD_QUERY.fullmatch(name):      # Model.field or table.column: who writes it
            written = graph.writes(name)
            # In the map's order (file, then line as a number), unclear ones last: each write ranks a little below the
            # one before it, all within (1998, 2000].
            ranked.extend((2000 - bool(row['unclear']) - order / len(written), line)
                          for order, (row, line) in enumerate(zip(written, _write_lines(cfg, written))))
            unknown = _unknown_model(graph, name)
            from . import health, owners as checks       # several files write it and nobody owns it: say so first
            change = checks.Change(cfg, graph, None)
            for issue in health.writers(change, index, written, listed=True).issues:
                ranked.append((2001, _structure_line(cfg, issue)))
            ranked.extend((2001, line) for line in health.co_written(change, name, index))
            ranked.extend((1998 - order, line) for order, line in enumerate(
                checks.field_lines(graph, name, written, lambda files: _test_marks(cfg, files))))
            if not written:     # no code writes it now (PEMEL23-6c): what the task-start code wrote and read of it that
                then = checks.Change(cfg, graph, checks.baseline(cfg))      # no function does now
                if then.baseline:
                    # a read compares by its function and kind, never its line: one only moved, or a field nothing
                    # writes (a @property, an attribute only read) on an unchanged tree, is listed once, as it reads now
                    reads = {(row['node'], row['method']) for row in graph.field_reads(name)}
                    old = [*(line + AT_START for line in _write_lines(cfg, then.baseline_writes(name))),
                           *dict.fromkeys(checks.python_read_line(row, name, AT_START)
                                          for row in then.baseline_field_reads(name)
                                          if (row['node'], row['method']) not in reads)]
                    ranked.extend((1500 - order / len(old), line) for order, line in enumerate(old))
        if any(row['name'] == name for row in graph.labels_read(graph.label_rows())):  # the family the block reports
            from . import health, owners as checks
            for issue in health.labels(checks.Change(cfg, graph, None), name).issues:
                ranked.append((2001, _structure_line(cfg, issue)))
        for rid, rule in rules.items():
            score = 1000 if name.casefold() in {rid.casefold(), rule['decides'].casefold()} else 0
            named = named or bool(score)
            score += 4 * len(words & tokens(rule['decides'] + ' ' + rule.get('doc', '')))
            if score and rid not in listed:        # a rule that concerns the query is listed first already
                ranked.append((score, f'rule {rid}: {rule["decides"]} {rule.get("doc", "")}'))
        if re.search(r'\s', name.strip()):        # words: the known entries whose why or ask shares one, after the names
            for entry in catalog(cfg).known.values():
                if entry.id not in known and (shared := words & tokens(f'{entry.why} {entry.ask}')):
                    ranked.append((900 + len(shared), _known_line(entry)))
        owners = graph.outline(('function', 'method', 'class'))
        held = _held_methods(graph, name)
        decided = {}
        for ident, field, identity in graph.con.execute('SELECT node, field, identity FROM site'):
            decided.setdefault(ident, []).append((field or '') + ' ' + (identity or ''))
        exact = []          # the functions, methods and classes the name or `object.method` names
        for ident, item in owners.items():
            last = item['qual'].rsplit('.', 1)[-1]          # a member the map names by its line, `name@490`, is name
            names = {ident.casefold(), item['qual'].casefold(), last.casefold(), re.sub(r'@\d+$', '', last).casefold()}
            score = 1000 if name.casefold() in names or ident in held else 0
            # Only an owner whose text can hold a query word is split into words (may_share is exact).
            if any(may_share(words, text) for text in decided.get(ident, ())):
                sites = graph.sites(ident)
                score += 2 * len(words & tokens(' '.join(s['field'] + ' ' + (s['identity'] or '') for s in sites)))
            if may_share(words, ident + ' ' + item['doc']):
                score += len(words & tokens(ident + ' ' + item['doc']))
            if score >= 1000:
                exact.append((score, ident))
            elif score:
                ranked.append((score, f'{ident} {item["file"]}:{item["line"]}'))
        exact.sort(key=lambda row: (-row[0], row[1]))
        views = []          # one function or a few: each one's node view, before the word matches
        if len(exact) <= NODE_VIEWS:
            writes, callers = (graph.writes(), graph.resolved_calls()[1]) if exact else (None, None)
            for _, ident in exact:
                views += _node_lines(graph, graph.node(ident), ident, full=full, again=ident, writes=writes, callers=callers)
        else:
            ranked.extend((score, f'{ident} {owners[ident]["file"]}:{owners[ident]["line"]}') for score, ident in exact)
        for ident, aliases in graph.import_aliases(name).items():       # the names an import binds to an owner
            item = graph.node(ident)
            ranked.extend((1000, f'{alias} -> {ident} {item["file"]}:{item["line"]}') for alias in aliases)
            named = True
        knows = knows or bool(exact)
        if not knows and not named and not unknown and not re.search(r'\s', name.strip()) and not _map_knows(graph, name, written):
            unknown = f'not on the map: no function, class, type, constant, enum, Prisma model or field, or SQL table or column is named {name}'
        ranked.sort(key=lambda row: (-row[0], row[1]))
        matches = [line for score, line in ranked if score < 1000]
        head = [*opening, *([unknown] if unknown else []), *views,
                *(line for score, line in ranked if score >= 1000)]
        complete = [*head, *([f'word matches: the {_counted(len(matches), "line")} below only share'
                              f'{"s" if len(matches) == 1 else ""} a word with {query}'] if matches else []), *matches]
        from .differences import display          # a structure line carries Chinese text: escape what the console cannot show
        if full:
            display('\n'.join(complete))
            return 0
        # Without --full the screen holds `screen_lines` lines: when the map knows the name itself, names that merely
        # share a word with it wait for --full. The last line counts what --full adds below the last line shown, the
        # last run's lines that its own count line counts aside (unless that line is cut away too).
        view = head if knows else complete
        if len(view) > cfg.screen_lines or (knows and matches):
            kept = view[:cfg.screen_lines - 1]
            marker = len(opening) - 1           # the index of the last run's count line, when it has one
            adds = len(complete) - len(kept) + (hidden[0] - 1 if hidden and marker >= len(kept) else 0)
            sharing = f', {len(matches)} of them only share{"s" if len(matches) == 1 else ""} a word with {query}' \
                if matches and len(head) >= len(kept) else ''
            view = [*kept, f'... {adds} more lines{sharing}: python -m flowguard show {_spelled(query)} --full lists them all']
        display('\n'.join(view))
    return 0


def write_docs(cfg):
    """`python -m flowguard docs`: rewrite every generated region of the repository's Markdown files from the map
    (`docs.rewrite`); one line per region it rewrote or could not write. 1 when one could not be written. The session
    brief's count of regions out of date (`cache.structure_summary`, which a check saves) becomes what is left: the
    regions it could not write; without a saved summary nothing is saved."""
    from . import docs
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        done = docs.rewrite(graph)
        saved = cache.structure_summary(cfg)
        if saved is not None:
            left = sum(bool(problem) for *_, problem in done)
            with graph.con:
                cache.save_structure(graph.con, dict(saved, regions=left, unwritable=left))
    for document, line, kind, argument, problem in done:
        print(f'{document}:{line} generate {kind} {argument}: ' + (problem or 'rewritten') if kind else problem)
    if not done:
        print('no generated region is out of date')
    return int(any(problem for *_, problem in done))


def add_known_entry(cfg, options):
    """`python -m flowguard known add`: one entry appended to .flowguard/known.toml (`sources.add_known`), and what
    it holds."""
    from .sources import KNOWN, add_known
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        entry = add_known(cfg, graph, '' if options.finding == '-' else options.finding, act=options.act, why=options.why,
                          ask=options.ask, identifier=options.identifier, sites=options.site)
    print(f'known.{entry.id} added to {KNOWN}: act {entry.act}, sites {", ".join(entry.sites)}'
          + (f', finding {entry.finding}' if entry.finding else ''))
    if entry.act != 'ask':
        print('the next run lists it as loosened, as every new entry whose act is not ask')
    return 0


class _Own:
    """What `check` finds itself, beside the deliveries of its pytest batch (`signals.delivery`): findings
    (`health.Issue`) of the families that need no map, lines already of their kind, the families and finding names
    its own checks judged in full (`ran`: a known entry naming one that is no longer found is `known fixed?`), and
    its batch's pytest exit code, seconds (FlowGuard's own share of them is in the batch's report), output file and
    the end of that output."""

    def __init__(self):
        self.issues, self.lines, self.code, self.seconds, self.output, self.tail = [], [], 0, 0.0, None, []
        self.ran = set()        # what check's own checks judged in full (`signals.deliver`'s `ran`)
        self.touched = set()    # the members of its own findings this change touches (`signals.deliver`)

    def red(self, family, name, subject, what, step, *, places=(), files=(), detail=()):
        from .signals import finding
        self.issues.append(finding(family, name, subject, [what], step, places=places, files=[file for file in files if file],
                                   detail=detail))

    def history(self, messages):
        """The reds of the intent rules' history (`history.check`): a rule or row removed without its reason."""
        for message in messages:
            what, step = _step_of(message, 'show the rule and correct its source, binding or regression rows')
            subject, colon, rest = what.partition(': ')
            self.red('input', f'history:{what}', subject if colon else 'history', rest if colon else what, step)

    def delivery(self):
        from .signals import delivery
        return delivery(self.issues, self.lines, touched_functions=self.touched, ran=self.ran)


def _step_of(message, step):
    """(what, step) of a message that may carry its own step after its last ' -> ', in ASCII; else `step`."""
    from .signals import ascii_text, split_step
    what, own = split_step(ascii_text(message))
    return what, own or step


def _index_findings(index):
    """The findings of the flowguard comments, in the words of a pytest session: a malformed comment is red (it
    disables checks, D4), and a source file that does not parse is not compared, only that file."""
    from .signals import ascii_text, finding, not_compared, split_step
    reds, unparsed = {}, {}
    for issue in index.issues:
        place = f'{issue.file}:{issue.line}' if issue.line else issue.file
        if issue.level == 'red':
            what, step = split_step(ascii_text(issue.message))
            entry = reds.setdefault(f'comment:{place}:{issue.code}', dict(place=place, file=issue.file, whats=[],
                                                                          step=step or 'correct this flowguard comment'))
            entry['whats'].append(what)
        elif issue.code == 'source-syntax':
            unparsed.setdefault(issue.file, []).append('cannot be parsed: ' + ascii_text(issue.message))
    return ([finding('input', name, f'comment {entry["place"]}', entry['whats'], entry['step'], places=(entry['place'],),
                     files=(entry['file'],)) for name, entry in reds.items()],
            [not_compared(file, reasons, places=(file,)) for file, reasons in unparsed.items()])


def _ledger_findings(result):
    """The fallback ledger's findings, in the words of a pytest session, as (issues, ran): each red one line, the entry
    to copy in its detail (`ledger check` prints it as well); each section 5.0 removed one red input line
    (`ledger.section_removed`); and the ledger family in `ran` when a ledger was compared with the map in full, none
    of it unverified, as a pytest session names it (a known entry naming a ledger finding no longer found is then
    `known fixed?`)."""
    from .ledger import LEDGER, section_removed
    from .signals import LEDGER_STEP, ascii_text, finding
    issues = [finding('ledger', f'ledger:{red.text}', 'ledger', [ascii_text(red.text)], LEDGER_STEP,
                      places=(LEDGER, *re.findall(r'(?<![\w./-])[\w./-]+\.[A-Za-z]\w*:\d+', red.text)), files=(LEDGER,),
                      detail=list(red.fix)) for red in result.red]
    for name in result.sections:
        subject, what, step = section_removed(name)
        issues.append(finding('input', f'ledger-section:{name}', subject, [what], step, places=(LEDGER,), files=(LEDGER,)))
    return issues, {'ledger'} if result.present and not result.grey else set()


def _legacy_lines(listed):
    """`--all`: a before line for each kind of handler body of the ledger's unreviewed legacy handlers that do not
    hand their error on (`ledger.open_legacy`, its heading and next step in each line's detail)."""
    from .ledger import LEDGER
    from .signals import BEFORE_STEP, Line, ascii_text
    if not listed:
        return []
    heading, *groups, step = (ascii_text(line).strip() for line in listed)
    return [Line('before', 'ledger:legacy:' + group.partition(':')[0], '', 'ledger legacy: ' + group.replace(' handlers:', ' handlers: ', 1),
                 BEFORE_STEP, (LEDGER,), (heading, step)) for group in groups]


def _declared_at(model, identifier):
    """`file:line` of the declaration `identifier` (as a pytest session names it), '' when the model has none."""
    declaration = model.rules.get(identifier) or model.states.get(identifier) or model.flows.get(identifier)
    return f'{model.file_of[identifier]}:{declaration.line}' if declaration is not None and identifier in model.file_of else ''


def _site(rule, target):
    """The place of a rule home's function as the 4.3 lines spell one, `path:qualified name`; its target without an
    anchor."""
    home = next((home for home in rule.homes if home.target == target and getattr(home, 'anchor', None)), None)
    return f'{home.anchor.file}:{home.anchor.qual}' if home is not None else target


def _rule_finding(model, rid, values):
    """The one `rule:ID` finding of an intent rule's red results, in the words a pytest session gives the same results
    (`plugin.Observations._rule_red`): the rule's own reds first, then the code's at its homes (the smallest input
    first), its first step from `signals.rule_steps` over every red, every step and the owner's words in its detail."""
    from .signals import finding, rule_steps
    from .sources import parse, source_text
    rule = model.rules[rid]
    where = _declared_at(model, rid)
    sites = [_site(rule, home.target) for home in rule.homes if not hasattr(home, 'scenario')]
    whats, said, at, places = [], [], [], []
    for value in values:
        place = _site(rule, value['target']) if value.get('target') else None
        for message in value['red'] or ['reported red']:
            what = said_text = str(message)
            counted = re.match(r'(?:\S+: )?(\d+ of \d+ (?:cells|rows) disagree); smallest (.+? -> rule .+?)(?: \((row L\d+)\))?$', what)
            if counted and place:       # the engine's count of one home: its smallest input first, as the code's red reads
                what = f'{counted[2]} at {place} ({counted[1]}' + (f', {counted[3]})' if counted[3] else ')')
            whats.append(what)
            said.append(said_text)
            places.extend(item for item in (where, place, *sites) if item)
            if place and place not in at:
                at.append(place)
    whats.sort(key=lambda text: not text.startswith(('self: ', 'row ', 'conflict ', 'gap in ')))
    steps = [step.rstrip('; ') for step in rule_steps(rid, at or sites or [rid + ' binding'], where, said)]
    source = parse(rule.source)
    return finding('rule', f'rule:{rid}', f'rule {rid}', whats, steps[0] if steps else '', places=tuple(dict.fromkeys(places)),
                   files=[model.file_of[rid]] if rid in model.file_of else [],
                   detail=[*steps, f'{rid} source: {source_text(source, model.cfg)}'])


def _cache_findings(cfg, model, data):
    """check's own findings from the intent results it ran or reused (`cache.read`), in the words of a pytest
    session, as (issues, lines): intent load errors, an unfinished verification or collection and a removed rule
    or row (red, D3, D4); each red intent rule (`_rule_finding`) or other declaration; a cited source that
    already failed at the baseline (before); a failed test of pytest's scope (red); and each grey intent item, or a
    rule without results, not compared."""
    from .deps import test_scope
    from .health import LINES_ONLY, Issue
    from .plugin import FLOW_STEP
    from .signals import BEFORE_STEP, ascii_text, finding, load_step, not_compared
    own = _Own()
    summary, attempt = data['summary'], data.get('attempt') or {}
    for error in summary['errors']:
        place = f'{error["file"]}:{error["line"]}'
        own.red('input', f'load:{place}', f'load {place}', *load_step(error['msg']), places=(place,), files=(error['file'],))
    order = {item: number for number, item in enumerate(model.declared_items())}
    def values(rid):
        items = data['results'].get(rid, {}).get('items', {})
        return [dict(value, item=item) for item, value in sorted(items.items(), key=lambda pair: order.get(pair[0], len(order)))]
    for value in values(None):              # an intent file that does not load: its `load` item
        for message in value.get('red') or ['reported red']:
            found = re.match(r'(.+?):(\d+): (.*)', str(message), re.S)
            place = f'{found[1]}:{found[2]}' if found else value['item'].partition('::')[0]
            own.red('input', f'load:{place}', f'load {place}', *load_step(found[3] if found else message), places=(place,),
                    files=(place.partition(':')[0],))
    collected = attempt and (attempt.get('sentinel') is not None or attempt.get('collected') or attempt.get('selected')
                             or attempt.get('deferred'))
    if collected and (attempt.get('missing') or attempt.get('sentinel') != 'ok'):
        own.red('input', 'collection:intent', 'collection', 'a declared intent item or the sentinel was not collected',
                'run python -m flowguard init and collect the complete intent path')
    for message in attempt.get('errors', []):
        own.red('input', f'verification:{message}', 'verification', *_step_of(message, 'correct the reported error and run check'))
    own.history(data.get('history', []))
    kinds = {'flow': 'flow', 'states': 'states'}
    for rid, item in summary['rules'].items():
        if item.get('superseded_by'):
            continue
        results = values(rid)
        if not results:
            own.lines.append(not_compared(rid, ['no results yet']))
        reds = [value for value in results if value.get('red') or value.get('verdict') == 'red']
        if reds and rid in model.rules:
            own.issues.append(_rule_finding(model, rid, reds))
        others = {}
        for value in [] if rid in model.rules else reds:
            kind = kinds.get(value.get('kind'), 'rule')
            where = _declared_at(model, rid)
            entry = others.setdefault((kind, value.get('target') or ''), dict(whats=[], where=where, step=FLOW_STEP.format(id=rid)
                                      if kind == 'flow' else f'correct the code or {kind} {rid} at {where}'))
            entry['whats'] += [ascii_text(message) for message in value.get('red') or ['reported red']]
        for (kind, target), entry in others.items():
            own.issues.append(finding('flow' if kind == 'flow' else 'rule', f'{kind}:{rid}', f'{kind} {rid}', entry['whats'],
                                      entry['step'], function=target, places=(entry['where'],) if entry['where'] else ()))
        for value in results:
            if value.get('before'):         # a cited source that already failed at the baseline (`engine._judged`)
                where = _declared_at(model, rid) or value['item'].partition('::')[0]
                reasons = tuple(dict.fromkeys(ascii_text(reason) for reason in value['before']))
                subject = f'source {rid}'
                own.issues.append(Issue(f'source:{rid}', LINES_ONLY, subject, f'{subject}: {reasons[0]}', BEFORE_STEP,
                                        files=frozenset({where.partition(':')[0]}), family='source', subject=subject,
                                        parts=(('', where, reasons[0], BEFORE_STEP),), detail=reasons))
            if value.get('verdict') == 'grey':
                own.lines.append(not_compared(value['item'].partition('::')[2], [str(reason) for reason in value.get('grey', ())]
                                              or ['unverified']))
    in_scope = test_scope(cfg)
    for test, value in data.get('tests', {}).items():
        file = test.partition('::')[0]
        if value.get('outcome') == 'failed' and in_scope(file):
            reason = value.get('reason') or value.get('phase')
            own.red('test', f'test:{test}', f'test {test}', f'{reason} (outside the project)' if value.get('kind') == 'env' else reason,
                    'rerun this test after correcting the cause', places=(file,), files=(file,))
    return own.issues, own.lines


def _judged_names(model, data):
    """The finding names of the declarations every intent result of which check ran or reused judged (none
    unverified), as a pytest session names them (`plugin.Observations._judged_names`): `rule:ID` (`flow:ID`, ...),
    and `source:ID` when every result passed, which none does whose source fails. A known entry naming one of them
    that is no longer found is `known fixed?`."""
    from .plugin import ITEM_KINDS
    judged = set()
    for rid, group in data['results'].items():
        results = list(group.get('items', {}).values())
        if rid is None or not results or any(value.get('verdict') == 'grey' for value in results):
            continue
        judged.add(f'rule:{rid}' if rid in model.rules else f'{ITEM_KINDS.get(results[0].get("kind"), "rule")}:{rid}')
        if all(value.get('verdict') == 'ok' for value in results):
            judged.add(f'source:{rid}')
    return judged


def _same_name_findings(cfg, index, compared, touched, baseline):
    """D24 and design 4.5: the same-name copies check's pytest batch did not compare (`compared`: the names it did).
    Where their current code differs (`differences._compare_pairs`), the copies are compared as a pytest session
    compares them (`plugin.compare_copies`): sealed, now and at `baseline`, on the inputs where they differ. A pair
    that differs where it agreed at the baseline (or a copy the baseline lacks; without a baseline every copy) is red,
    one that already differed there is old: `before` or `known` where this change touches a copy's file (the member
    is touched then, as in a pytest session), else no line. Copies of another signature are red where they are this
    change's (copies that take different parameters in the words `signals.copies_parameters` gives them in a pytest
    session), and what could not be compared is not compared. (issues, lines, ran, touched functions): `ran` names
    the groups whose every pair was compared on every input made for it and agreed (`same:NAME`), whose known entry
    is then `known fixed?`, as in pytest."""
    import math
    from ..map.common import git_renames, read_source
    from .differences import _compare_pairs
    from .plugin import _parse_baseline, compare_copies
    from .runtime import Runtime, _module_at, sealed
    from .signals import copies_parameters, finding, not_compared
    issues, lines, ran, members = [], [], set(), set()
    # without a baseline the copies still run sealed now; nothing is read at a baseline
    runtime = Runtime(cfg.root, baseline) if baseline else Runtime(cfg.root, previous={})
    renamed = git_renames(cfg.root, baseline) if baseline else {}
    texts = {}
    def source(point, old=False):
        key = point['file'], old
        if key not in texts:
            texts[key] = runtime._source(renamed.get(key[0], key[0])) if old else read_source(cfg.root / key[0])
        return texts[key]
    def run(point, sample, old=False):
        text = source(point, old)
        file, module = point['file'], point['module']
        if old and file in renamed:         # at the baseline a moved file imported from its old place
            file, module = renamed[file], _module_at(renamed[file], file, module)
        if old and text and (why := _parse_baseline(text)[1]):       # in the words a pytest session gives
            return dict(status='unavailable', reason=f'{file} {why}')
        return sealed(text, point['qual'], sample['args'], sample['kwargs'], runtime.imports(file, module, old)) \
            if text is not None else dict(status='unavailable', reason='no baseline source')
    def json_input(row):
        """A sealed comparison's input holds JSON values only: no Decimal, date or non-finite number."""
        return all(value is None or type(value) in (bool, int, str) or type(value) is float and math.isfinite(value)
                   for value in row.values())
    for name in sorted({anchor.name for anchor in index.entries if anchor.kind == 'sensor'} - compared):
        # A reference (`same NAME ref`) is the function its same-name copies are compared with.
        copies = sorted((anchor for anchor in index.named(name, 'sensor') if anchor.source_role == 'production'),
                        key=lambda anchor: not anchor.owner)
        if len(copies) < 2:
            continue
        result = _compare_pairs(cfg.root, [(copies[0], other) for other in copies[1:]], witnesses=True)
        files = {anchor.file for anchor in copies}
        new = bool(files & touched) or baseline is None
        differ = result['witnesses']
        if differ:
            points = [dict(anchor=anchor, target=anchor.target, file=anchor.file, module=anchor.module, qual=anchor.qual,
                           name=anchor.name, kind='sensor', node=None) for anchor in copies]
            lines_of = {anchor.target: f'{anchor.file}:{anchor.target_line}' for anchor in copies}
            found = compare_copies(name, points, [row for row in differ if json_input(row)], source, run, lines_of.get,
                                   no_inputs='the inputs where its copies differ are not JSON')
            if found.issue is not None:
                issues.append(found.issue)
                if found.issue.files & touched:
                    members.update(part[0] for part in found.issue.parts)
            grey = [reason.removeprefix(name + ': ') for reason in found.grey]
            if found.issue is None and not grey:
                grey = ['its copies differ on their current code, not in the closed environment']
            if grey:
                lines.append(not_compared(name, grey))
        # what kept a pair from being compared; a pair shown to differ was compared
        differing = {reason for item in result['items'] if item['changes'] for reason in item['reasons']}
        reasons = [reason.removeprefix(name + ': ') for reason in result['reasons'] if reason not in differing]
        if result['status'] == 'red' and not result['changes']:
            if new and len({tuple(p.name for p in anchor.parameters) for anchor in copies}) > 1:
                # copies that take different parameters, in the words of a pytest session (`compare_copies`)
                text, step = copies_parameters([(f'{anchor.file}:{anchor.qual}', '(' + ', '.join(p.source for p in anchor.parameters) + ')')
                                                for anchor in copies])
                issues.append(finding('same', f'same:{name}', f'same {name}', [text], step, function='signature',
                                      places=tuple(f'{anchor.file}:{anchor.qual}' for anchor in copies), files=files))
            elif new:   # copies whose declared inputs or outputs no longer match: nothing compares them
                issues.append(finding('same', f'same:{name}', f'same {name}', reasons, 'declare the same inputs and outputs on every copy',
                                      function='signature', places=tuple(f'{anchor.file}:{anchor.qual}' for anchor in copies),
                                      files=files))
        elif reasons:
            lines.append(not_compared(name, reasons))
        if (not result['changes'] and result['selected'] == len(copies) - 1 and result['total']
                and result['checked'] == result['total'] and not result['unknown']):
            # every pair compared on every input made for it, and they agree (as a pytest session's sealed
            # comparison): a known entry naming their disagreement may be fixed, also where the inputs, not a
            # proof, leave a not compared line
            ran.add(f'same:{name}')
    return issues, lines, ran, members


def _uncovered_alone(issues, deliveries, index):
    """`issues` without the members of a `changed-alone:NAME` finding that a `same:NAME` finding of the run already
    covers (D30: one red per agreement member): a changed copy registered under NAME whose copies the same-name
    comparison found to disagree. A changed function NAME does not register stays, and so does the finding where no
    same-name finding of its name was made."""
    from dataclasses import replace
    covered = {issue.name.partition(':')[2] for part in deliveries for issue in part['issues'] if issue.family == 'same'}
    kept = []
    for issue in issues:
        name = issue.name.partition(':')[2]
        if issue.family == 'changed-alone' and name in covered:
            copies = {anchor.target for anchor in index.named(name, 'sensor')}
            parts = tuple(part for part in issue.parts if part[0] not in copies)
            if not parts:
                continue
            issue = replace(issue, parts=parts, fresh=issue.fresh & {part[0] for part in parts})
        kept.append(issue)
    return kept


def check(cfg, *, everything=False, deep=False, base=None):
    """Run the one ordinary pytest route; source validation executes no code. The 4.3 block at the end: the findings
    of its pytest batch (`plugin.collect_signals().deliveries`), its own (the intent results, the comments, the
    same-name copies no batch compared) and the static ones with copy discovery (`_owner_findings`), through one
    `signals.collect`, one line per (kind, name, function); `everything` (`--all`) lists every old finding and has no
    budget. The first line counts FlowGuard's own seconds: its batch's
    and check's own work besides pytest; the lines are kept for `show --last` with that first line, and a place is
    named by the shortest end of its path that no other file of the repository has. Exit 1 for a red line only.
    Without `base` the first check of a task records HEAD as its baseline when none is recorded; a recorded one
    stays, as in pytest (`cache.task_start`)."""
    started, timing = time.time(), time.perf_counter()
    from . import signals
    from .differences import _source_index
    from .plugin import collect_signals
    start = cache.task_start(cfg, record=True) if base is None else (base, 'base', None)
    own = _Own()
    with collect_signals(everything=everything) as reports:
        _check(cfg, everything=everything, deep=deep, base=base, reports=reports, own=own)
    with ExitStack() as maps:       # the map is read only for a removed 4.2 spelling (`_source_index`)
        index = _source_index(cfg.root, lambda: maps.enter_context(closing(build(cfg.root, roots=cfg.roots))))
    issues, lines = _index_findings(index)
    own.issues += issues
    own.lines += lines
    found = _owner_findings(cfg, everything=everything, base=base,
                            static=reports.static.get((cfg.root, base, everything)))
    deliveries = list(reports.deliveries)
    touched = set(found.touched_files).union(*(part['touched_files'] for part in deliveries))
    # A same-name group the batch compared (a changed copy it observed, or copies it found differing) is its own.
    compared = {item['name'] for part in reports for item in part['items'] if item.get('file')}
    compared |= {issue.name.partition(':')[2] for part in deliveries for issue in part['issues'] if issue.family == 'same'}
    compared |= {name.partition(':')[2] for part in deliveries for name in part['ran'] if name.startswith('same:')}
    from .owners import baseline as owner_baseline
    issues, lines, ran, members = _same_name_findings(cfg, index, compared, touched, owner_baseline(cfg, base))
    own.issues += issues
    own.lines += lines
    own.ran |= ran
    own.touched |= members
    found.issues = _uncovered_alone(found.issues, [*deliveries, own.delivery()], index)
    lines, ignored = signals.collect([*deliveries, own.delivery()], found, everything=everything)
    if own.code and not any(line.kind == 'red' for line in lines):
        # pytest failed where no finding says why (an internal or usage error, an interruption): never a quiet pass.
        own.red('test', 'test:pytest', 'pytest', f'exit {own.code}', f'read {own.output} and correct the reported error',
                detail=own.tail)
        lines, ignored = signals.collect([*deliveries, own.delivery()], found, everything=everything)
    batch = next((part for part in reports if part.get('baseline')), None)
    baseline, kind, ahead = (batch['baseline'], batch['baseline_kind'], batch['baseline_ahead']) if batch else start
    files = git_files(cfg.root)         # the repository's files, which no shortened path of the block may name
    seconds = time.perf_counter() - timing - own.seconds + sum(part['seconds'] for part in reports)
    # An explicit --base is named as it was given (`since --base release/task-start`), as check --static names it,
    # also where the pytest batch resolved it to its commit.
    heading = signals.title(lines, baseline=baseline if base is None else base, kind=kind, ahead=ahead, option='--base',
                            seconds=seconds)
    cache.keep_last(cfg, signals.last_run(lines, ignored, scope=cache.REPO, run='check', stamp=started, baseline=baseline,
                                          kind=kind, title=heading, seconds=seconds))
    status = int(any(line.kind == 'red' for line in lines))
    _show_signals(signals.render_block(lines, title=heading, everything=everything, files=files), status)
    return status


def _show_signals(text, status):
    """The block on the console, as at the end of an ordinary test run."""
    if text:
        try:
            from .differences import display
            display(text)
        except BrokenPipeError:
            raise           # A closed consumer is quiet at the command entry, not an unavailable output.
        except (OSError, ValueError) as error:
            try:
                print(f'FlowGuard output unavailable: {type(error).__name__}; verification status {status}', file=sys.stderr)
            except (OSError, ValueError):
                pass


def static_check(cfg, *, everything=False, base=None):
    """`check --static`: the map checks alone, without pytest: the fallback ledger, owner writes and pairs,
    values outside declared sets, new spellings, unchanged copies, deletes that leave children, missing columns,
    the catalog and touched structure problems (`owners.static_findings`), with the flowguard comments, as the 4.3
    block (`signals.collect`, `render_block`). Only what this change adds is red; `everything` (`--all`) lists every
    old finding as before and has no budget. The first line always
    prints, with the whole command's seconds; the lines are kept for `show --last`, and a place is named by the
    shortest end of its path that no other file of the repository has. With FLOWGUARD_LINES set (the static test
    inside a vitest run, `NPM_CHECK`) the payload `show --last` keeps (`signals.last_run`) and the parts of its first
    line (`title_parts`, the keywords of `signals.title`) go to that JSON file for the vitest report's block, nothing
    to stdout, and nothing to `show --last`: the vitest report keeps them in its package's slot, and a vitest run killed
    before it reports leaves the slot's earlier run, never these lines as a finished `check --static` (5.0 did). Exit
    1 for a red line only. Without `base` the first run of a task records HEAD as its baseline when none is recorded; a
    recorded one stays, as in pytest (`cache.task_start`); the title names it as pytest does."""
    started, timing = time.time(), time.perf_counter()
    from . import anchors, ledger as fallbacks, owners, signals
    start = cache.task_start(cfg, record=True) if base is None else (base, 'base', None)
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        index = anchors.collect(graph)
        found = owners.static_findings(cfg, graph, index, base, everything=everything)
        baseline = owners.baseline(cfg, base)
        result = fallbacks.evaluate(cfg, graph, baseline=baseline) if fallbacks.path(cfg).is_file() \
            else fallbacks.absent(cfg, baseline)
        comments, unparsed = _index_findings(index)
        ledger_reds, ran = _ledger_findings(result)
        legacy = _legacy_lines(fallbacks.open_legacy(cfg, graph)) if everything else []
        lines, ignored = signals.collect([signals.delivery([*comments, *ledger_reds], [*unparsed, *legacy], ran=ran)],
                                         found, everything=everything)
        target = os.environ.get('FLOWGUARD_LINES')       # the static test inside a vitest run (NPM_CHECK)
        files = frozenset() if target else git_files(cfg.root)      # the vitest report prints these lines
        seconds = time.perf_counter() - timing
        parts = dict(baseline=start[0], kind=start[1], ahead=start[2], option='--base')
        heading = signals.title(lines, **parts, seconds=seconds)
        payload = signals.last_run(lines, ignored, scope=cache.REPO, run='check --static', stamp=started, baseline=start[0],
                                   kind=start[1], title=heading, seconds=seconds)
        with graph.con:
            cache.save_structure(graph.con, found.summary)
            if not target:          # inside vitest the vitest report keeps the run, these lines among its own
                cache.save_last(graph.con, payload)
    status = int(any(line.kind == 'red' for line in lines))
    if target:
        # the vitest report reads this file (`vitest.static_lines`): the payload show --last reads, and the parts of
        # its first line (`signals.title`)
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(dict(payload, title_parts=parts), ensure_ascii=False, sort_keys=True), encoding='utf-8')
    else:
        _show_signals(signals.render_block(lines, title=heading, everything=everything, files=files), status)
    return status


def _owner_findings(cfg, *, everything=False, base=None, static=None):
    """Owners, copies and static findings of this change; copy discovery runs only here, in check. `everything`
    (`--all`) adds the before lines of the ledger's open legacy handlers (`_legacy_lines`). Without a baseline
    (outside Git, before the first commit, a recorded start this repository lacks) nothing is new and the old ledger
    is check --all's, but an invalid or unresolvable entry of rules.toml or known.toml is red all the same (D4), as
    in pytest and check --static: these are the only findings then."""
    from . import anchors, owners, sources
    if not owners.baseline(cfg, base) and not everything:
        if not sources.catalog_files(cfg):
            return owners.Findings()
        with closing(build(cfg.root, roots=cfg.roots)) as graph:
            return owners.Findings(issues=sources.input_findings(cfg, lambda: graph))
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        index = anchors.collect(graph)
        found = owners.check_findings(cfg, graph, index, base, everything=everything, static=static)
        if everything:
            from .ledger import open_legacy
            found.lines = [*found.lines, *_legacy_lines(open_legacy(cfg, graph))]
        with graph.con:
            cache.save_structure(graph.con, found.summary)
        return found


def _check_selection(cfg: Config, model: object, data: dict, everything: bool, sentinel: Path, base: str | None = None):
    from flowguard.map.common import git_run
    from . import deps
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        # The commit pytest compares with (its Runtime resolves --flowguard-base the same way), else the task
        # baseline: a source judged against another commit (`baseline:<commit>` of deps.record) is judged again.
        commit = None if base is None else git_run(cfg.root, 'rev-parse', '--verify', base + '^{commit}').stdout.decode().strip()
        now = deps.Now(cfg, graph, baseline=commit)
        selected = set(model.rules) if everything else set(deps.affected(data, model, now))
        flows = {identifier for identifier in [*model.flows, *model.states]
                 if everything or not deps.reusable(data, identifier, now)}
        selected.update(identifier for identifier, rule in model.rules.items() if not {
            model.file_of[identifier] + '::' + name for name in model.items_of(rule)
        } <= data['results'].get(identifier, {}).get('items', {}).keys())
        records = deps.test_dependencies(cfg, graph, now)
        test_scope = deps.test_scope(cfg)
        def ordinary_file(file):
            path = (cfg.root / file).resolve()
            return test_scope(file) and not path.is_relative_to(cfg.intent) and path != sentinel
        ordinary = set()
        for file, record in records.items():
            if not ordinary_file(file):
                continue
            readings = {nodeid: reading for nodeid, reading in data['tests'].items() if nodeid.partition('::')[0] == file}
            full = data['test_collection'].get(file, {})
            if (everything or '<unresolved>' in record or cache.test_signature(record) != data['test_deps'].get(file)
                    or not full or not full['tests'] or not set(full['tests']) <= readings.keys()
                    or any(reading['outcome'] != 'passed' for reading in readings.values())):
                ordinary.add(file)
        # An opaque test may change shared inputs for another test or rule.
        if any('<unresolved>' in record for file, record in records.items() if ordinary_file(file)):
            ordinary.update(file for file in records if ordinary_file(file))
            selected.update(model.rules)
            flows.update([*model.flows, *model.states])
        # A `fields` anchor's rule is checked on the calls its tests reach: rerun the tests that reached
        # it last time, every test while that is unknown.
        for identifier in selected:
            if any(getattr(home, 'anchor', None) and home.anchor.fields for home in model.rules[identifier].homes):
                reached = {test.partition('::')[0] for value in data['results'].get(identifier, {}).get('items', {}).values()
                           for test in value.get('tests', ())}
                ordinary.update(file for file in records if ordinary_file(file) and (file in reached or not reached))
    return selected, flows, ordinary, records


# flowguard: event CHECK_PYTEST(command: list, root: Path, output: Path, stream: bool)
def _run_check_pytest(command: list, root: Path, output: Path, stream: bool):
    """One top-level pytest Session, with the real output retained verbatim."""
    from contextlib import redirect_stdout, redirect_stderr
    from types import SimpleNamespace
    from .config import _INSERTED_PATHS
    from .plugin import _CURRENT
    import pytest
    if _CURRENT is not None and not _CURRENT.closed:
        raise MapError('check needs the top-level test session; it cannot start a nested pytest session')
    output.parent.mkdir(parents=True, exist_ok=True)
    captured = io.StringIO()
    previous_directory = Path.cwd()
    previous_paths, paths = sys.path, list(sys.path)
    owned = set(_INSERTED_PATHS)
    stdout, stderr = sys.stdout, sys.stderr
    class Output:
        def __init__(self, live, saved):
            self.live, self.saved = live, saved
            self.encoding = getattr(live, 'encoding', None) or 'utf-8'
        def write(self, text):
            captured.write(text)
            self.saved.write(text)
            if stream:
                self.live.write(text)
            return len(text)
        def flush(self):
            self.saved.flush()
            if stream:
                self.live.flush()
        def isatty(self):
            return False
    try:
        os.chdir(root)
        with output.open('w', encoding='utf-8', newline='') as saved:
            with redirect_stdout(Output(stdout, saved)), redirect_stderr(Output(stderr, saved)):
                status = int(pytest.main(command))
        return SimpleNamespace(returncode=status, stdout=captured.getvalue(), stderr='')
    finally:
        os.chdir(previous_directory)
        sys.path = previous_paths
        previous_paths[:] = paths
        _INSERTED_PATHS.clear()
        _INSERTED_PATHS.update(owned)


def _check(cfg, *, everything=False, deep=False, base=None, reports=None, own=None):
    """The pytest part of `check`: select the affected rules and tests, run them in one pytest batch (its findings
    reach `reports`, `plugin.collect_signals`) and add check's own findings to `own` (`_Own`): the intent results it
    ran or reused (`_cache_findings`), the history of the intent rules, the ledger when no intent item runs, and an
    unfinished batch; `own.code` is the batch's pytest exit code."""
    import ast
    from . import history
    from .loader import load
    stream_all = everything
    model = load(cfg)
    model.deep = deep
    historical = history.check(cfg, base)
    data = cache.read(cfg)
    retry_incomplete = bool((data.get('attempt') or {}).get('errors'))
    if not model.declared_items() and not everything and not retry_incomplete:
        # No intent item runs, so the ledger the plugin would report is compared here without pytest.
        from .owners import baseline as owner_baseline
        issues, ran = _ledger_findings(_ledger_result(cfg, owner_baseline(cfg, base)))
        own.issues += issues
        own.ran |= ran
        own.history(historical)
        return 0
    sentinel = cfg.root / 'tests/test_flowguard_intent.py'
    if model.declared_items() and not sentinel.is_file():
        own.red('input', 'sentinel:missing', 'sentinel', f'{cfg.rel(sentinel)} is missing', 'run python -m flowguard init',
                places=(cfg.rel(sentinel),))
        return 0
    command = ['-vv' if stream_all else '-q', '-p', 'flowguard.intent.plugin', '--flowguard-record-tests']
    if deep:
        command.append('--flowguard-deep')
    if stream_all:
        command += ['-o', 'verbosity_test_cases=2', '--durations=10', '--flowguard-complete']
    if base is not None:
        command.append('--flowguard-base=' + base)
    initial_baseline = not data.get('collection') or retry_incomplete or deep and not data['collection'].get('deep', False)
    everything = everything or initial_baseline
    declared = set(model.declared_items())
    if stream_all:
        print('FlowGuard check --all: preparing source dependencies before pytest.', flush=True)
    selected, flows, ordinary, test_records = _check_selection(cfg, model, data, everything, sentinel, base)
    extras = flows
    attempt = data.get('attempt') or {}
    failed_collection = (attempt.get('sentinel') is not None or attempt.get('collected')) and (
        attempt.get('missing') or attempt.get('sentinel') != 'ok')
    run = everything or selected or extras or ordinary or model.errors or failed_collection or not data.get('collection')
    executed = set()
    process_code = 0
    if run:
        output = cfg.cache / 'check-output.txt'
        if stream_all:
            scope = ': running full pytest'
            print(f'FlowGuard check --all{scope}; live output: {output}', flush=True)
        batch = list(command)
        if not everything:
            targets = {cfg.rel(cfg.intent), cfg.rel(sentinel), *ordinary}
            batch += ['--flowguard-rules=' + ','.join(sorted(selected | extras)), *sorted(targets)]
        started, timing = time.time(), time.perf_counter()
        process = _run_check_pytest(batch, cfg.root, output, stream_all)
        own.seconds += time.perf_counter() - timing
        process_code = own.code = process.returncode
        own.output = cfg.rel(output)
        actual = [line for line in (process.stdout + process.stderr).splitlines() if line.strip()]
        own.tail = [line for line in actual if line.startswith('FlowGuard:')] or actual[-5:]
        data = cache.read(cfg)
        executed.update(selected)
        if not model.declared_items():
            own.history(historical)
            return process_code
        if not data.get('attempt') or data['attempt'].get('stamp', 0) < started:
            own.red('test', 'test:pytest', 'pytest', 'did not finish', f'read {own.output} and correct the reported error')
            return process_code
        if data['attempt'].get('sentinel') == 'ok' and not data['attempt'].get('missing'):
            for group in data['results'].values():
                group['items'] = {item: value for item, value in group['items'].items() if item in declared}
        if process_code == 0:
            completed = {file: record for file, record in test_records.items()
                         if (data['test_collection'].get(file, {}).get('stamp', 0) >= started
                             and data['test_collection'][file]['tests']
                             and all(data['tests'].get(nodeid, {}).get('outcome') == 'passed'
                                     for nodeid in data['test_collection'][file]['tests']))}
            with closing(build(cfg.root, roots=cfg.roots)) as graph:
                cache.save_test_dependencies(graph.con, completed)
                graph.con.commit()
    from .owners import baseline as owner_baseline
    revision = owner_baseline(cfg, base)
    if revision is not None and executed:
        old = cache.scan(cfg, history._texts(cfg, revision, cfg.rel(cfg.intent)))['rules']
        current = data['summary']['rules']
        # history.proven builds and reads the same map. Every proof is finished
        # before this function opens its write transaction, so it never waits on itself.
        proofs = {}
        for rid in sorted(executed):
            rule = model.rules[rid]
            parts = data['results'].get(rid, {}).get('items', {})
            if not parts or any(value.get('verdict') == 'red' for value in parts.values()):
                continue
            prior = [(row['fields'], row['expect']) for row in old.get(rid, {}).get('row_records', []) if not row['retired']]
            new_lines = {row['line'] for row in current[rid]['row_records']
                         if not row['retired'] and (row['fields'], row['expect']) not in prior}
            retained = {proof.get('signature') for value in parts.values() for proof in value.get('proven_rows', [])}
            for row in rule.live_rows:
                if row.line not in new_lines or history.current_row_signature(rule, row) in retained:
                    continue
                proof = history.proven(cfg, rule, row, revision)
                proofs.setdefault(rid, []).append(proof)
        with closing(build(cfg.root, roots=cfg.roots)) as graph:
            for rid, found in proofs.items():
                cache.save_proven(graph.con, model.rules[rid], found)
            graph.con.commit()
        data = cache.read(cfg)
    for group in data['results'].values():
        group['items'] = {item: value for item, value in group['items'].items() if item in declared}
    data['summary']['errors'].extend(error for error in model.errors if error not in data['summary']['errors'])
    data['history'] = historical
    issues, lines = _cache_findings(cfg, model, data)
    own.issues += issues + (_owner_rules_unverified(cfg, data) if stream_all else [])
    own.lines += lines
    own.ran |= _judged_names(model, data)
    return process_code


def _owner_rules_unverified(cfg, data):
    """check --all: a rule quoting the owner's words that stays grey is red (D7), one finding per rule. Nothing exempts
    one: the ledger's [unverified] section, which did, was removed in 5.0."""
    from .api import IntentError
    from .signals import ascii_text, finding
    from .sources import cited, parse
    issues = []
    for rid, item in data['summary']['rules'].items():
        result = data['results'].get(rid, {})
        # The --deep mutation probe (`live`) measures how tightly the tests bind a rule, not whether the rule
        # was checked: a `fields` anchor cannot be called directly by it, and its rule is still verified.
        checked = dict(result, items={key: value for key, value in result.get('items', {}).items()
                                      if value.get('kind') != 'live'})
        if item.get('superseded_by') or _rule_colour(item, checked) != 'grey':
            continue
        try:
            source = cited(parse(item.get('source', '')), cfg)     # rule.<id>: the words its rules.toml entry cites
        except IntentError:
            continue        # The load check reports an unreadable source.
        if source.kind not in ('owner', 'request', 'picked'):
            continue
        reasons = [ascii_text(message) for value in result.get('items', {}).values() for message in value.get('grey', ())]
        # The line names no way to silence it (design 4.7): the grey reasons, with their own steps, are its detail.
        issues.append(finding('rule', f'unverified:{rid}', f'rule {rid}',
                              [("cites the owner's pick among the agent's options" if source.kind == 'picked' else
                                'cites original words from the owner') + f' ({source.rids[0]}), but is now grey (unverified): '
                               + (reasons[0].partition(' -> ')[0] if reasons else 'no results yet')],
                              'restore observability so the rule is checked again', detail=reasons))
    return issues


def _early_plugin(text):
    """Use pytest's project configuration so preparation precedes conftest imports."""
    if text.startswith('\ufeff'):
        return '\ufeff' + _early_plugin(text[1:])
    header = '[tool.pytest.ini_options]'
    data = tomllib.loads(text).get('tool', {}).get('pytest', {}).get('ini_options', {})
    options = data.get('addopts', '')
    if not isinstance(options, (str, list)):
        raise ValueError('pytest addopts must be text or a list of text options')
    parts = shlex.split(options) if isinstance(options, str) else list(options)
    plugin = 'flowguard.intent.plugin'
    if '-p' + plugin in parts or any(a == '-p' and b == plugin for a, b in zip(parts, parts[1:])):
        return text
    if any(not isinstance(part, str) for part in parts):
        raise ValueError('pytest addopts must be text or a list of text options')
    value = options.rstrip() + ' -p ' + plugin if isinstance(options, str) else [*options, '-p', plugin]
    line = 'addopts = ' + json.dumps(value.lstrip() if isinstance(value, str) else value, ensure_ascii=False) + '\n'
    section = re.search(r'^\[tool\.pytest\.ini_options\][ \t]*(?:#.*)?$', text, re.M)
    if not section:
        return text.rstrip() + '\n\n' + header + '\n' + line
    start = section.end()
    if start == len(text):
        text += '\n'
    start += 1
    next_section = re.search(r'^\[', text[start:], re.M)
    end = start + next_section.start() if next_section else len(text)
    body = text[start:end]
    setting = re.search(r'^[ \t]*addopts[ \t]*=', body, re.M)
    if setting:
        finish = body.find('\n', setting.end())
        while True:
            finish = len(body) if finish < 0 else finish + 1
            try:
                tomllib.loads(body[setting.start():finish])
                break
            except tomllib.TOMLDecodeError:
                if finish == len(body):
                    raise ValueError('cannot update pytest addopts without changing other settings')
                finish = body.find('\n', finish)
        body = body[:setting.start()] + line + body[finish:]
    else:
        body = body.rstrip() + '\n' + line + '\n'
    return text[:start] + body + text[end:]


NPM_HEADER = INIT_MARK + ': FlowGuard\'s map checks inside `npm test`.'
NPM_CHECK = NPM_HEADER + '''
// It does one thing: run `python -m flowguard check --static` at the project root and fail when anything is red
// (exit 1) or FlowGuard cannot run. Its lines are FlowGuard's block: in a run of FlowGuard's test runner plugin
// (FLOWGUARD_VITEST_OBS set) they go to that run's static.json, which the plugin prints in its block after the
// summary; otherwise this test prints them. On red it fails with one line that points at the block.
// Python is found in this order:
//   1. the FLOWGUARD_PYTHON environment variable, when set (then only that one);
//   2. the interpreter that ran `flowguard init` on this machine, recorded in @RECORDED@ (git-ignored);
//   3. `python3`, `python` and, on Windows, `py -3` on PATH.
// The first that can import flowguard runs the check. When none can, FlowGuard is not installed on this machine:
// the test is skipped with that reason and the project's own tests run as they would without FlowGuard. With
// FLOWGUARD_PYTHON set, that interpreter must import flowguard, or the test fails and says what was tried.
@IMPORTS@
const ROOT = @ROOT@;
const RECORDED = path.join(ROOT, ...@RECORDED@.split('/'));

function interpreters() {
  if (process.env.FLOWGUARD_PYTHON) return [[process.env.FLOWGUARD_PYTHON]];
  const listed = fs.existsSync(RECORDED) ? [[fs.readFileSync(RECORDED, 'utf8').trim()]] : [];
  listed.push(['python3'], ['python']);
  if (process.platform === 'win32') listed.push(['py', '-3']);
  return listed;
}

function findPython() {
  const tried = [];
  for (const [command, ...prefix] of interpreters()) {
    const probe = spawnSync(command, [...prefix, '-c', 'import flowguard'], { cwd: ROOT, encoding: 'utf8' });
    if (probe.status === 0) return { command, prefix, tried };
    const why = probe.error ? probe.error.message : ((probe.stderr || '').trim().split('\\n').pop() || 'exit ' + probe.status);
    tried.push([command, ...prefix].join(' ') + ': ' + why);
  }
  return { command: null, prefix: [], tried };
}

function reds(lines, stdout) {
  // The red lines the check found: those of static.json, or the count on the block's first line.
  if (lines !== null) {
    return fs.existsSync(lines) ? JSON.parse(fs.readFileSync(lines, 'utf8')).lines.filter((line) => line.kind === 'red').length : 0;
  }
  const first = /^FlowGuard \\d+\\.\\d+ \\(.*\\): (\\d+) red[,;]/m.exec(stdout);
  return first ? Number(first[1]) : 0;
}

const PYTHON = findPython();
const ABSENT = PYTHON.command === null && !process.env.FLOWGUARD_PYTHON;

(ABSENT ? test.skip : test)(ABSENT ? 'FlowGuard check --static (FlowGuard is not installed here: its map checks did not run)'
  : 'FlowGuard check --static', () => {
  const python = PYTHON;
  if (python.command === null) {
    throw new Error('FlowGuard: no Python that can import flowguard was found; set FLOWGUARD_PYTHON to the interpreter '
      + 'FlowGuard is installed in. Tried:\\n' + python.tried.join('\\n'));
  }
  const observations = process.env.FLOWGUARD_VITEST_OBS;
  const lines = observations ? path.join(observations, 'static.json') : null;
  const env = { ...process.env, PYTHONIOENCODING: 'utf-8' };
  if (lines !== null) {
    env.FLOWGUARD_LINES = lines;
    fs.rmSync(lines, { force: true });        // never the lines of an earlier run
  }
  const run = spawnSync(python.command, [...python.prefix, '-m', 'flowguard', 'check', '--static'], {
    cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, env,
  });
  const stdout = (run.stdout || '').trimEnd();
  const output = ((run.stdout || '') + (run.stderr || '')).trimEnd();
  if (lines === null) {
    if (output) console.log(output);
  } else if ((run.stderr || '').trim()) {
    console.error((run.stderr || '').trimEnd());
  }
  if (run.error) throw run.error;
  const red = run.status === 1 ? reds(lines, stdout) : 0;
  if (red > 0) throw new Error('FlowGuard: ' + red + ' red, see the FlowGuard block at the end');
  if (run.status !== 0) {
    throw new Error('FlowGuard check --static exit ' + run.status + (output ? ':\\n' + output : ''));
  }
}, 600000);
'''


# The scripts init reads as test suites, and the unit suite names it wires before any other (`test:unit`, `unit`).
_TEST_SCRIPT = re.compile(r'test(?:[:_-].+)?|unit')
_UNIT_SCRIPT = re.compile(r'(?:test[:_-])?unit')
# Suites that reach real databases and services: init leaves their scripts as they are. A script is one when a
# part of its name (split on : _ -) or a folder of a path it runs (split on /) is one of these words or starts
# with `integration`.
_OTHER_SUITES = {'int', 'it', 'e2e', 'db', 'database', 'smoke', 'acceptance', 'perf', 'performance', 'load', 'bench',
                 'benchmark'}
# Options of vitest and jest whose value is the next word (unless written `--option=value`); the others are flags.
_VALUED = {'-c', '--config', '-r', '--root', '--dir', '--project', '-t', '--testNamePattern', '--reporter', '--outputFile',
           '--environment', '--pool', '--shard', '--mode', '--exclude', '--testPathPattern', '--testPathPatterns',
           '--selectProjects', '--rootDir', '--roots', '--projects', '--ignoreProjects', '--workspace', '--changedSince',
           '--testMatch', '--testRegex', '--testPathIgnorePatterns'}
# Options that choose the files or tests a call runs from something init does not read (its own root or folder, a
# config, a project, test names, a shard, changed or related files): init cannot tell whether such a call runs a
# file at the package root, and a file named on it may still not run.
_ELSEWHERE = {'-r', '--root', '--dir', '--rootDir', '--roots', '-c', '--config', '--project', '--projects',
              '--selectProjects', '--ignoreProjects', '--workspace', '-t', '--testNamePattern', '--shard', '--changed',
              '-o', '--onlyChanged', '--changedSince', '--lastCommit', '--findRelatedTests', '-f', '--onlyFailures',
              '--testPathPattern', '--testPathPatterns', '--testMatch', '--testRegex'}
_WATCH = {'--watch', '--watchAll'}
# Options init knows to leave the files a call runs as they are: reporting, workers, timeouts, coverage, caching.
# A call with any other option is one init cannot read: it neither wires nor names it as running a file.
_SAFE = {'--run', '--passWithNoTests', '--silent', '--coverage', '--no-coverage', '--globals', '--isolate', '--no-isolate',
         '--no-file-parallelism', '--fileParallelism', '--ci', '--runInBand', '-i', '--verbose', '--colors', '--no-colors',
         '--color', '--no-color', '--json', '--detectOpenHandles', '--forceExit', '-u', '--update', '--no-cache',
         '--logHeapUsage', '--allowOnly', '--hideSkippedTests', '--clearMocks', '--reporter', '--reporters', '--outputFile',
         '--coverageReporters', '--coverageDirectory', '--watchman', '--no-watchman', '--pool', '--environment',
         '--maxWorkers', '--minWorkers', '--testTimeout', '--hookTimeout', '--bail', '--mode', '--maxConcurrency', '--retry',
         '--logLevel'}
_SAFE_PREFIXES = ('--coverage.', '--reporter.', '--outputFile.', '--sequence.', '--poolOptions.')
# Safe options whose value is the next word unless written `--option=value`.
_SAFE_VALUED = {'--reporter', '--outputFile', '--coverageDirectory', '--pool', '--environment', '--maxWorkers',
                '--minWorkers', '--testTimeout', '--hookTimeout', '--mode', '--maxConcurrency', '--retry', '--logLevel'}
# jest's array options (yargs): every word after one, up to the next option, is a value, also after `--reporters=x`.
_JEST_ARRAYS = {'--reporters', '--coverageReporters'}
# vitest's options with an optional value (`-u [type]`): the next word, unless it is an option.
_VITEST_OPTIONAL = {'-u', '--update'}
# The words vitest's --silent takes (vitest 3.1 on refuse any other word after it, `--silent tests/unit`, where vitest
# 3.0 and earlier read a flag and then a path): the next word only when it is one of them.
_SILENT = ('true', 'yes', 'false', 'no', 'passed-only')
# The prefixed options vitest 2 to 5 all read as booleans; every other prefixed option (`--coverage.include src`) has a
# value, except the ones below.
_PREFIXED_FLAGS = re.compile(r'--coverage\.(?:enabled|clean|cleanOnRerun|reportOnFailure|allowExternal|skipFull'
                             r'|thresholds\.100)|--sequence\.(?:shuffle(?:\.files|\.tests)?|concurrent)')
# Prefixed options vitest versions read differently, a boolean in some (the next word is a path) and a value in others
# (the next word is that value): vitest 3's --coverage.all and poolOptions booleans, which vitest 4 dropped (an option
# vitest does not know takes the next word), --coverage.thresholds.autoUpdate (a value from vitest 4),
# --coverage.thresholds.perFile (from vitest 5) and vitest 5's new booleans. They take true, yes, false or no; a call
# that gives one another word is one init cannot read.
_PREFIXED_VERSIONED = re.compile(r'--coverage\.(?:all|thresholds\.(?:autoUpdate|perFile)|excludeAfterRemap'
                                 r'|autoAttachSubprocess)|--poolOptions\.\w+\.(?:isolate|singleThread|singleFork|useAtomics)')
# The file a runner's package starts it from when a script calls it through node (`node node_modules/jest/bin/jest.js`).
_RUNNER_FILES = {'jest': 'jest.js', 'vitest': 'vitest.mjs'}
# Commands a shell finds without npx: node and the package managers; npx runs any other word of a call.
_LAUNCHERS = {'node', 'npx', 'pnpm', 'pnpx', 'yarn', 'bun', 'bunx'}
# node's flag jest needs to load ES module tests, and jest's documented call with it.
_VM = '--experimental-vm-modules'
_JEST_ESM = f'node {_VM} node_modules/jest/bin/jest.js'
# Options that make a call wait for a debugger before it runs (node's, also in NODE_OPTIONS, and vitest's).
_DEBUGGER = re.compile(r'--inspect-(?:brk|wait)\b|--inspectBrk\b')


def _alone(prefix, name):
    """The call that runs the generated test file `name` alone, started the way `prefix` starts the runner (the
    words of a script's call up to the runner, and vitest's `run`: `vitest run`, `node --experimental-vm-modules
    node_modules/jest/bin/jest.js`)."""
    return f'{prefix} {name}'


def _vm_scripts(scripts):
    """The scripts that run under node's --experimental-vm-modules: those whose command names the flag
    anywhere (`NODE_OPTIONS=... jest`, `export NODE_OPTIONS=... && jest`, Windows' `set NODE_OPTIONS=... &&
    jest`), and the scripts such a command runs (`npm run test:jest`, `pnpm run x`, `yarn x`), which inherit its
    environment."""
    found = {name for name, command in scripts.items() if isinstance(command, str) and _VM in command}
    pending = list(found)
    while pending:
        command = scripts[pending.pop()]
        for other in re.findall(r'\b(?:npm|pnpm|yarn)(?:\s+run(?:-script)?)?\s+([\w:.-]+)', command):
            if other in scripts and other not in found:
                found.add(other)
                pending.append(other)
    return found


def _vm_launch(prefix):
    """How a line for another script starts jest with node's --experimental-vm-modules, from a call's `prefix`
    (its words up to the runner): its `cross-env`, its NODE_OPTIONS setting reduced to that flag, `node` with
    that flag alone, and the runner. The call's other settings (a database URL) and node flags (a debugger that
    waits, a heap size) belong to it alone. A call that passes the flag another way gives jest's documented call."""
    words = re.findall(r'(?:[^\s"\']+|"[^"]*"|\'[^\']*\')+', prefix)
    kept = [f'NODE_OPTIONS={_VM}' if word.startswith('NODE_OPTIONS=') else word for word in words[:-1]
            if word in ('cross-env', 'node', _VM) or word.startswith('NODE_OPTIONS=') and _VM in word]
    return ' '.join([*kept, words[-1]]) if any(_VM in word for word in kept) else _JEST_ESM


def _from_shell(call):
    """`call` as a shell outside npm runs it: npm puts node_modules/.bin on PATH, so the first word after the
    leading `NAME=value` settings goes through npx unless it is node or a package manager."""
    for word in re.finditer(r'(?:[^\s"\']+|"[^"]*"|\'[^\']*\')+', call):
        if re.match(r'[A-Za-z_]\w*=', word.group()):
            continue
        return call if word.group() in _LAUNCHERS else call[:word.start()] + 'npx ' + call[word.start():]
    return call


def _takes(option, runner):
    """How `option` of `runner` takes the word after it (unless written `--option=value`): 'next' always as its
    value, 'word' unless it is an option, 'every' with each word after it up to the next option (also after
    `--option=value`), 'silent' only one of `_SILENT`, 'versioned' only true, yes, false or no (another word
    leaves the call unread, `_PREFIXED_VERSIONED`), 'flag' only `true` or `false` (a `--no-` option none;
    `--bail` also a number)."""
    if runner == 'jest' and option in _JEST_ARRAYS:
        return 'every'
    if runner == 'vitest' and option == '--silent':
        return 'silent'
    if _PREFIXED_VERSIONED.fullmatch(option):
        return 'versioned'
    if option in _VALUED or option in _SAFE_VALUED or runner == 'jest' and option == '-w':
        return 'next'
    if runner == 'vitest' and option in _VITEST_OPTIONAL or option.startswith(_SAFE_PREFIXES) \
            and not _PREFIXED_FLAGS.fullmatch(option):
        return 'word'
    return 'flag'


class _Call(typing.NamedTuple):
    """A call of the runner in a script (see _runner_calls)."""
    text: str
    watches: bool
    options: set
    paths: list
    clear: bool
    unread: set
    prefix: str
    end: int


def _runner_calls(command, runner):
    """Each call of `runner` in a script (`a && b`, `a; b` and `a || b` are calls of their own; the runner is a
    word named `runner` or its package's start file, `node_modules/jest/bin/jest.js`): its text, whether it
    watches, its options, its paths (`./` taken off; `.` is the package folder, spelled ''), whether init can
    read it (`clear`: every option is one of `_SAFE` or a watch option, and no option vitest versions read
    differently is given a word they read differently), the options it cannot read (`unread`), its prefix (its
    words up to the runner, then vitest's `run`) and where in its text a file added to it goes: at its end, or
    after its last path when its last option could take that file as its value (`vitest run tests -u`, `vitest
    run tests --silent`, `jest tests --reporters=default`). An option's value (`_takes`) is never a path:
    `--coverage.include src`, `-u tests` and vitest's `--silent passed-only` run every file, `--silent tests/unit`
    runs tests/unit. `--watch=false` and `--watchAll false` turn watching off; `vitest watch`, `vitest dev` and
    vitest's `-w` watch (jest's `-w` is its worker count)."""
    watch = _WATCH | ({'-w'} if runner == 'vitest' else set())
    safe = _SAFE | ({'-w'} if runner == 'jest' else set())
    calls = []
    for segment in re.split(r'&&|\|\||;', command):
        words = list(re.finditer(r'\S+', segment))
        at = next((index for index, word in enumerate(words)
                   if word.group().rpartition('/')[2] in (runner, _RUNNER_FILES[runner])), None)
        if at is None or [word.group() for word in words[at + 1:at + 2]] == ['related']:
            continue
        rest = words[at + 1:]
        verb = rest[0].group() if rest and rest[0].group() in ('run', 'watch', 'dev') else ''
        options, paths, pending, watches, last, unsure = set(), [], None, verb in ('watch', 'dev'), None, set()
        for match in rest[1:] if verb else rest:
            word = match.group()
            if pending is not None:
                option, takes = pending
                pending = pending if takes == 'every' else None
                if takes == 'next' or takes in ('word', 'every') and not word.startswith('-') or takes == 'flag' and (
                        word in ('true', 'false') and not option.startswith('--no-')
                        or option == '--bail' and word.isdigit()) or takes == 'silent' and word in _SILENT \
                        or takes == 'versioned' and word in ('true', 'yes', 'false', 'no'):
                    if option in watch:
                        watches = word == 'true'
                    continue
                if takes == 'versioned' and not word.startswith('-'):
                    unsure.add(option)
                pending = None
            if word.startswith('-'):
                option, equals, value = word.partition('=')
                options.add(option)
                if option in watch:
                    watches = value != 'false' if equals else True
                takes = _takes(option, runner)
                pending = (option, takes) if takes == 'every' or not equals else None
            else:
                last = match
                while word.startswith('./'):
                    word = word[2:]
                paths.append('' if word in ('.', '') else word.rstrip('/'))
        clear = not unsure and all(option in safe or option in watch or option.startswith(_SAFE_PREFIXES) for option in options)
        unread = unsure | {option for option in options if option not in _SAFE and not option.startswith(_SAFE_PREFIXES)}
        prefix = segment[words[0].start():words[at].end()] + (' run' if runner == 'vitest' else '')
        opened = pending is not None and pending[1] != 'flag' and last is not None
        calls.append(_Call(segment, watches, options, paths, clear, unread, prefix,
                           last.end() if opened else len(segment.rstrip())))
    return calls


def _filtered_scripts(cfg, package, runner, name, launch, vm, vm_scripts=frozenset()):
    """What init did to the test suite scripts (`test`, `test:unit`, `unit`, ...) so one of them runs `name`;
    the script that runs it (None when init can tell of none); and the watch scripts or other suites that run it.
    init reads a call only when every option it has is one it knows to leave the files alone (`_SAFE`:
    reporters, workers, timeouts, coverage; `_runner_calls` `clear`); a call with any other option (its own
    root or config, a project, test names, ignore patterns, an option init does not know) may run any files, so
    init neither wires it nor names it as running `name`. A script runs `name` when a call init reads names it
    or runs every file (no path, or the package folder). Watch scripts (a name part `watch`, `--watch`, vitest's
    `-w`, `vitest watch`) and integration, end-to-end, database, smoke, acceptance, performance, load or
    benchmark suites (real databases and services; by a part of the name or a folder they run) are never wired
    and never named as the script that runs it, nor are debug scripts (a name part `debug`, or a call that waits
    for a debugger: `--inspect-brk`). With `vm` (jest loads `name`, an ES module, only under node's
    --experimental-vm-modules) a call without that flag cannot run it and counts as no call. A script that runs the runner on named folders only (`vitest
    run tests/unit`) skips a test at the package root, so `name` is added to one such script: `test` (what npm
    test runs) first, then `test:unit`, `test-unit`, `test_unit` and `unit`, then other unit names, then shorter
    names, then the order of the file. The check covers the whole repository, so one script is enough: nothing
    is added when a call init reads already names `name`. A script init cannot edit without touching the rest of
    the file is named with the edit to make, and the next one is tried. A script init cannot read is named with
    the edit to make when it is `test`, runs named paths, or when nothing runs `name`; the other suites init left alone are
    named when nothing runs it. A script that runs single files is a check of its own and stays as it is. `name`
    goes where `_runner_calls` says, so no option takes it as its value. The edit named for a script starts the
    runner the way that script's call does (its prefix); the other lines start it with `launch`."""
    text = package.read_text(encoding='utf-8-sig')
    scripts = json.loads(text).get('scripts') or {}
    named, runners, excluded, others, tried, unread = False, [], [], [], [], []
    for index, (script, command) in enumerate(scripts.items()):
        calls = [call for call in _runner_calls(command, runner) if not vm or script in vm_scripts or _VM in call.prefix] \
            if isinstance(command, str) and _TEST_SCRIPT.fullmatch(script) else []
        if not calls:
            continue
        words = re.split(r'[:_-]', script.lower())
        clear = [call for call in calls if call.clear]
        names = any(name in call.paths for call in clear)
        named = named or names
        runs = names or any(not call.paths or '' in call.paths for call in clear)
        if _other_suite(script, calls):
            (excluded if runs else others).append(script)
            continue
        if 'watch' in words or 'debug' in words or any(call.watches or _DEBUGGER.search(call.text) for call in calls):
            if runs:
                excluded.append(script)
            continue
        rank = (script != 'test', not _UNIT_SCRIPT.fullmatch(script.lower()),
                not any(word.startswith('unit') for word in words), len(script), index)
        if runs:
            runners.append((rank, script))
            continue
        wire = next((call for call in clear if call.paths and all((package.parent / path).is_dir() for path in call.paths)),
                    None)
        if wire is not None:
            tried.append((rank, script, command, wire.text, wire.end))
        if len(clear) < len(calls):
            options = sorted({option for call in calls if not call.clear for option in call.unread})
            prefix = next(call.prefix for call in calls if not call.clear)
            unread.append((rank, script, command, options, any(call.paths for call in calls), prefix))
    call = _alone(launch, name)
    lines, wired = [], None
    for rank, script, command, segment, end in [] if named else sorted(tried):
        where = f'{cfg.rel(package)} script "{script}"'
        new = command.replace(segment, segment[:end] + ' ' + name + segment[end:], 1)
        spelled = re.compile(r'(' + re.escape(json.dumps(script)) + r'\s*:\s*)' + re.escape(json.dumps(command)))
        if len(spelled.findall(text)) != 1:
            lines.append(f'{where} runs {runner} on named paths only: change it to {new} so it runs {name} too')
            continue
        package.write_text(spelled.sub(lambda match: match.group(1) + json.dumps(new), text), encoding='utf-8')
        lines.append(f'{where} runs {runner} on named paths only; init added {name}: {new}')
        runners.append((rank, script))
        wired = script
        break
    for _, script, command, options, has_paths, prefix in [] if named else sorted(unread):
        if has_paths or not runners or script == 'test':           # npm test's own script is always worth the line
            lines.append(f'{cfg.rel(package)} script "{script}" runs {runner} with {", ".join(options)}, which init does not '
                         f'read ({command}): init cannot tell whether it runs {name}; if it does not, add '
                         f'"&& {_alone(prefix, name)}" to it yourself')
    if not runners and others:
        left = ', '.join('"' + script + '"' for script in others)
        lines.append(f'{cfg.rel(package)} script {left} runs {runner} on an integration, end-to-end or other suite that '
                     'reaches real databases and services: init leaves it alone; to run the check with it, '
                     f'add "&& {call}" to it yourself' if len(others) == 1 else
                     f'{cfg.rel(package)} scripts {left} run {runner} on integration, end-to-end or other suites that '
                     'reach real databases and services: init leaves them alone; to run the check with one of them, '
                     f'add "&& {call}" to it yourself')
    return lines, min(runners)[1] if runners else None, excluded


def _package_runner(package):
    """(the package.json's data, its scripts as text, its test runner): 'vitest', or 'jest' for a jest project, as its
    dependencies and its "test" script name them, None when neither its dependencies nor its scripts name either."""
    data = json.loads(package.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError(f'{package}: package.json is not a JSON object')
    named = {**(data.get('dependencies') or {}), **(data.get('devDependencies') or {})}
    scripts = {name: str(command) for name, command in (data.get('scripts') or {}).items()}
    script = scripts.get('test', '')
    if not {'vitest', 'jest'} & set(named) and not any(re.search(r'\b(?:vitest|jest)\b', command) for command in scripts.values()):
        return data, scripts, None
    return data, scripts, 'jest' if ('jest' in named or 'jest' in script) and 'vitest' not in named and 'vitest' not in script \
        else 'vitest'


def _other_suite(script, calls):
    """Is this test script an integration, end-to-end, database, smoke, acceptance, performance, load or benchmark
    suite (real databases and services): a part of its name (split on : _ -) or a folder of a path one of its
    `calls` runs (split on /) is one of `_OTHER_SUITES` or starts with `integration`?"""
    words = re.split(r'[:_-]', script.lower())
    folders = [folder for call in calls for path in call.paths for folder in path.lower().split('/')]
    return any(part.startswith('integration') or part in _OTHER_SUITES for part in words + folders)


def _test_marks(cfg, files):
    """{file: words} of the test files `show Model.field` lists (`owners.field_lines`) that the project's test scope
    leaves out, or that lie where its scripts run a suite that reaches real databases and services (gate-7: Planning
    Tool's backend runs tests/integration only through its "test:integration" script): a Python file pytest's
    configured scope does not take (`deps.test_scope`: testpaths, python_files, norecursedirs); a JS/TS file of an npm
    package (`deps.npm_packages`, the nearest one holding it) in a folder or file a test script of that package runs
    with its runner (`_package_runner`, `_runner_calls`) when that script is such a suite as init reads one
    (`_other_suite`), and one the test.include and test.exclude of the package's vitest config leave out
    (`vitest.static_test_runs`; nothing when init cannot read them). Any other file gets no words."""
    from .deps import npm_packages, test_scope
    from .vitest import static_test_runs
    from ..structure.readers.registry import ECMA, language_for
    in_scope, packages, marks = None, None, {}
    for file in files:
        said = []
        if file.endswith('.py'):
            in_scope = in_scope or test_scope(cfg)
            if not in_scope(file):
                said.append("left out of the test scope: pytest's testpaths, python_files and norecursedirs do not take it")
        elif language_for(file) in ECMA:
            packages = packages if packages is not None else sorted(
                (package for package in npm_packages(cfg.root)), key=lambda package: -len(package.parent.parts))
            package = next((package for package in packages if (cfg.root / file).is_relative_to(package.parent)), None)
            if package is not None:
                _, scripts, runner = _package_runner(package)
                inside = (cfg.root / file).relative_to(package.parent).as_posix()
                for script, command in scripts.items() if runner else ():
                    calls = _runner_calls(command, runner) if _TEST_SCRIPT.fullmatch(script) else []
                    runs = [path for call in calls for path in call.paths if path and (
                        inside == path or inside.startswith(path + '/') or fnmatch.fnmatchcase(inside, path))]
                    if runs and _other_suite(script, calls):
                        said.append(f'a suite that reaches real databases and services: {cfg.rel(package)} script '
                                    f'"{script}" runs {runs[0]}')
                        break
                # A package without a config runs vitest's defaults, which take every test file name: never False.
                taken, config, _ = static_test_runs(package.parent, inside) if runner == 'vitest' else (True, None, ())
                if taken is False:
                    said.append(f'left out of the test scope: test.include and test.exclude of '
                                f'{cfg.rel(package.parent / config)} do not take it')
        if said:
            marks[file] = '; '.join(said)
    return marks


def _npm_check(cfg, package):
    """Write the vitest (or, for a jest project, jest) test that runs `check --static`; returns what it did."""
    data, scripts, runner = _package_runner(package)
    if runner is None:
        return (f'{cfg.rel(package)} names no test runner (vitest or jest in its dependencies or scripts): no FlowGuard '
                'test is written there; the check of another package covers the whole repository.')
    # jest loads a test as an ES module only under node's --experimental-vm-modules, and every test as CommonJS
    # without it, whatever the package's type: the test of a "type": "module" package is an ES module when a script
    # runs jest with that flag (in its own call, an earlier `export`/`set NODE_OPTIONS=` of the script, or a script
    # that runs it: `_vm_scripts`), or none runs jest at all; when its scripts run jest only without it, CommonJS.
    under_vm = _vm_scripts(scripts)
    calls = [call for command in scripts.values() for call in _runner_calls(command, runner)]
    vm_calls = [call for script_name, command in scripts.items() for call in _runner_calls(command, runner)
                if script_name in under_vm or _VM in call.prefix]
    vm = runner == 'jest' and data.get('type') == 'module' and (not calls or bool(vm_calls))
    module = runner == 'vitest' or vm
    target = package.parent / ('flowguard.static.test.mjs' if runner == 'vitest' else 'flowguard.static.test.js')
    relative = os.path.relpath(cfg.root, package.parent).replace(os.sep, '/')
    if module:
        imports = ("import { test } from 'vitest';\n" if runner == 'vitest' else '') + \
            ("import { spawnSync } from 'node:child_process';\nimport fs from 'node:fs';\nimport path from 'node:path';\n"
             "import { fileURLToPath } from 'node:url';")
        root = f"path.resolve(path.dirname(fileURLToPath(import.meta.url)), {json.dumps(relative)})"
    else:
        imports = "const { spawnSync } = require('node:child_process');\nconst fs = require('node:fs');\nconst path = require('node:path');"
        root = f'path.resolve(__dirname, {json.dumps(relative)})'
    text = (NPM_CHECK.replace('@IMPORTS@', imports).replace('@ROOT@', root)
            .replace('@RECORDED@', json.dumps(RECORDED_PYTHON)))
    if target.exists() and not target.read_text(encoding='utf-8').startswith(NPM_HEADER):
        raise ValueError(f'{target}: an existing file has this name; rename it, then run init again')
    target.write_text(text, encoding='utf-8', newline='\n')
    # How the advice starts the runner: as is, but an ES module test of jest under --experimental-vm-modules, the
    # way the first script that does so starts it (`_vm_launch`), else as jest's own documentation spells it.
    launch = 'vitest run' if runner == 'vitest' else 'jest'
    if vm:
        launch = next((_vm_launch(call.prefix) for call in vm_calls if _VM in call.prefix), _JEST_ESM)
    lines, runs, excluded = _filtered_scripts(cfg, package, runner, target.name, launch, vm, under_vm)
    # The line names the script that runs the file: npm test only when the "test" script itself runs it, and never
    # a watch script or a suite that reaches real databases and services.
    if runs is None:
        left = ', '.join('"' + script + '"' for script in excluded)
        found = (f'in {cfg.rel(package)} only {left} {"runs" if len(excluded) == 1 else "run"} it, and init names no watch '
                 'or debug script, nor a suite that reaches real databases and services' if excluded else
                 f'init finds no script in {cfg.rel(package)} that runs it')
        call = _alone(launch, target.name)
        static = (f'Generated {cfg.rel(target)} ({runner}), but {found}: add "&& {call}" to the script you run your tests '
                  f'with, so it runs python -m flowguard check --static and fails on red ({_from_shell(call)} runs it alone).')
    else:
        script = 'npm test' if runs == 'test' else 'npm run ' + runs
        # vitest runs a file only when its config's test.include takes it, whatever the script names
        from .vitest import static_test_runs
        taken, config, include = static_test_runs(package.parent, target.name) if runner == 'vitest' else (True, None, ())
        where = cfg.rel(package.parent / config) if config else ''
        if taken:
            static = f'Generated {cfg.rel(target)} ({runner}): {script} runs python -m flowguard check --static and fails on red.'
        elif taken is None:
            static = (f'Generated {cfg.rel(target)} ({runner}): init cannot read test.include in {where}, so it cannot confirm '
                      f'that {script} runs python -m flowguard check --static: test.include must take {target.name}.')
        else:
            static = (f'Generated {cfg.rel(target)} ({runner}), but test.include in {where} ({", ".join(include)}) leaves it '
                      f'out: add "{target.name}" to test.include there, so {script} runs python -m flowguard check --static and '
                      'fails on red.')
    static += ''.join('\n' + line for line in lines)
    if runner == 'jest':
        return static + '\nThe execution side supports vitest only: this jest project runs check --static alone.'
    from .vitest import wire
    return static + '\n' + wire(cfg, package)


# The conftest lines init wrote before 4.2, when it registered the plugin a second time beside addopts.
CONFTEST_PLUGIN = ('pytest_plugins = ["flowguard.intent.plugin"]\n',
                   'pytest_plugins = ([pytest_plugins] if isinstance(pytest_plugins, str) else list(pytest_plugins)) + ["flowguard.intent.plugin"]\n')


def _pytest_config(root, pyproject_text):
    """The file pytest reads its options from when that is not pyproject.toml, else None: pytest.toml or
    .pytest.toml (pytest 9), pytest.ini or .pytest.ini, or tox.ini/setup.cfg with a pytest section while
    pyproject.toml has none (pytest's order)."""
    for name in ('pytest.toml', '.pytest.toml', 'pytest.ini', '.pytest.ini'):
        if (root / name).is_file():
            return name
    if re.search(r'^\[tool\.pytest\.ini_options\]', pyproject_text, re.M):
        return None
    for name, section in (('tox.ini', 'pytest'), ('setup.cfg', 'tool:pytest')):
        path = root / name
        if path.is_file() and re.search(r'^\[' + re.escape(section) + r'\]', path.read_text(encoding='utf-8-sig'), re.M):
            return name
    return None


def _register_plugin(cfg, conftest, text):
    """The pyproject.toml text with the plugin registered once: in pytest's addopts when pyproject.toml is
    pytest's configuration (it loads before any conftest), else in the sentinel's conftest.py. A conftest
    line an earlier init wrote beside addopts is removed."""
    content = conftest.read_text(encoding='utf-8') if conftest.exists() else ''
    if _pytest_config(cfg.root, text) is None:
        kept = content
        for line in CONFTEST_PLUGIN:
            kept = kept.replace('\n\n' + line, '\n').replace(line, '')
        if kept != content and kept.strip():
            conftest.write_text(kept.rstrip('\n') + '\n', encoding='utf-8')
        elif kept != content:
            conftest.unlink()           # it held nothing but init's own registration
        return _early_plugin(text)
    if 'flowguard.intent.plugin' not in content:
        conftest.write_text(content.rstrip() + '\n\n' + CONFTEST_PLUGIN['pytest_plugins' in content], encoding='utf-8')
    return text


def _legacy_bindings(cfg):
    """{folder: (files, modules)} of the Python test files that import a flowguard module this version does not
    have (FlowGuard 0.70's bindings import flowguard.map.facts): pytest cannot collect them."""
    import flowguard
    from .deps import NORECURSEDIRS, _patterns, _pytest_options, kept_out, test_scope
    package, scope = Path(flowguard.__file__).parent, test_scope(cfg)
    skipped = _patterns(_pytest_options(cfg), 'norecursedirs', NORECURSEDIRS)
    found = {}
    for folder, names, files in os.walk(cfg.root):
        names[:] = [name for name in names if name not in ('node_modules', '__pycache__')
                    and not kept_out(Path(folder, name).resolve(), skipped)]
        for name in files:
            path = Path(folder) / name
            relative = cfg.rel(path)
            if not name.endswith('.py') or not scope(relative):
                continue
            missing = sorted({module for module in re.findall(r'^\s*(?:from|import)\s+(flowguard(?:\.\w+)+)',
                                                              path.read_text(encoding='utf-8-sig', errors='replace'), re.M)
                              if not (package.joinpath(*module.split('.')[1:]).with_suffix('.py').is_file()
                                      or package.joinpath(*module.split('.')[1:], '__init__.py').is_file())})
            if missing:
                files_, modules = found.setdefault(Path(relative).parent.as_posix(), ([], set()))
                files_.append(relative)
                modules.update(missing)
    return found


def _legacy_binding_lines(cfg, pyproject_text):
    """What init prints about legacy bindings: the folders and the norecursedirs line that keeps pytest out."""
    from .deps import NORECURSEDIRS, _patterns, _pytest_options
    found = _legacy_bindings(cfg)
    if not found:
        return []
    roots = {cfg.rel(cfg.root / value) for value in _patterns(_pytest_options(cfg), 'testpaths', ['.'])}
    folders = sorted({folder.rpartition('/')[2] for folder in found if folder not in roots | {'.'}})
    lines = []
    for folder, (files, modules) in sorted(found.items()):
        lines.append(f'{folder}/ holds {len(files)} test files that import {", ".join(sorted(modules))}, which this '
                     'FlowGuard does not have (bindings of an older FlowGuard): pytest cannot collect them.')
    if folders:
        current = _patterns(_pytest_options(cfg), 'norecursedirs', NORECURSEDIRS)
        where = _pytest_config(cfg.root, pyproject_text) or 'pyproject.toml [tool.pytest.ini_options]'
        wanted = [*current, *(f for f in folders if f not in current)]
        # A TOML file takes a list; pytest.ini, tox.ini and setup.cfg take the patterns separated by spaces.
        value = json.dumps(wanted) if where.partition(' ')[0].endswith('.toml') else ' '.join(wanted)
        lines.append(f'To keep pytest out of them, set in {where} (pytest\'s list plus the folder; a check refuses '
                     f'--ignore): norecursedirs = {value}')
    if len(folders) < len(found):
        lines.append('Files directly in a test root cannot be left out by folder: move or delete them.')
    return lines


# FlowGuard 0.70 wrote its workflow into AGENTS.md (read, map check/confirm, target ..., models); 4.x has none of it.
LEGACY_SECTION = re.compile(r'^##[ \t]+(?P<title>[^\r\n]*?(?:workflow|current-map exception)[^\r\n]*)\r?\n'
                            r'(?P<body>.*?)(?=^#{1,2}[ \t]|^<!-- flowguard:start -->|\Z)', re.M | re.S | re.I)
LEGACY_WORDS = re.compile(r'\b0\.70\.\d+|flowguard (?:read|change)\b|\bmap (?:check|confirm)\b|'
                          r'\btarget (?:start|add|check|promote)\b|flowguard_unit_runner|current[- ]map', re.I)
# A line that still names a command of an earlier FlowGuard, which 4.x does not have. The top-level commands and the
# releases that had them (`ERAS`, of EARLIER_COMMANDS), as the git tags' flowguard/__main__.py gives them: read, change,
# map (0.70.2) and target (0.70.11) up to 0.75; template and release from 0.70.2 to 1.4; status (0.71.0) and where
# (0.71.1) to 1.4; decide from 0.75 and draft from 1.2, both to 1.4 (4.x drafts with `anchor draft` and `model draft`).
# The subcommands of map and target are 0.70.14's. After a launcher (python, python3.11, py, python.exe) or a backquote
# any of them is a command; written bare, only flowguard read, change, `map SUB` and `target SUB` are, all lowercase:
# the other words are prose after the name ("a FlowGuard release alone", "after each flowguard release", "python -m
# flowguard before each task"). 0.70's `map check` and `map confirm` are read in any case ("Map check must pass"), also
# in prose ("the site map check"), which cannot be told from them. A required version (`requires FlowGuard 0.70.14`,
# `FlowGuard 0.70.x is required`, `flowguard==0.70.14`) and the install tag are 0.70's; a minimum that 4.x meets
# ("requires FlowGuard 0.70.14 or newer") asks for nothing 4.x lacks and is not listed. A launcher may carry the
# interpreter's own options (`py -3.11 -m`, `python -X utf8 -m`, `python3 -I -m`). A capitalized `FlowGuard map` in
# backquotes with no subcommand is the map's name ("the `FlowGuard map` shows the owners"). A line that only names 0.70
# or its files (`.flowguard/models/**`, `flowguard_unit_runner.py` "belong to the earlier 0.70.x workflow") explains
# them and asks for nothing.
ERAS = {name: era for name, (era, _, _) in EARLIER_COMMANDS.items()}
LAUNCHER = r'\b(?:py|python[\d.]*)(?:\.exe)?\s+(?:-(?!m\b)[\w.]+(?:\s+(?!-)[\w.=]+)?\s+)*'
MAP_SUB = r'(?:scan|discover|show|find|digest|check|lint|impact|deps|confirm|models|verify)\b'
TARGET_SUB = r'(?:start|add|drop|check|promote)\b'
LEGACY_INSTRUCTION = re.compile(
    rf'(?P<command>(?:{LAUNCHER}-m\s+|`)(?i:flowguard)\s+(?:read|change|template|release|status|where|decide|draft'
    rf'|map(?:\s+{MAP_SUB})?|target(?:\s+{TARGET_SUB})?)\b'
    rf'|\bflowguard\s+(?:read|change|map\s+{MAP_SUB}|target\s+{TARGET_SUB})\b|\b(?i:map\s+(?:check|confirm))\b'
    rf'|`target\s+{TARGET_SUB})'
    rf'|(?P<launcher>{LAUNCHER}(?:-m\s+)?(?:[\w.-]+[/\\])*flowguard_unit_runner(?:\.py)?\b)'
    r'|(?P<install>@v0\.70\.\d+)'
    r'|(?P<requirement>\b(?i:requires?|needs?)\s+(?i:flowguard)\s+\**v?0\.70(?:\.\d+|\.x)?(?!\.\d)(?!\w)\**'
    r'(?!\s*(?:\+|(?i:or\s+(?:newer|later|higher|above))))'
    r'|\b(?i:flowguard)\s+\**v?0\.70(?:\.\d+|\.x)?\**\s+(?i:is\s+required)'
    r'|\b(?i:flowguard)(?:\[[\w,-]+\])?\s*[=~]=\s*v?0\.70(?:\.\d+)?)'
    r'|(?P<exception>\b(?i:current[- ]map\s+exception)\b)')


def _era(match):
    """The releases of FlowGuard that had what a `LEGACY_INSTRUCTION` match names: a command's (`ERAS`), else 0.70."""
    if not match['command']:
        return '0.70'
    after = re.search(r'(?i:flowguard)\s+(\w+)', match[0])
    return ERAS[(after[1] if after else match[0].strip('`').split()[0]).lower()]


def _legacy_instructions(content):
    """The lines of the AGENTS.md init writes (`content`, numbered as written) that name an earlier FlowGuard's command,
    launcher, install or required version (`LEGACY_INSTRUCTION`), each named in full with the releases that had it;
    the rules block init wrote is FlowGuard's own and is not read. A ban ("Do not run `flowguard change`") names the
    command too."""
    lines = []
    inside = False
    for number, line in enumerate(content.splitlines(), 1):
        inside = (inside or line.strip() == '<!-- flowguard:start -->') and line.strip() != '<!-- flowguard:end -->'
        if inside or line.strip() == '<!-- flowguard:end -->':
            continue
        eras = {}
        for match in LEGACY_INSTRUCTION.finditer(line):
            if match['command'] and re.fullmatch(r'`FlowGuard\s+map', match[0]):
                continue        # "the `FlowGuard map`": the name of the map, a noun, not 0.70's map command
            eras.setdefault(_era(match), {}).setdefault(match[0].strip('`'), None)
        if eras:
            named = ' and '.join(', '.join(f'`{name}`' for name in names) + f' from FlowGuard {era}' for era, names in eras.items())
            lines.append(f'AGENTS.md:{number} names {named}, which 4.x does not have ({line.strip()[:70]}): reword or delete it')
    return lines


def _legacy_agents(content, rules, newline, languages):
    """(content, lines to print) for an AGENTS.md written for FlowGuard 0.70: its workflow sections ("Six-step
    workflow", the current-map exception) give way to the rules block, in the first one's place; the install
    line and the pinned version (`Use FlowGuard **0.70.14**`) become this version; the project's own rules
    stay byte for byte. A sentence about what 0.70 did is not rewritten to claim it of this version: it is
    kept as it is. `init` lists afterwards, in the file it wrote, each remaining line that still names an earlier
    command (`_legacy_instructions`). A workflow section is FlowGuard's only when its body
    names flowguard, so a project's own release or data workflow stays."""
    removed = []
    def section(match):
        if 'flowguard' not in match['body'].lower() or not LEGACY_WORDS.search(match['body']):
            return match.group(0)
        removed.append(match['title'].strip())
        return '' if len(removed) > 1 or '<!-- flowguard:start -->' in content else rules + newline
    content = LEGACY_SECTION.sub(section, content)
    extra = '[languages]' if languages else ''
    content, installs = re.subn(r'flowguard(?:\[[\w,]+\])? @ (git\+\S+?)@v0\.70\.\d+',
                                lambda match: f'flowguard{extra} @ {match[1]}@v{__version__}', content)
    # Only the pinned statement; any other bold 'FlowGuard **0.70.x**' says what 0.70 was and stays as it is.
    content, versions = re.subn(r'(\bUse\s+FlowGuard\s+\**)0\.70\.\d+', lambda match: match[1] + __version__, content)
    lines = [f'AGENTS.md: the FlowGuard 0.70 section "{title}" is replaced by the project rules block' for title in removed]
    if installs or versions:
        lines.append(f'AGENTS.md: the FlowGuard version and install line now name {__version__}')
    return content, lines


# The CI fragment init writes. A project pytest has tests of runs everything; one whose tests npm runs (TS/JS) runs the
# map checks, which pytest would not, against where its branch left the default branch: a CI checkout is a detached
# HEAD, whose task start is HEAD itself, so without --base it would compare nothing. The base is set on a line of its
# own: GitHub runs a bash step under -e, so a merge-base that fails (no origin/main) fails the step instead of
# giving check an empty --base.
CI_PYTEST = '''# Merge these steps into the project CI after installing FlowGuard.
- uses: actions/checkout@v5
  with:
    fetch-depth: 0
- run: python -m flowguard check --all --deep
'''
CI_STATIC = '''# Merge these steps into the project CI after installing FlowGuard.
# The base is where this branch left the default branch. If the default branch is not called main, replace main below.
- uses: actions/checkout@v5
  with:
    fetch-depth: 0
- run: |
    base=$(git merge-base HEAD "origin/${GITHUB_BASE_REF:-main}")
    python -m flowguard check --static --base "$base"
  shell: bash
'''


# The owner's repositories carry a level-one block whose commands 4.x no longer has.
OWNER_BLOCK = re.compile(r'^# FlowGuard rules for the project agent[ \t]*\r?\n.*?(?=^#{1,6} |^<!-- flowguard:start -->|\Z)',
                         re.M | re.S)
RULES_HEADING = re.compile(r'^## FlowGuard rules for the project agent\s*$', re.M)
RULES_FILES = ('AGENTS.md', 'CLAUDE.md')


def _rules_rewritten(content, rules, newline):
    """(content, held): `content` with its FlowGuard rules block replaced by `rules`, as init writes AGENTS.md and
    CLAUDE.md, and whether it held one: the block between `<!-- flowguard:start -->` and `<!-- flowguard:end -->` (an
    owner's level-one block beside it is removed), a `## FlowGuard rules for the project agent` section or the
    owner's level-one block."""
    if '<!-- flowguard:start -->' in content:
        before, _, rest = content.partition('<!-- flowguard:start -->')
        _, _, after = rest.partition('<!-- flowguard:end -->')
        content = before + rules + (newline + after.lstrip('\r\n') if after.strip() else '')
        return OWNER_BLOCK.sub('', content, count=1), True
    if RULES_HEADING.search(content):
        return re.sub(r'^## FlowGuard rules for the project agent\s*\n.*?(?=^## |\Z)', lambda _: rules + newline,
                      content, count=1, flags=re.M | re.S), True
    if OWNER_BLOCK.search(content):
        return OWNER_BLOCK.sub(lambda match: rules + (newline if match.end() < len(content) else ''), content, count=1), True
    return content, False


def _rules_text(path):
    """((text, bom, encoding), problem) of AGENTS.md or CLAUDE.md as init and the brief read them and init writes
    them back (`common.document_text`, the one route of a project document: a BOM selects UTF-8 or UTF-16, else
    UTF-8); (('', b'', 'utf-8'), '') for a file that does not exist; (None, problem) naming the file and the decoder's
    text when its bytes are no such text."""
    from flowguard.map.common import document_text
    if not path.is_file():
        return ('', b'', 'utf-8'), ''
    return document_text(path.name, path.read_bytes())


def _readable_rules(path):
    """(text, bom, encoding) of AGENTS.md or CLAUDE.md for init (`_rules_text`); raises ValueError with its problem
    when the file is no UTF-8 or UTF-16 text, so init stops there and says which file and why."""
    decoded, problem = _rules_text(path)
    if problem:
        raise ValueError(problem)
    return decoded


def _stale_rules(cfg):
    """(stale, unreadable): the files of RULES_FILES whose FlowGuard rules block is not the one init writes now (the
    marked block with other words, newlines compared normalized, `normalize_newlines`, or a block written without the
    markers, or an owner's level-one block beside it), and the `_rules_text` problem of each file it cannot read, which
    the brief names in a line of its own instead of failing."""
    from flowguard.map.common import normalize_newlines
    stale, unreadable = [], []
    for name in RULES_FILES:
        decoded, problem = _rules_text(cfg.root / name)
        if problem:
            unreadable.append(problem)
            continue
        text = normalize_newlines(decoded[0].encode('utf-8')).decode('utf-8')
        if '<!-- flowguard:start -->' in text:
            block = '<!-- flowguard:start -->' + text.partition('<!-- flowguard:start -->')[2].partition(
                '<!-- flowguard:end -->')[0] + '<!-- flowguard:end -->'
            if block != PROJECT_RULES.rstrip('\n') or OWNER_BLOCK.search(text):
                stale.append(name)
        elif RULES_HEADING.search(text) or OWNER_BLOCK.search(text):
            stale.append(name)
    return stale, unreadable


def init(cfg):
    pyproject = cfg.root / 'pyproject.toml'
    text = pyproject.read_text(encoding='utf-8') if pyproject.is_file() else ''
    if '[tool.flowguard]' not in text:
        text = text.rstrip() + '\n\n[tool.flowguard]\n'
    sentinel = cfg.root / 'tests/test_flowguard_intent.py'
    if sentinel.exists() and sentinel.read_text(encoding='utf-8') != SENTINEL:
        raise ValueError(f'{sentinel}: an existing test needs merging with the intent sentinel')
    pyproject.write_text(_register_plugin(cfg, sentinel.parent / 'conftest.py', text), encoding='utf-8')
    cfg.intent.mkdir(parents=True, exist_ok=True)
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text(SENTINEL, encoding='utf-8')
    from .deps import npm_packages, static_only
    fragment = cfg.root / '.flowguard/ci.yml'
    fragment.parent.mkdir(parents=True, exist_ok=True)
    fragment.write_text(CI_STATIC if static_only(cfg) else CI_PYTEST, encoding='utf-8')
    agents = cfg.root / 'AGENTS.md'
    # Bytes outside the replaced block are kept, including their line endings.
    content, bom, encoding = _readable_rules(agents)
    newline = '\r\n' if '\r\n' in content else '\n'
    rules = PROJECT_RULES.replace('\n', newline)
    packages = npm_packages(cfg.root)
    content, notes = _legacy_agents(content, rules, newline, bool(packages))
    content, held = _rules_rewritten(content, rules, newline)
    if not held:
        content = content.rstrip() + newline + newline + rules
    agents.write_bytes(bom + content.encode(encoding))
    notes += _legacy_instructions(content)
    claude = cfg.root / 'CLAUDE.md'         # a block there is rewritten too; init writes none into it
    if claude.is_file():
        instructions, bom, encoding = _readable_rules(claude)
        ending = '\r\n' if '\r\n' in instructions else '\n'
        rewritten, held = _rules_rewritten(instructions, PROJECT_RULES.replace('\n', ending), ending)
        if held and rewritten != instructions:
            claude.write_bytes(bom + rewritten.encode(encoding))
            notes.append('CLAUDE.md: its FlowGuard rules block is rewritten')
    print('Initialized intent sentinel, pytest plugin, CI fragment and seven project rules.')
    for line in [*notes, *_legacy_binding_lines(cfg, text)]:
        print(line)
    if packages:
        # The generated npm files find this interpreter here; the cache is git-ignored and stays on this machine.
        from flowguard.map.common import cache_dir
        cache_dir(cfg.root)
        (cfg.root / RECORDED_PYTHON).write_text(sys.executable, encoding='utf-8')
    for package in packages:
        print(_npm_check(cfg, package))
    return 0


def _plugin_loaded(cfg, graph):
    """Whether pytest's own configuration (pyproject.toml or a mapped conftest.py) loads the FlowGuard plugin."""
    paths = [cfg.root / 'pyproject.toml'] + [cfg.root / node['file'] for node in graph.nodes(kind='module')
                                             if node['file'] and node['file'].rpartition('/')[2] == 'conftest.py']
    return any('flowguard.intent.plugin' in path.read_text(encoding='utf-8-sig') for path in paths if path.is_file())


def ledger(cfg, operation):
    """`ledger init` records the existing fallbacks as legacy; `ledger check` lists every difference."""
    from . import ledger as fallbacks
    if operation == 'init':
        with closing(build(cfg.root, roots=cfg.roots)) as graph:
            report = fallbacks.init(cfg, graph)
            loaded = _plugin_loaded(cfg, graph)
        if not loaded:
            report.append('pytest does not load the FlowGuard plugin yet, so ordinary tests cannot report the ledger: '
                          'run python -m flowguard init')
        print('\n'.join(report))
        return 0
    from .signals import missing_start
    # A recorded task start this repository lacks compares nothing (`cache.task_start`); the check says so first,
    # with the next step, as the title of pytest, `check` and `check --static` does.
    commit, kind = cache.task_baseline(cfg)
    missing = [missing_start(commit)] if kind == 'missing' else []
    result = _ledger_result(cfg, None if missing else commit)
    if not result.present and not result.red:
        print('\n'.join([*missing, f'FlowGuard ledger: no {fallbacks.LEDGER}; python -m flowguard ledger init starts one from the current code.']))
        return 0
    print('\n'.join([*missing, fallbacks.summary(result), *fallbacks.lines(result), *('not checked: ' + line for line in result.grey)]))
    return int(bool(result.red or result.sections))


def _ledger_result(cfg, baseline):
    """The ledger compared with the current map without running tests (only its deletion when there is none),
    against `baseline` (`owners.baseline`: an explicit `--base`, else the task baseline)."""
    from . import ledger as fallbacks
    if not fallbacks.path(cfg).is_file():
        return fallbacks.absent(cfg, baseline)
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        return fallbacks.evaluate(cfg, graph, baseline=baseline)


def _input_bytes(name):
    """The bytes of a file argument, or of stdin for `-`."""
    return sys.stdin.buffer.read() if name == '-' else Path(name).read_bytes()


def requests(cfg, options):
    if options.operation == 'add' and options.offer is None and (options.picked or options.selected):
        raise MapError('choice_offer_missing: --picked and --selected record the owner\'s pick among options you '
                       'offered; pass those options with --offer FILE, byte for byte as he saw them')
    if options.operation == 'add' and options.offer is not None:
        if not options.picked:
            raise MapError('choice_picked_missing: --offer needs --picked TEXT, the whole text of the option the owner '
                           'picked as the offer spells it (once for each option he picked)')
        if options.offer == '-' and options.file == '-':
            raise MapError('choice_offer_stdin: the reply and the offer cannot both come from stdin; pass the offer '
                           'as a file')
        item = store_choice(cfg.root, _input_bytes(options.file), _input_bytes(options.offer), options.picked,
                            identifier=options.identifier, selected=options.selected, supersedes=options.supersedes)
        # A selected answer is what the interface returned for his pick, no reply of his.
        reply = 'the answer selected' if item['reply'] == 'selected' else "the owner's reply"
        print(f'stored {item["id"]} (choice: {reply} {item["bytes"]} bytes, the agent\'s options '
              f'{item["offer"]["bytes"]} bytes, {len(item["picked"])} picked; sha {item["sha256"][:12]})')
        from .differences import display
        display(f'if this choice sets a continuing rule, add it to .flowguard/rules.toml: [rule.<id>] text = "..." '
                f'source = \'{item["id"]} picked "<words of the picked option>"\''
                + (f' or \'{item["id"]} "<his exact words>"\'' if item['reply'] == 'typed' else ''))
    elif options.operation == 'add':
        raw = _input_bytes(options.file)
        item = store_request(cfg.root, raw, identifier=options.identifier, supersedes=options.supersedes)
        print(f'stored {item["id"]} ({item["kind"]}, sha {item["sha256"][:12]}, {item["bytes"]} bytes)')
        from .differences import display
        display(f'if these words set a continuing rule, add it to .flowguard/rules.toml: [rule.<id>] text = "..." '
                f'source = \'{item["id"]} "<exact words>"\'')
    elif options.operation == 'retire':
        retire_request(cfg.root, options.identifier, note=options.note)
        print(f'retired {options.identifier}: not the owner\'s words')
    else:
        items = owner_words(cfg.root)['rows']
        print(f'requests: {len(items)}; show ID for the stored words')
        for item in items:
            state = ('retired' if item.get('retired') else 'superseded' if item.get('superseded_by') else 'stored')
            if item.get('invalid') or item.get('edited'):
                state = item.get('invalid') or item.get('edited')
            elif item['kind'] == 'choice':
                state += (f' ({len(item["picked"])} picked; '
                          + ('selected with no words of his own)' if item['reply'] == 'selected' else 'his reply typed)'))
            print(f'  {item["id"]} {item["kind"] or "unverified"} {item["received"]} {state}')
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = None
    if '--root' in argv:
        at = argv.index('--root')
        if at + 1 == len(argv):
            raise SystemExit('--root needs a project directory')
        root = argv[at + 1]
        del argv[at:at + 2]
    parser = argparse.ArgumentParser(prog='flowguard')
    parser.add_argument('--version', action='version', version=__version__)
    commands = parser.add_subparsers(dest='command', metavar='{' + ','.join(COMMANDS) + '}')
    def add_parser(name):
        return commands.add_parser(name, **({'help': COMMANDS[name]} if name in COMMANDS else {}))
    show_parser = add_parser('show')
    show_parser.add_argument('query', nargs='?')
    show_parser.add_argument('--draft', action=_RemovedOption, what='show --draft', replacement='python -m flowguard show NAME')
    show_parser.add_argument('--gaps', action=_RemovedOption, what='show --gaps', replacement='python -m flowguard show NAME')
    show_parser.add_argument('--full', action='store_true', help='Include decision sites and full candidate metadata')
    show_parser.add_argument('--last', action='store_true', help='Every line of the last run, with its details')
    check_parser = add_parser('check')
    check_parser.add_argument('--all', action='store_true')
    check_parser.add_argument('--deep', action='store_true', help='Run decision probes and mutation-survival checks')
    check_parser.add_argument('--since', action=_RemovedOption, what='check --since',
                              replacement='python -m flowguard check --base REV')
    check_parser.add_argument('--base', type=cache.base_commit,
                              help='Compare behavior with this commit instead of the remembered session baseline')
    check_parser.add_argument('--static', action='store_true',
                              help='Map checks only, without pytest (any language FlowGuard reads, e.g. TS/JS, Prisma, SQL)')
    check_parser.add_argument('--leads', action=_RemovedOption, nargs=0, what='check --leads',
                              replacement='python -m flowguard show --last')
    add_parser('init')
    add_parser('new-task')
    add_parser('docs')
    known_parser = add_parser('known')
    known_operations = known_parser.add_subparsers(dest='operation', required=True)
    known_add = known_operations.add_parser('add', help="Append one entry; its sites are the places of the last run's lines of FINDING")
    known_add.add_argument('finding', help="a finding's name as show --last lists it, or - for a matter no check finds")
    from .sources import ACTS
    known_add.add_argument('--act', required=True, choices=ACTS)
    known_add.add_argument('--why', required=True, help='what the matter is')
    known_add.add_argument('--ask', default='', help='the question for the owner (with --act ask)')
    known_add.add_argument('--id', dest='identifier', default='', help="the entry's id; the finding's name by default")
    known_add.add_argument('--site', action='append', default=[], help='path:symbol, instead of the finding\'s places')
    ledger_parser = add_parser('ledger')
    ledger_operations = ledger_parser.add_subparsers(dest='operation', required=True)
    ledger_operations.add_parser('init', help='Record every existing fallback as legacy')
    ledger_operations.add_parser('check', help='List every difference between the ledger and the code')
    req_parser = add_parser('req')
    operations = req_parser.add_subparsers(dest='operation', required=True)
    add = operations.add_parser('add')
    add.add_argument('file')
    add.add_argument('--id', dest='identifier')
    add.add_argument('--kind', action=_KindOption, what='req add --kind {value}',
                     replacement='python -m flowguard req add FILE --id R<n>')
    add.add_argument('--supersedes', action='append', default=[])
    add.add_argument('--offer', metavar='FILE', help="the options you offered the owner, byte for byte: FILE is then his "
                     "reply to them, stored with the options as your words")
    add.add_argument('--picked', action='append', default=[], metavar='TEXT',
                     help='with --offer: the whole text of an option he picked, as the offer spells it (once for each)')
    add.add_argument('--selected', action='store_true',
                     help='with --offer: he picked without typing; FILE is the answer as the interface returned it')
    operations.add_parser('list')
    retire = operations.add_parser('retire')
    retire.add_argument('identifier')
    retire.add_argument('--not-owner', action='store_true', required=True)
    retire.add_argument('--note')
    try:
        if argv and argv[0] in REMOVED_COMMANDS:
            raise Removed(REMOVED_COMMANDS[argv[0]], NEW_COMMANDS)
        if argv and argv[0] in EARLIER_COMMANDS:
            _, release, replacement = EARLIER_COMMANDS[argv[0]]
            raise Removed(argv[0], replacement, release)
        options = parser.parse_args(argv)
        cfg = load_config(root or find_root())
        if options.command == 'show':
            return show(cfg, options.query, full=options.full, last=options.last)
        if options.command == 'check' and options.static:
            if options.deep:
                raise ValueError('check --static runs no tests: --deep needs the pytest check')
            return static_check(cfg, everything=options.all, base=options.base)
        if options.command == 'check':
            return check(cfg, everything=options.all, deep=options.deep, base=options.base)
        if options.command == 'init':
            return init(cfg)
        if options.command == 'docs':
            return write_docs(cfg)
        if options.command == 'known':
            return add_known_entry(cfg, options)
        if options.command == 'ledger':
            return ledger(cfg, options.operation)
        if options.command == 'req':
            return requests(cfg, options)
        return screen(cfg, new_task=options.command == 'new-task')
    except BrokenPipeError:
        raise               # The command entry exits quietly when the consumer closes stdout.
    except (ValueError, MapError, OSError) as error:
        print(f'flowguard: {error}', file=sys.stderr)
        return 2
