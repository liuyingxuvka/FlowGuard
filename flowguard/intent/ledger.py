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
`kind`, `type`, `non_raising`); the language comes from the file suffix. A file whose reader cannot supply
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
from flowguard.structure.readers.registry import language_for

LEDGER = '.flowguard/ledger.toml'
INIT_RECORD = 'ledger-init.json'
LEGACY_RULE = '旧账'
LEGACY_REASON = '旧账，未审：ledger init 记下时代码里已有这处兜底；改到这里时写明它做了什么、为什么可以留，并指向成文规矩'
PLACEHOLDER_REASON = '换成真实的理由：这处做了什么、为什么可以留（不少于 8 个词）'
PLACEHOLDER_RULE = dict(file='成文规矩所在的文件', text='该文件里必须出现的一句话')
MIN_WORDS = 8
FIELDS = {'count', 'reason', 'rule'}
SECTIONS = frozenset()          # Named sections a later part of the ledger may add; none are read yet.
WARNING_FILTERS = {'warnings.simplefilter', 'warnings.filterwarnings', 'warnings.catch_warnings',
                   'pytest.mark.filterwarnings'}
BROAD = {'Exception', 'BaseException', 'builtins.Exception', 'builtins.BaseException'}
CJK = re.compile(r'[぀-ヿ㐀-䶿一-鿿豈-﫿가-힯]')
HEADER = f'''# FlowGuard 兜底账本：每条记一个函数里能不抛出就结束的异常处理，键是"文件:函数:捕获的类型"。
# count 是这个函数里这种处理的处数；reason 写它做了什么、为什么可以留（不少于 {MIN_WORDS} 个词）；
# rule 指向成文规矩：{{ file = "文件", text = "该文件里必须出现的一句话" }}，每次测试都核对这句话还在。
# 新增、数量变化、代码消失、那句话找不到，都会让 pytest 失败。rule = "{LEGACY_RULE}" 的条目由 ledger init 记下，只能减少。
# 裸 except、except Exception/BaseException、contextlib.suppress、警告过滤、finally 里的 return/break/continue
# 和可能返回真值的 __exit__ 不能新增登记：改代码。
'''
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
            return '裸 except 吞掉所有错误，连 KeyboardInterrupt 也吞掉'
        types = ast.parse(caught, mode='eval').body
        names = {ast.unparse(item) for item in (types.elts if isinstance(types, ast.Tuple) else [types])}
        if names & BROAD:
            return '捕获 ' + '、'.join(sorted(names & BROAD)) + ' 会把各种程序错误一起藏起来'
        return ''
    return {'suppress': 'contextlib.suppress 不留痕迹地吞掉错误',
            'warning_filter': '警告过滤让警告看不见',
            'finally': 'finally 里的 return/break/continue 会丢掉正在抛出的错误',
            'exit_method': '__exit__ 可能返回真值，会吞掉 with 块里的错误'}[kind]


FIXES = {'except': '只捕获具体的错误类型，或者让每条路径都重新抛出',
         'suppress': '改成 try/except 具体的错误类型并登记理由，或者让错误抛出',
         'warning_filter': '去掉过滤；测试要确认警告时用 pytest.warns',
         'finally': '把 return/break/continue 移出 finally',
         'exit_method': '让 __exit__ 返回 None 或 False'}


def fallbacks(cfg, graph):
    """({key: [Fallback, ...]}, {file: why it was not checked}) for the ledger's scope."""
    covered = _scope(cfg)
    graph.reset_query_coverage()
    rows = [row for row in graph.handlers() if covered(row['file']) and row['non_raising']]
    rows += [dict(row, kind='warning_filter', type=row['resolved']) for row in graph.calls()
             if row['resolved'] in WARNING_FILTERS and language_for(row['file']) == 'python' and covered(row['file'])]
    unread = {file: issue['reason'] for issue in graph.query_coverage()['issues']
              for file in issue['files'] if covered(file)}
    found = {}
    for row in sorted(rows, key=lambda row: (row['file'], row['line'])):
        language = language_for(row['file'])
        caught = row['type'] or ('BARE' if language == 'python' else row['kind'])
        function = row['node'].partition(':')[2] or '<module>'
        key = f"{row['file']}:{function}:{caught}"
        refused = _python_refusal(row['kind'], caught) if language == 'python' else ''
        found.setdefault(key, []).append(Fallback(key, row['file'], function, caught, row['line'], row['kind'],
                                                   language, refused))
    return found, unread


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
        return {}, [Finding(f'兜底账本读不了：{LEDGER}：{error}', ('改正这个文件的 TOML 写法',))], None
    entries, red, malformed = {}, [], set()
    for key, value in data.items():
        if key in SECTIONS:
            continue
        if key.count(':') < 2 or not isinstance(value, dict):
            red.append(Finding(f'兜底账本里的 {_quote(key)} 不是条目：键要写成 "文件:函数:捕获的类型"，值是一张表',
                               ('删掉它，或者改成 ["文件:函数:捕获的类型"] 下面写 count、reason、rule',)))
            continue
        problems = [f'未知字段 {name}' for name in sorted(set(value) - FIELDS)]
        problems += [f'缺少 {name}' for name in sorted(FIELDS - set(value))]
        count, reason, rule = value.get('count'), value.get('reason'), value.get('rule')
        if 'count' in value and (type(count) is not int or count < 1):
            problems.append('count 要写正整数')
        if 'reason' in value:
            if not isinstance(reason, str):
                problems.append('reason 要写一段文字')
            elif reason.strip() == PLACEHOLDER_REASON:
                problems.append('reason 还是占位文字：写明这处做了什么、为什么可以留')
            elif words(reason) < MIN_WORDS:
                problems.append(f'reason 只有 {words(reason)} 个词，至少 {MIN_WORDS} 个：写明这处做了什么、为什么可以留')
        if 'rule' in value:
            if rule == LEGACY_RULE:
                pass
            elif (not isinstance(rule, dict) or set(rule) != {'file', 'text'}
                  or not all(isinstance(rule[name], str) and rule[name].strip() for name in ('file', 'text'))):
                problems.append('rule 要写成 { file = "文件", text = "该文件里必须出现的一句话" }')
            else:
                rule = (rule['file'], rule['text'])
        if problems:
            red.append(Finding(f'兜底账本条目 {_quote(key)}：' + '；'.join(problems),
                               ('按 ledger.toml 开头的说明改正这个条目',)))
            malformed.add(key)
            continue
        entries[key] = Entry(key, count, reason, rule)
    return entries, red, malformed


def _sentence_problem(cfg, rule, texts):
    relative, sentence = rule
    if (relative, sentence) == (PLACEHOLDER_RULE['file'], PLACEHOLDER_RULE['text']):
        return 'rule 还是占位文字：写出成文规矩所在的文件和其中的一句话'
    target = (cfg.root / relative).resolve()
    if Path(relative).is_absolute() or not target.is_relative_to(cfg.root):
        return f'rule 的文件 {relative} 不在项目里'
    if target == path(cfg).resolve():
        return 'rule 不能指向账本自己'
    if not target.is_file():
        return f'rule 的文件 {relative} 不存在'
    if relative not in texts:
        texts[relative] = ' '.join(target.read_text(encoding='utf-8-sig').split())
    if ' '.join(sentence.split()) not in texts[relative]:
        return f'{relative} 里找不到 rule 那句话 {_quote(sentence)}'
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
            'finally': 'finally 里的 return/break/continue', 'exit_method': '__exit__ 返回真值'}.get(item.kind, f'{item.kind} {item.caught}')


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
        f'兜底账本 {LEDGER} 在基准提交里还在，现在没有了：删掉账本不能让兜底变绿',
        (f'恢复它：git checkout {baseline[:12]} -- {LEDGER}，再按红行改代码或条目；'
         '确实不再用账本时，提交删除后运行 python -m flowguard 记下新的基准',))])


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
            notes.append(f'基准提交 {baseline[:12]} 读不了：{why}')
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
    result = Result(present=True, entries=len(entries), legacy=sum(entry.legacy for entry in entries.values()), red=red)
    if malformed is None:
        return result                       # An unreadable ledger is compared with nothing until it is corrected.
    found, unread = fallbacks(cfg, graph)
    result.fallbacks = sum(len(items) for items in found.values())
    covered, texts = _scope(cfg), {}
    legacy = [entry for entry in entries.values() if entry.legacy]
    notes = []
    reference = _legacy_reference(cfg, baseline, notes) if legacy else {}
    if reference is None:
        result.grey.append(f'{len(legacy)} 条旧账没有核对：基准提交里没有账本，也没有 ledger init 的记录'
                           + ''.join('；' + note for note in notes))
    for key in sorted((set(found) | set(entries)) - malformed):
        items, entry = found.get(key, []), entries.get(key)
        file = key.partition(':')[0]
        listed = entry.count if entry else 0
        if entry and entry.legacy and reference is not None and entry.count > reference.get(key, 0):
            result.red.append(Finding(
                f'旧账只能由 ledger init 记下：{_quote(key)} 写着旧账 {entry.count} 处，ledger init 和基准提交只记下 {reference.get(key, 0)} 处',
                ('旧账不能加：写出真实的 reason 和 rule' + ('' if not items or not items[0].refused else '；这种写法不能登记，要改代码'),)))
            continue
        if not items:
            if file in unread:
                result.grey.append(f'{key} 没有核对：{unread[file]}')
            elif not covered(file):
                result.red.append(Finding(f'兜底账本条目 {_quote(key)} 所在的文件不在账本的扫描范围里',
                                          ('删掉这个条目，或者调整 [tool.flowguard.ledger] 的 paths/exclude',)))
            else:
                result.red.append(Finding(f'代码已消失：账本条目 {_quote(key)} 记着 {listed} 处，代码里一处也没有',
                                          ('从 .flowguard/ledger.toml 删掉这个条目',)))
            continue
        first = items[0]
        if first.refused and not (entry and entry.legacy and len(items) <= listed):
            red = f'不能登记的写法：{_where(items)} {_what(first)}（{key}）：{first.refused}'
            if entry and not entry.legacy:
                red += '；账本条目也不能让它变绿'
            result.red.append(Finding(red, (FIXES[first.kind] + ('；然后删掉账本里这个条目' if entry else ''),)))
            continue
        if entry and not entry.legacy:
            problem = _sentence_problem(cfg, entry.rule, texts)
            if problem:
                result.red.append(Finding(f'兜底账本条目 {_quote(key)}：{problem}',
                                          ('改成该文件里真实存在的一句成文规矩',)))
        if len(items) > listed:
            if not entry:
                text = f'新增兜底未登记：{_where(items)} {_what(first)} 之后能不抛出就结束'
            elif entry.legacy:
                text = f'新增兜底：{_where(items)} {_what(first)} 现有 {len(items)} 处，旧账只记了 {listed} 处'
            else:
                text = f'兜底多了：{_where(items)} {_what(first)} 现有 {len(items)} 处，账本记着 {listed} 处'
            fix = ['要保留就在 .flowguard/ledger.toml ' + ('写入这一条（替换原条目）：' if entry else '加：'),
                   *_entry_lines(key, len(items),
                                 rule=None if not entry or entry.legacy else dict(file=entry.rule[0], text=entry.rule[1]),
                                 reason=PLACEHOLDER_REASON if not entry or entry.legacy else entry.reason),
                   '不该留就改代码，让错误抛出']
            result.red.append(Finding(text, tuple(fix)))
        elif len(items) < listed:
            result.red.append(Finding(f'兜底少了：{_quote(key)} 账本记着 {listed} 处，代码里只有 {len(items)} 处（{_where(items)}）',
                                      (f'把这个条目改成 count = {len(items)}',)))
    for file, reason in sorted(unread.items()):
        if not any(key.partition(':')[0] == file for key in entries):
            result.grey.append(f'{file} 没有核对：{reason}')
    return result


def lines(result) -> list[str]:
    """The red findings in full, each followed by its next step, which can be copied as written."""
    out = []
    for finding in result.red:
        out.append('红：' + finding.text)
        out.extend('    ' + line for line in finding.fix)
    return out


def summary(result) -> str:
    return (f'FlowGuard 兜底账本：{result.entries} 条（旧账 {result.legacy} 条），代码里 {result.fallbacks} 处兜底；'
            f'红 {len(result.red)}，未核对 {len(result.grey)}')


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
    report = [f'FlowGuard 兜底账本已建立：{LEDGER}，{len(found)} 条旧账，共 {sum(map(len, found.values()))} 处兜底'
              f'（其中 {refused} 条是不能新增的写法）。以后新增、数量变化、代码消失都会让 pytest 失败；提交这个文件。']
    report += [f'没有核对：{file}：{reason}' for file, reason in sorted(unread.items())]
    return report
