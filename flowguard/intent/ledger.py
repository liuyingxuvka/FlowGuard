"""The fallback ledger: every handler that can end without raising, counted per function, with why it may
stay and the written rule it serves (`.flowguard/ledger.toml`).

The facts are the map's own: `handlers()` (an `except` that does not raise on every path, also when only one
branch raises, `contextlib.suppress` under any alias, a `return`/`break`/`continue` inside `finally`, an
`__exit__` that may return a true value) and the resolved `calls()` of the warning filters. A key is
`file:function:caught`, the same key the owner's handler lists use; `<module>` stands for code outside any
function and `BARE` for a bare `except`. The count in the ledger must equal the count in the code: one more
is red until it is listed, one fewer or a vanished key is red until the entry is corrected. Each entry states
what the handler does and why it may stay (at least eight words) and cites a written rule as a file and a
sentence that file must contain; the sentence is checked on every run.

Bare `except`, `except Exception`/`BaseException`, `contextlib.suppress`, warning filters, an exit from
`finally` and an `__exit__` that may return true cannot be listed: they are red until the code changes.
`ledger init` records the existing handlers as legacy (`rule = "旧账"`), which also covers those forms; a
legacy entry can only shrink, never grow, compared with the ledger at the task's baseline commit and with
the record `ledger init` kept. Deleting a ledger that the baseline commit still has is red as well.

Other languages supply handler rows through their map reader with the same fields (`node`, `file`, `line`,
`kind`, `type`, `non_raising`, and for `except`/`catch` rows `ends`: how the body ends); the language comes from
the file suffix. `check --all` lists the legacy entries of production code whose handlers carry on with a
substitute value, only log or are empty (`open_legacy`). A file whose reader cannot supply
handlers, or that does not parse, is listed as not checked; it is never read as having no handlers.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
import tomllib

from flowguard.map.common import MapError, git_blob, glob_match
from flowguard.structure.readers.registry import ECMA, language_for
from .deprecation import warn

LEDGER = '.flowguard/ledger.toml'
INIT_RECORD = 'ledger-init.json'
LEGACY_RULE = '旧账'
LEGACY_REASON = 'Legacy, unreviewed: this fallback existed when ledger init recorded it; when editing it, explain what it does, why it may remain, and the written rule it serves'
PLACEHOLDER_REASON = 'Replace with the real reason: what this handler does and why it may remain (at least 8 words)'
PLACEHOLDER_RULE = dict(file='file containing the written rule', text='an exact sentence that must occur in that file')
_OLD_PLACEHOLDER_REASON = '换成真实的理由：这处做了什么、为什么可以留（不少于 8 个词）'
_OLD_PLACEHOLDER_RULE = ('成文规矩所在的文件', '该文件里必须出现的一句话')
MIN_WORDS = 8
FIELDS = {'count', 'reason', 'rule'}
UNVERIFIED = 'unverified'
STRUCTURE = 'structure'         # [structure."name"]: the owner's decision on one structure problem
SECTIONS = frozenset({UNVERIFIED, STRUCTURE})  # Named sections beside the handler entries.
PLACEHOLDER_UNVERIFIED = 'Replace with the real reason: why this judgment is not replayed and what checks it instead (at least 8 words)'
_OLD_PLACEHOLDER_UNVERIFIED = '换成真实的理由：为什么这个判断不再回放、由什么守住它（不少于 8 个词）'
WARNING_FILTERS = {'warnings.simplefilter', 'warnings.filterwarnings', 'warnings.catch_warnings',
                   'pytest.mark.filterwarnings'}
BROAD = {'Exception', 'BaseException', 'builtins.Exception', 'builtins.BaseException'}
CJK = re.compile(r'[぀-ヿ㐀-䶿一-鿿豈-﫿가-힯]')
HEADER = f"""# FlowGuard fallback ledger: each entry records a function's handler that can end without raising; keys are "file:function:caught type".
# count is this function's number of handlers of this kind; reason states what they do and why they may remain (at least {MIN_WORDS} words);
# rule points to a written rule: {{ file = "file", text = "an exact sentence that must occur in that file" }}; every test session checks that the sentence remains.
# New handlers, changed counts, missing code or a missing rule sentence fail pytest. Entries with rule = "{LEGACY_RULE}" are recorded by ledger init and can only decrease.
# Bare except, except Exception/BaseException, contextlib.suppress, warning filters, return/break/continue in finally,
# and __exit__ methods that may return a truthy value cannot be newly registered: fix the code.
"""
# A handler list a project already keeps as a test: string keys "path.py:function:caught" next to an AST
# handler scan. Recognised by content, never by file name.
OWN_LIST_KEY = re.compile(r'''["'][\w./-]*\.py:[A-Za-z_<][\w.<>]*:[^"'\n]+["']''')


@dataclass(frozen=True)
class Fallback:
    """One place where an error can end without being raised."""
    key: str
    file: str
    function: str
    caught: str
    line: int
    kind: str
    language: str
    refused: str        # why this form can never be listed; empty when it may be listed with a reason
    ends: str           # how its body ends (readers.common.ENDINGS)


# How the other forms end: `contextlib.suppress`, a warning filter and an `__exit__` that returns true drop the
# error without a word; a `return` in `finally` replaces it with its value.
FORM_ENDS = {'suppress': 'empty', 'warning_filter': 'empty', 'exit_method': 'empty', 'finally': 'substitute'}
# The legacy entries `--all` lists, the most worrying first: production code that carries on with a substitute
# value, only logs, or says nothing.
OPEN_ENDS = {'substitute': 'returns or substitutes another value', 'log': 'only logs', 'empty': 'empty body'}


@dataclass(frozen=True)
class Finding:
    text: str
    fix: tuple[str, ...] = ()


@dataclass
class Result:
    present: bool
    entries: int = 0
    legacy: int = 0
    fallbacks: int = 0
    red: list[Finding] = field(default_factory=list)
    grey: list[str] = field(default_factory=list)
    # [structure] entries with fields of a later FlowGuard: unverified in a test run, also among `grey`
    later: list[str] = field(default_factory=list)


def path(cfg) -> Path:
    return cfg.root / LEDGER


def _quote(text) -> str:
    """A TOML basic string; JSON's escapes are TOML's, except that TOML also refuses a raw DEL."""
    return json.dumps(str(text), ensure_ascii=False).replace('\x7f', '\\u007f')


def _scope(cfg):
    """The files the ledger covers: every mapped source file unless [tool.flowguard.ledger] narrows it."""
    def covers(pattern, file):
        pattern = pattern.strip('/')
        return glob_match(file, pattern) or glob_match(file, pattern + '/**')
    return lambda file: (any(covers(pattern, file) for pattern in cfg.ledger_paths)
                         and not any(covers(pattern, file) for pattern in cfg.ledger_exclude))


def _python_refusal(kind, caught):
    if kind == 'except':
        if caught == 'BARE':
            return 'bare except swallows every error, including KeyboardInterrupt'
        types = ast.parse(caught, mode='eval').body
        names = {ast.unparse(item) for item in (types.elts if isinstance(types, ast.Tuple) else [types])}
        if names & BROAD:
            return 'catching ' + ', '.join(sorted(names & BROAD)) + ' hides unrelated programming errors together'
        return ''
    return {'suppress': 'contextlib.suppress silently swallows errors',
            'warning_filter': 'a warning filter hides warnings',
            'finally': 'return/break/continue in finally discards an active error',
            'exit_method': '__exit__ may return a truthy value and swallow errors from the with block'}[kind]


FIXES = {'except': 'catch specific error types, or re-raise on every path',
         'suppress': 'use try/except with specific error types and record the reason, or let the error propagate',
         'warning_filter': 'remove the filter; use pytest.warns to assert warnings in tests',
         'finally': 'move return/break/continue outside finally',
         'exit_method': 'make __exit__ return None or False'}


def fallbacks(cfg, graph):
    """({key: [Fallback, ...]}, {file: why it was not checked}) for the ledger's scope."""
    covered = _scope(cfg)
    graph.reset_query_coverage()
    rows = [row for row in graph.handlers() if covered(row['file']) and row['non_raising']]
    rows += [dict(row, kind='warning_filter', type=row['resolved']) for row in graph.python_calls()
             if row['resolved'] in WARNING_FILTERS and language_for(row['file']) == 'python' and covered(row['file'])]
    unread = {file: issue['reason'] for issue in graph.query_coverage()['issues']
              for file in issue['files'] if covered(file)}
    found = {}
    for row in sorted(rows, key=lambda row: (row['file'], row['line'])):
        language = language_for(row['file'])
        caught = row['type'] or ('BARE' if language == 'python' else row['kind'])
        # A JS/TS row names its enclosing named function, so an anonymous callback's line never enters the key.
        function = row['function'] if language in ECMA else row['node'].partition(':')[2] or '<module>'
        key = f"{row['file']}:{function}:{caught}"
        refused = _python_refusal(row['kind'], caught) if language == 'python' else ''
        ends = row['ends'] if row['kind'] in ('except', 'catch') else FORM_ENDS[row['kind']]
        found.setdefault(key, []).append(Fallback(key, row['file'], function, caught, row['line'], row['kind'],
                                                   language, refused, ends))
    return found, unread


def open_legacy(cfg, graph):
    """The `--all` lines of legacy entries (rule = "旧账", never reviewed) in production code whose handlers do
    not hand the error on, by how their bodies end (OPEN_ENDS): an entry counts once, by its most worrying
    handler. A ledger that does not parse lists nothing here; its red lines say why."""
    ledger = path(cfg)
    if not ledger.is_file():
        return []
    entries, _, malformed = parse(ledger.read_text(encoding='utf-8-sig'))
    if malformed is None:
        return []
    found, _ = fallbacks(cfg, graph)
    tests = {file for (file,) in graph.con.execute('SELECT path FROM file WHERE is_test = 1')}
    order = list(OPEN_ENDS)
    groups = {}
    for key, entry in sorted(entries.items()):
        items = found.get(key, [])
        if not entry.legacy or not items or items[0].file in tests or graph.archived(items[0].file):
            continue
        ends = [item.ends for item in items if item.ends in OPEN_ENDS]
        if ends:
            groups.setdefault(min(ends, key=order.index), []).append(items)
    if not groups:
        return []
    total = sum(len(group) for group in groups.values())
    lines = [f"""{total} legacy production handlers do not propagate errors ({LEDGER}, rule = "{LEGACY_RULE}", unreviewed; grouped by handler body):"""]
    for ends in order:
        if ends in groups:
            lines.append(f"""   {OPEN_ENDS[ends]}: {len(groups[ends])} handlers:"""
                         + ', '.join(f'{_where(items)} {items[0].function}' for items in groups[ends]))
    lines.append('   Next: review each handler. If callers need the error, let it raise or propagate; otherwise make reason explain what it does, why it may remain, and point rule to a written rule')
    return lines


def words(text) -> int:
    """Words separated by white space; two CJK characters count as one word."""
    cjk = len(CJK.findall(text))
    latin = [token for token in CJK.sub(' ', text).split() if re.search(r'\w', token)]
    return len(latin) + math.ceil(cjk / 2)


@dataclass(frozen=True)
class Entry:
    key: str
    count: int
    reason: str
    rule: object        # LEGACY_RULE or (file, text)

    @property
    def legacy(self):
        return self.rule == LEGACY_RULE


def parse(text):
    """({key: Entry}, [Finding], {malformed key}) from the ledger's text; every malformed entry is a red finding."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        return {}, [Finding(f"""Cannot read fallback ledger {LEDGER}: {error}""", ("correct this file's TOML syntax",))], None
    entries, red, malformed = {}, [], set()
    for key, value in data.items():
        if key == UNVERIFIED:
            red.extend(_unverified_section(value)[1])
            continue
        if key in SECTIONS:
            continue            # [structure] decisions are read and checked by structure_decisions
        if key.count(':') < 2 or not isinstance(value, dict):
            red.append(Finding(f"""Fallback ledger item {_quote(key)} is not an entry: the key must be "file:function:caught type" and the value a table""",
                               ('remove it, or write count, reason and rule below ["file:function:caught type"]',)))
            continue
        problems = [f"""unknown field {name}""" for name in sorted(set(value) - FIELDS)]
        problems += [f"""missing {name}""" for name in sorted(FIELDS - set(value))]
        count, reason, rule = value.get('count'), value.get('reason'), value.get('rule')
        if 'count' in value and (type(count) is not int or count < 1):
            problems.append('count must be a positive integer')
        if 'reason' in value:
            if not isinstance(reason, str):
                problems.append('reason must be a string')
            elif reason.strip() in (PLACEHOLDER_REASON, _OLD_PLACEHOLDER_REASON):
                problems.append('reason is still a placeholder: explain what this handler does and why it may remain')
            elif words(reason) < MIN_WORDS:
                problems.append(f"""reason has {words(reason)} words; at least {MIN_WORDS} are required: explain what this handler does and why it may remain""")
        if 'rule' in value:
            if rule == LEGACY_RULE:
                pass
            elif (not isinstance(rule, dict) or set(rule) != {'file', 'text'}
                  or not all(isinstance(rule[name], str) and rule[name].strip() for name in ('file', 'text'))):
                problems.append('rule must be { file = "file", text = "an exact sentence that must occur in that file" }')
            else:
                rule = (rule['file'], rule['text'])
        if problems:
            red.append(Finding(f"""Fallback ledger entry {_quote(key)}: """ + '; '.join(problems),
                               ('correct this entry following the instructions at the start of ledger.toml',)))
            malformed.add(key)
            continue
        entries[key] = Entry(key, count, reason, rule)
    return entries, red, malformed


def _unverified_section(value):
    """({anchor or rule name: reason}, [Finding]) of the [unverified] section: observations that the baseline
    code makes and the current code cannot, kept unverified on purpose. Each reason has at least eight words."""
    warn('ledger [unverified]')
    if not isinstance(value, dict):
        return {}, [Finding(f"""Fallback ledger [{UNVERIFIED}] must be a table with one name = "reason" per line""",
                            (f"""write one anchor or rule name = "reason" per line below [{UNVERIFIED}]""",))]
    entries, red = {}, []
    for name, reason in value.items():
        if not isinstance(reason, str):
            problem = 'reason must be a string'
        elif reason.strip() in (PLACEHOLDER_UNVERIFIED, _OLD_PLACEHOLDER_UNVERIFIED):
            problem = 'reason is still a placeholder: explain why replay is unavailable and what checks it instead'
        elif words(reason) < MIN_WORDS:
            problem = f"""reason has {words(reason)} words; at least {MIN_WORDS} are required: explain why replay is unavailable and what checks it instead"""
        else:
            entries[name] = reason
            continue
        red.append(Finding(f"""Fallback ledger [{UNVERIFIED}] item {_quote(name)}: {problem}""", ('correct this line',)))
    return entries, red


def unverified(cfg):
    """({name: reason}, [Finding]) of the ledger's [unverified] section; no ledger lists nothing."""
    ledger = path(cfg)
    if not ledger.is_file():
        return {}, []
    try:
        data = tomllib.loads(ledger.read_text(encoding='utf-8-sig'))
    except tomllib.TOMLDecodeError:
        return {}, []           # parse() reports the unreadable ledger once, as red.
    return _unverified_section(data[UNVERIFIED]) if UNVERIFIED in data else ({}, [])


def _sentence_problem(cfg, rule, texts):
    relative, sentence = rule
    if (relative, sentence) in ((PLACEHOLDER_RULE['file'], PLACEHOLDER_RULE['text']), _OLD_PLACEHOLDER_RULE):
        return 'rule is still a placeholder: name the file containing the written rule and quote an exact sentence'
    target = (cfg.root / relative).resolve()
    if Path(relative).is_absolute() or not target.is_relative_to(cfg.root):
        return f"""rule file {relative} is outside the project"""
    if target == path(cfg).resolve():
        return 'rule cannot refer to the ledger itself'
    if not target.is_file():
        return f"""rule file {relative} does not exist"""
    if relative not in texts:
        texts[relative] = ' '.join(target.read_text(encoding='utf-8-sig').split())
    if ' '.join(sentence.split()) not in texts[relative]:
        return f"""rule sentence {_quote(sentence)} is missing from {relative}"""
    return ''


def _entry_lines(key, count, reason=PLACEHOLDER_REASON, rule=None):
    rule = PLACEHOLDER_RULE if rule is None else rule
    shown = _quote(rule) if isinstance(rule, str) else '{ file = ' + _quote(rule['file']) + ', text = ' + _quote(rule['text']) + ' }'
    return ['[' + _quote(key) + ']', f'count = {count}', 'reason = ' + _quote(reason), 'rule = ' + shown]


def _where(items):
    lines = [str(item.line) for item in items]
    return items[0].file + ':' + ','.join(lines)


def _what(item):
    return {'except': f'except {item.caught}', 'suppress': item.caught, 'warning_filter': item.caught + '()',
            'finally': 'return/break/continue in finally', 'exit_method': '__exit__ returns a truthy value'}.get(item.kind, f'{item.kind} {item.caught}')


def _baseline_ledger(cfg, baseline):
    """(the ledger's bytes at the baseline commit or None, why that commit could not be read)."""
    if not baseline:
        return None, ''
    try:
        return git_blob(cfg.root, baseline, LEDGER), ''
    except MapError as error:
        # A baseline commit this clone does not have vouches for nothing; the caller reports why.
        return None, str(error)


def absent(cfg, baseline) -> Result:
    """No ledger now: red when the baseline commit still has one, since deleting it would silence every entry."""
    before, _ = _baseline_ledger(cfg, baseline)
    return Result(present=False) if before is None else removed(baseline)


def removed(baseline) -> Result:
    return Result(present=False, red=[Finding(
        f"""Fallback ledger {LEDGER} existed at the baseline but is now missing: deleting the ledger cannot clear a fallback failure""",
        (f"""restore it with git checkout {baseline[:12]} -- {LEDGER}, then correct the code or entries identified by red lines; if the ledger is intentionally retired, commit its removal and start a new task with python -m flowguard new-task""",))])


def _legacy_reference(cfg, baseline, notes):
    """{key: count} of legacy entries that `ledger init` recorded or the baseline ledger holds; None when neither is available."""
    reference, available = {}, False
    record = cfg.cache / INIT_RECORD
    if record.is_file():
        try:
            saved = json.loads(record.read_text(encoding='utf-8'))
        except json.JSONDecodeError as error:
            raise MapError(f'{record}: the ledger init record cannot be read: {error}; delete it to rely on the baseline commit') from error
        reference.update(saved['legacy'])
        available = True
    if baseline:
        raw, why = _baseline_ledger(cfg, baseline)
        if why:
            notes.append(f"""Cannot read baseline commit {baseline[:12]}: {why}""")
        entries, _, malformed = parse(raw.decode('utf-8-sig')) if raw is not None else ({}, [], None)
        if malformed is not None:           # A baseline ledger that does not parse vouches for nothing.
            for key, entry in entries.items():
                if entry.legacy:
                    reference[key] = max(reference.get(key, 0), entry.count)
            available = True
    return reference if available else None


def evaluate(cfg, graph, *, baseline=None) -> Result:
    """Compare the ledger with the code. `baseline` is the task's baseline commit (None outside Git)."""
    ledger = path(cfg)
    if not ledger.is_file():
        return absent(cfg, baseline)
    entries, red, malformed = parse(ledger.read_text(encoding='utf-8-sig'))
    _, structure_red, later = structure_decisions(cfg)
    result = Result(present=True, entries=len(entries), legacy=sum(entry.legacy for entry in entries.values()),
                    red=red + structure_red, grey=list(later), later=later)
    if malformed is None:
        return result                       # An unreadable ledger is compared with nothing until it is corrected.
    found, unread = fallbacks(cfg, graph)
    result.fallbacks = sum(len(items) for items in found.values())
    covered, texts = _scope(cfg), {}
    legacy = [entry for entry in entries.values() if entry.legacy]
    notes = []
    reference = _legacy_reference(cfg, baseline, notes) if legacy else {}
    if reference is None:
        result.grey.append(f"""{len(legacy)} legacy entries are unverified: the baseline contains neither a ledger nor a ledger init record"""
                           + ''.join('; ' + note for note in notes))
    for key in sorted((set(found) | set(entries)) - malformed):
        items, entry = found.get(key, []), entries.get(key)
        file = key.partition(':')[0]
        listed = entry.count if entry else 0
        if entry and entry.legacy and reference is not None and entry.count > reference.get(key, 0):
            result.red.append(Finding(
                f"""Only ledger init may record legacy entries: {_quote(key)} claims {entry.count} legacy handlers, but ledger init and the baseline record only {reference.get(key, 0)}""",
                ('legacy entries cannot increase: supply the real reason and rule' + ('' if not items or not items[0].refused else '; this form cannot be registered; fix the code'),)))
            continue
        if not items:
            if file in unread:
                result.grey.append(f"""{key} is unverified: {unread[file]}""")
            elif not covered(file):
                result.red.append(Finding(f"""File for fallback ledger entry {_quote(key)} is outside the ledger scan scope""",
                                          ('remove this entry or correct [tool.flowguard.ledger] paths/exclude',)))
            else:
                result.red.append(Finding(f"""Code disappeared: ledger entry {_quote(key)} records {listed} handlers, but none remain in the code""",
                                          ('remove this entry from .flowguard/ledger.toml',)))
            continue
        first = items[0]
        if first.refused and not (entry and entry.legacy and len(items) <= listed):
            red = f"""Form cannot be registered: {_where(items)} {_what(first)} ({key}): {first.refused}"""
            if entry and not entry.legacy:
                red += '; a ledger entry cannot clear this failure'
            result.red.append(Finding(red, (FIXES[first.kind] + ('; then remove this ledger entry' if entry else ''),)))
            continue
        if entry and not entry.legacy:
            problem = _sentence_problem(cfg, entry.rule, texts)
            if problem:
                result.red.append(Finding(f"""Fallback ledger entry {_quote(key)}: {problem}""",
                                          ('quote an exact written rule that occurs in that file',)))
        if len(items) > listed:
            if not entry:
                text = f"""New unregistered fallback: {_where(items)} {_what(first)} can end without raising"""
            elif entry.legacy:
                text = f"""New fallback: {_where(items)} {_what(first)} now has {len(items)} handlers; the legacy entry records only {listed}"""
            else:
                text = f"""More fallbacks: {_where(items)} {_what(first)} now has {len(items)} handlers; the ledger records {listed}"""
            fix = ['to retain this handler, in .flowguard/ledger.toml ' + ('write this entry (replace the old entry):' if entry else 'add:'),
                   *_entry_lines(key, len(items),
                                 rule=None if not entry or entry.legacy else dict(file=entry.rule[0], text=entry.rule[1]),
                                 reason=PLACEHOLDER_REASON if not entry or entry.legacy else entry.reason),
                   'otherwise change the code to let the error propagate']
            result.red.append(Finding(text, tuple(fix)))
        elif len(items) < listed:
            result.red.append(Finding(f"""Fewer fallbacks: {_quote(key)} records {listed} handlers, but only {len(items)} remain ({_where(items)})""",
                                      (f"""change this entry to count = {len(items)}""",)))
    for file, reason in sorted(unread.items()):
        if not any(key.partition(':')[0] == file for key in entries):
            result.grey.append(f"""{file} is unverified: {reason}""")
    return result


@dataclass(frozen=True)
class Decision:
    """The owner's decision on one structure problem, by its stable name (`writers:Model.field`)."""
    name: str
    decision: str
    source: object      # 'R<n>' (stored owner words) or (file, sentence) like an entry's rule


STRUCTURE_FIELDS = {'decision', 'source'}


def structure_entry(name, decision="Replace with the owner's decision: who owns this and why (at least 8 words)", source='R<n>'):
    """The `[structure]` lines to copy for one problem."""
    shown = _quote(source) if isinstance(source, str) else '{ file = ' + _quote(source[0]) + ', text = ' + _quote(source[1]) + ' }'
    return [f'[{STRUCTURE}.' + _quote(name) + ']', 'decision = ' + _quote(decision), 'source = ' + shown]


def _near(word, known):
    """Whether `word` is `known` with one or two letters wrong, missing or extra (`decison`, `sorce`)."""
    previous = list(range(len(known) + 1))
    for index, letter in enumerate(word, 1):
        current = [index]
        for position, other in enumerate(known, 1):
            current.append(min(previous[position] + 1, current[-1] + 1, previous[position - 1] + (letter != other)))
        previous = current
    return previous[-1] <= 2


def structure_decisions(cfg):
    """({name: Decision}, [Finding], [str]): the `[structure]` section of the ledger. A decision has at least eight
    words and a source: `R<n>`, owner words stored with `req add`, or a written rule `{ file, text }` whose
    sentence the file still contains. A malformed decision is red and silences nothing, and so is a field one or
    two letters from decision or source when that one is missing (`decison`). An entry with another field this
    version does not know (a later FlowGuard writes `status`, `sites`, `why`, ...; `sources` beside `source`) is not
    judged: it is one unverified line (the third list), not red, which also says what is wrong with its decision or
    source, and it closes nothing either."""
    ledger = path(cfg)
    if not ledger.is_file():
        return {}, [], []
    try:
        data = tomllib.loads(ledger.read_text(encoding='utf-8-sig'))
    except tomllib.TOMLDecodeError:
        return {}, [], []      # parse() already reports the unreadable ledger as red with its error
    if STRUCTURE in data:
        # A decision closes a structure problem; from 4.3 a known.toml entry does (act "ignore" or "leave").
        warn('ledger [structure]', '[known.<id>] in .flowguard/known.toml with act = "ignore" or "leave"')
    section = data.get(STRUCTURE, {})
    if not isinstance(section, dict):
        return {}, [Finding(f"""{LEDGER} [{STRUCTURE}] must be a table: write decision and source below [{STRUCTURE}."issue-name"]""",
                            ('correct this section',))], []
    from flowguard.map.requests import owner_word
    decisions, red, later, texts = {}, [], [], {}
    for name, value in section.items():
        if not isinstance(value, dict):
            red.append(Finding(f"""[{STRUCTURE}] item {_quote(name)} is not an entry: its value must be a table""", ('correct it using the structure_entry format',)))
            continue
        unknown = sorted(set(value) - STRUCTURE_FIELDS)
        # A field one or two letters from decision or source, while that field is missing, is misspelt: the entry is
        # judged as written. Beside the field it is near (`sources` beside `source`) it is another field.
        misspelt = {key: known for key in unknown for known in sorted(STRUCTURE_FIELDS - set(value)) if _near(key, known)}
        newer = [key for key in unknown if key not in misspelt and not misspelt]
        problems = [f"""unknown field {key} (did you mean {known}?)""" for key, known in misspelt.items()]
        problems += [f"""unknown field {key}""" for key in unknown if key not in misspelt and misspelt]
        problems += [f"""missing {key}""" for key in sorted(STRUCTURE_FIELDS - set(value)) if not newer]
        decision, source = value.get('decision'), value.get('source')
        if 'decision' in value and (not isinstance(decision, str) or words(decision) < MIN_WORDS):
            problems.append(f"""decision needs at least {MIN_WORDS} words: explain what the owner decided and why""")
        if isinstance(source, str):
            entry = owner_word(cfg.root, source) if re.fullmatch(r'R\d+', source) else None
            if entry is None:
                problems.append(f"""source {_quote(source)} is not stored owner wording: first store the original words with python -m flowguard req add, then use their R identifier""")
            elif entry.get('edited') or entry.get('invalid') or entry.get('retired'):
                problems.append(f"""source {source} has changed or been retired and cannot be used as a source""")
        elif isinstance(source, dict) and set(source) == {'file', 'text'} and all(isinstance(source[k], str) and source[k].strip() for k in source):
            if problem := _sentence_problem(cfg, (source['file'], source['text']), texts):
                problems.append(problem.replace('rule', 'source'))
        elif 'source' in value:
            problems.append('source must be "R<n>" or { file = "file", text = "an exact sentence that must occur in that file" }')
        if newer:
            # Fields of a later FlowGuard: the entry is not judged and closes nothing; what is wrong with the fields
            # this version knows is said on its unverified line.
            later.append(f"""Structure entry [{STRUCTURE}.{_quote(name)}] has fields this version does not recognize: {", ".join(newer)}; these fields require a newer FlowGuard; upgrade before reviewing them. This entry closes no issue in the current version"""
                         + ''.join('; ' + problem for problem in problems))
            continue
        if problems:
            red.append(Finding(f"""Structure decision [{STRUCTURE}.{_quote(name)}]: """ + '; '.join(problems), ('correct this entry following the ledger.toml format',)))
            continue
        decisions[name] = Decision(name, decision, source if isinstance(source, str) else (source['file'], source['text']))
    return decisions, red, later


def lines(result) -> list[str]:
    """The red findings in full, each followed by its next step, which can be copied as written."""
    out = []
    for finding in result.red:
        out.append('red: ' + finding.text)
        out.extend('    ' + line for line in finding.fix)
    return out


def summary(result) -> str:
    return (f"""FlowGuard fallback ledger: {result.entries} entries ({result.legacy} legacy), {result.fallbacks} code handlers; {len(result.red)} red, {len(result.grey)} unverified""")


def own_list_tests(cfg, graph):
    """Project files that already keep their own handler list (keys "file.py:function:caught" beside an AST
    handler scan). Recognised by content."""
    candidates = sorted({row['file'] for row in graph.calls(include_reads=True, language='python')
                         if row['resolved'] == 'ast.ExceptHandler'})
    return [file for file in candidates
            if OWN_LIST_KEY.search((cfg.root / file).read_text(encoding='utf-8-sig'))]


def render_ledger(found) -> str:
    out = [HEADER]
    for key in sorted(found):
        out.append('\n'.join(_entry_lines(key, len(found[key]), reason=LEGACY_REASON, rule=LEGACY_RULE)) + '\n')
    return '\n'.join(out)


def init(cfg, graph):
    """Record every existing fallback as legacy; refuse a second ledger or a second handler list."""
    ledger = path(cfg)
    if ledger.exists():
        raise ValueError(f'{LEDGER} already exists; edit its entries instead of starting it again')
    own = own_list_tests(cfg, graph)
    if own:
        raise ValueError(f'this project already keeps its own handler list in {", ".join(own)}; '
                         'the ledger would be a second list for the same job. Choose one: keep that test '
                         '(no ledger is needed), or move its entries into the ledger and delete the test before ledger init')
    found, unread = fallbacks(cfg, graph)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(render_ledger(found), encoding='utf-8', newline='\n')
    cfg.cache.mkdir(parents=True, exist_ok=True)
    (cfg.cache / INIT_RECORD).write_text(json.dumps(dict(legacy={key: len(items) for key, items in found.items()}),
                                                    ensure_ascii=False, sort_keys=True), encoding='utf-8')
    refused = sum(1 for items in found.values() if items[0].refused)
    report = [f"""FlowGuard fallback ledger created: {LEDGER}, {len(found)} legacy entries, {sum(map(len, found.values()))} handlers ({refused} forms cannot be newly registered). New handlers, changed counts and missing code will fail pytest; commit this file."""]
    report += [f"""Unverified: {file}: {reason}""" for file, reason in sorted(unread.items())]
    return report
