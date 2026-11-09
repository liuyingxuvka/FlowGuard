"""The fallback ledger: handlers that may end without raising are counted per function against
`.flowguard/ledger.toml`, each kept with a reason and a written rule whose sentence must still exist."""
from contextlib import closing
from pathlib import Path
import json
import subprocess
import sys
import textwrap
import tomllib

import pytest

from flowguard.intent import ledger
from flowguard.intent.config import load_config
from flowguard.structure import build
from tests._pure_helpers import git, write
from tests.intent_engine._cli_fixture import display_text

SOURCE = str(Path(__file__).resolve().parents[2])
RULE = 'One route per function: when a step fails, the error reaches the caller or is reported with its text.'
LEGACY_CODE = '''
def old_reader(values, key):
    try:
        return values[key]
    except Exception:
        return None
'''
SWALLOW = '''

def swallow(work):
    try:
        work()
    except Exception:
        pass
'''
LOOKUP = '''

def lookup(values, key, strict):
    try:
        return values[key]
    except KeyError:
        if strict:
            raise
        return None
'''
REASON = 'a missing key in lenient mode is the answer: the caller shows the value as unknown'


def evaluate(root, baseline=None):
    cfg = load_config(root)
    with closing(build(root, workers=1)) as graph:
        return ledger.evaluate(cfg, graph, baseline=baseline)


def init(root):
    cfg = load_config(root)
    with closing(build(root, workers=1)) as graph:
        return ledger.init(cfg, graph)


def texts(result):
    return [finding.text for finding in result.red]


def entry(key, count=1, reason=REASON, rule=None):
    rule = dict(file='AGENTS.md', text=RULE) if rule is None else rule
    return '\n' + '\n'.join(ledger._entry_lines(key, count, reason=reason, rule=rule)) + '\n'


def add_entry(root, text):
    path = Path(root) / ledger.LEDGER
    path.write_text(path.read_text(encoding='utf-8') + text, encoding='utf-8')


@pytest.fixture
def shop(tmp_path):
    """A committed project whose ledger init recorded one legacy catch-all handler."""
    root = tmp_path / 'shop'
    write(root, 'src/shop/__init__.py', '')
    write(root, 'src/shop/stock.py', LEGACY_CODE)
    write(root, 'tests/test_stock.py', 'from shop.stock import old_reader\n\ndef test_reader():\n    assert old_reader({"a": 1}, "a") == 1\n')
    write(root, 'AGENTS.md', '# Rules\n\n' + RULE + '\n')
    write(root, 'pyproject.toml', '[tool.pytest.ini_options]\npythonpath = ["src"]\n')
    git(root, 'init', '-q')
    init(root)
    git(root, 'add', '-A')
    git(root, 'commit', '-qm', 'start the ledger')
    return root


def append(root, text):
    path = Path(root) / 'src/shop/stock.py'
    path.write_text(path.read_text(encoding='utf-8') + text, encoding='utf-8')


def head(root):
    return git(root, 'rev-parse', 'HEAD').decode().strip()


def test_ledger_init_records_existing_handlers_as_legacy_and_they_are_not_reported(shop):
    data = tomllib.loads((shop / ledger.LEDGER).read_text(encoding='utf-8'))
    assert data == {'src/shop/stock.py:old_reader:Exception': dict(count=1, reason=ledger.LEGACY_REASON, rule=ledger.LEGACY_RULE)}
    assert ledger.words(ledger.LEGACY_REASON) >= ledger.MIN_WORDS
    result = evaluate(shop, head(shop))
    assert result.present and result.red == [] and result.grey == []
    assert (result.entries, result.legacy, result.fallbacks) == (1, 1, 1)


def test_a_new_catch_all_handler_is_red_and_no_entry_makes_it_green(shop):
    append(shop, SWALLOW)
    found = texts(evaluate(shop, head(shop)))
    assert len(found) == 1 and found[0].startswith('不能登记的写法：src/shop/stock.py:') and 'swallow:Exception' in found[0]
    add_entry(shop, entry('src/shop/stock.py:swallow:Exception',
                          reason='a background job must never stop the loop, so every error is ignored here'))
    found = texts(evaluate(shop, head(shop)))
    assert len(found) == 1 and '账本条目也不能让它变绿' in found[0]
    # The legacy marker is reserved for ledger init: a hand-written legacy entry stays red.
    text = (shop / ledger.LEDGER).read_text(encoding='utf-8')
    (shop / ledger.LEDGER).write_text(text[:text.index('\n["src/shop/stock.py:swallow')]
                                      + entry('src/shop/stock.py:swallow:Exception', reason=ledger.LEGACY_REASON,
                                              rule=ledger.LEGACY_RULE), encoding='utf-8')
    found = texts(evaluate(shop, head(shop)))
    assert len(found) == 1 and found[0].startswith('旧账只能由 ledger init 记下')


def test_a_handler_raising_on_one_branch_is_red_until_its_reason_and_rule_are_listed(shop):
    append(shop, LOOKUP)
    result = evaluate(shop, head(shop))
    assert texts(result) == ['新增兜底未登记：src/shop/stock.py:12 except KeyError 之后能不抛出就结束']
    copy = [line for line in result.red[0].fix if line.startswith(('[', 'count', 'reason', 'rule'))]
    assert copy[0] == '["src/shop/stock.py:lookup:KeyError"]' and copy[1] == 'count = 1'
    # Copied as printed, the placeholders keep it red; with a real reason and rule it turns green.
    add_entry(shop, '\n' + '\n'.join(copy) + '\n')
    assert any('reason 还是占位文字' in text for text in texts(evaluate(shop, head(shop))))
    text = (shop / ledger.LEDGER).read_text(encoding='utf-8')
    text = text.replace(ledger._quote(ledger.PLACEHOLDER_REASON), ledger._quote(REASON))
    text = text.replace(ledger._quote(ledger.PLACEHOLDER_RULE['file']), ledger._quote('AGENTS.md'))
    text = text.replace(ledger._quote(ledger.PLACEHOLDER_RULE['text']), ledger._quote(RULE))
    (shop / ledger.LEDGER).write_text(text, encoding='utf-8')
    assert evaluate(shop, head(shop)).red == []


def test_a_handler_that_raises_on_every_path_is_not_a_fallback(shop):
    append(shop, '\n\ndef strict(values, key):\n    try:\n        return values[key]\n    except KeyError as error:\n'
                 '        if key:\n            raise LookupError(key) from error\n        raise\n')
    assert evaluate(shop, head(shop)).red == []


def test_code_removed_while_its_entry_stays_is_red(shop):
    append(shop, LOOKUP)
    add_entry(shop, entry('src/shop/stock.py:lookup:KeyError'))
    assert evaluate(shop, head(shop)).red == []
    write(shop, 'src/shop/stock.py', LEGACY_CODE)
    assert texts(evaluate(shop, head(shop))) == [
        '代码已消失：账本条目 "src/shop/stock.py:lookup:KeyError" 记着 1 处，代码里一处也没有']


def test_a_rule_sentence_missing_from_its_file_is_red(shop):
    append(shop, LOOKUP)
    add_entry(shop, entry('src/shop/stock.py:lookup:KeyError'))
    write(shop, 'AGENTS.md', '# Rules\n\nErrors reach the caller.\n')
    found = texts(evaluate(shop, head(shop)))
    assert found == ['兜底账本条目 "src/shop/stock.py:lookup:KeyError"：AGENTS.md 里找不到 rule 那句话 ' + ledger._quote(RULE)]
    write(shop, 'AGENTS.md', '# Rules\n\nOne route per function: when a step fails,\nthe error reaches the caller or is reported with its text.\n')
    assert evaluate(shop, head(shop)).red == []  # white space is normalised, as in the owners' lists


@pytest.mark.parametrize('rule, problem', [
    (dict(file='missing.md', text=RULE), 'rule 的文件 missing.md 不存在'),
    (dict(file='../outside.md', text=RULE), 'rule 的文件 ../outside.md 不在项目里'),
    (dict(file=ledger.LEDGER, text='count = 1'), 'rule 不能指向账本自己'),
])
def test_a_rule_must_quote_a_written_rule_inside_the_project(shop, rule, problem):
    append(shop, LOOKUP)
    add_entry(shop, entry('src/shop/stock.py:lookup:KeyError', rule=rule))
    assert texts(evaluate(shop, head(shop))) == [f'兜底账本条目 "src/shop/stock.py:lookup:KeyError"：{problem}']


def test_counts_must_be_equal_in_both_directions(shop):
    append(shop, LOOKUP + LOOKUP.replace('def lookup', 'def lookup_again'))
    add_entry(shop, entry('src/shop/stock.py:lookup:KeyError') + entry('src/shop/stock.py:lookup_again:KeyError'))
    assert evaluate(shop, head(shop)).red == []
    # A second handler of the same kind in one function needs the count raised.
    write(shop, 'src/shop/stock.py', LEGACY_CODE + LOOKUP.rstrip() + '\n    try:\n        return values[key.lower()]\n'
          '    except KeyError:\n        return None\n')
    result = evaluate(shop, head(shop))
    assert texts(result)[0] == '兜底多了：src/shop/stock.py:12,18 except KeyError 现有 2 处，账本记着 1 处'
    assert 'count = 2' in result.red[0].fix and ledger._quote(REASON) in ' '.join(result.red[0].fix)
    assert texts(result)[1] == '代码已消失：账本条目 "src/shop/stock.py:lookup_again:KeyError" 记着 1 处，代码里一处也没有'
    write(shop, ledger.LEDGER, (shop / ledger.LEDGER).read_text(encoding='utf-8').replace(
        'count = 1\nreason = ' + ledger._quote(REASON), 'count = 3\nreason = ' + ledger._quote(REASON), 1))
    assert '兜底少了："src/shop/stock.py:lookup:KeyError" 账本记着 3 处，代码里只有 2 处（src/shop/stock.py:12,18）' in texts(evaluate(shop, head(shop)))


@pytest.mark.parametrize('reason, problem', [
    ('swallows the error', 'reason 只有 3 个词，至少 8 个'),
    ('吞掉错误', 'reason 只有 2 个词，至少 8 个'),
    (ledger.PLACEHOLDER_REASON, 'reason 还是占位文字'),
])
def test_a_reason_states_what_the_handler_does_in_at_least_eight_words(shop, reason, problem):
    append(shop, LOOKUP)
    add_entry(shop, entry('src/shop/stock.py:lookup:KeyError', reason=reason))
    found = texts(evaluate(shop, head(shop)))
    assert len(found) == 1 and found[0].startswith('兜底账本条目 "src/shop/stock.py:lookup:KeyError"：') and problem in found[0]


def test_word_count_reads_latin_words_and_cjk_characters():
    assert ledger.words('the caller shows the value as unknown here') == 8
    assert ledger.words('调用方把缺失值显示为未知') == 6
    assert ledger.words('(finding, ...) os.path') == 2


def test_malformed_entries_are_red_without_a_second_report_for_their_key(shop):
    append(shop, LOOKUP)
    add_entry(shop, '\n["src/shop/stock.py:lookup:KeyError"]\ncount = 0\nreason = 3\nwhy = "x"\n\n[options]\nx = 1\n')
    assert texts(evaluate(shop, head(shop))) == [
        '兜底账本条目 "src/shop/stock.py:lookup:KeyError"：未知字段 why；缺少 rule；count 要写正整数；reason 要写一段文字',
        '兜底账本里的 "options" 不是条目：键要写成 "文件:函数:捕获的类型"，值是一张表']
    write(shop, ledger.LEDGER, 'not toml = = 1\n')
    found = texts(evaluate(shop, head(shop)))
    assert len(found) == 1 and found[0].startswith('兜底账本读不了：.flowguard/ledger.toml：')


FORMS = '''
import contextlib as cl
import warnings
from contextlib import suppress as quiet
import pytest

hush = cl.suppress


def forms(work):
    try:
        work()
    except:
        pass
    try:
        work()
    except BaseException:
        return None
    try:
        work()
    except (OSError, Exception):
        return None
    with quiet(OSError):
        work()
    with hush(KeyError):
        work()
    with getattr(cl, 'suppress')(ValueError):
        work()
    warnings.simplefilter('ignore')
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
    for item in work():
        try:
            work()
        finally:
            continue


@pytest.mark.filterwarnings('ignore')
def test_quiet():
    try:
        return 1
    finally:
        return 2


class Swallow:
    def __exit__(self, *details):
        return True


class Lambda:
    __exit__ = lambda self, *details: True


class Closing:
    def __exit__(self, *details):
        self.close()
        return False
'''


def test_every_refused_form_is_found_and_none_can_be_listed(tmp_path):
    write(tmp_path, 'forms.py', FORMS)
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, workers=1)) as graph:
        found, unread = ledger.fallbacks(cfg, graph)
    assert unread == {}
    assert {key: len(items) for key, items in found.items()} == {
        'forms.py:forms:BARE': 1, 'forms.py:forms:BaseException': 1, 'forms.py:forms:(OSError, Exception)': 1,
        'forms.py:forms:suppress(OSError)': 1, 'forms.py:forms:suppress(KeyError)': 1, 'forms.py:forms:suppress(ValueError)': 1,
        'forms.py:forms:warnings.simplefilter': 1, 'forms.py:forms:warnings.catch_warnings': 1,
        'forms.py:forms:warnings.filterwarnings': 1, 'forms.py:forms:finally exits': 1,
        'forms.py:<module>:pytest.mark.filterwarnings': 1, 'forms.py:test_quiet:finally exits': 1,
        'forms.py:Swallow.__exit__:may return true': 1, 'forms.py:Lambda:__exit__ may return true': 1}
    assert all(items[0].refused and items[0].language == 'python' for items in found.values())
    write(tmp_path, ledger.LEDGER, ledger.HEADER + ''.join(entry(key) for key in found))
    write(tmp_path, 'AGENTS.md', RULE + '\n')
    result = evaluate(tmp_path)
    assert len(result.red) == len(found) and all(text.startswith('不能登记的写法：') for text in texts(result))


def test_ledger_init_also_covers_refused_forms_and_round_trips_its_toml(tmp_path):
    write(tmp_path, 'forms.py', FORMS)
    for text in ('tab\there "quoted" \\ back', 'delete\x7f and \x01', '中文：键'):
        assert tomllib.loads('key = ' + ledger._quote(text))['key'] == text
    report = init(tmp_path)
    assert report[0].startswith('FlowGuard 兜底账本已建立：.flowguard/ledger.toml，14 条旧账，共 14 处兜底（其中 14 条是不能新增的写法）')
    data = tomllib.loads((tmp_path / ledger.LEDGER).read_text(encoding='utf-8'))
    assert len(data) == 14 and all(value['rule'] == ledger.LEGACY_RULE for value in data.values())
    assert json.loads((tmp_path / '.flowguard/cache' / ledger.INIT_RECORD).read_text(encoding='utf-8'))['legacy'] == {
        key: 1 for key in data}
    assert evaluate(tmp_path).red == []           # Outside Git the init record verifies the legacy entries.
    with pytest.raises(ValueError, match='already exists'):
        init(tmp_path)


def test_a_legacy_entry_can_shrink_but_never_grow(shop):
    (shop / '.flowguard/cache' / ledger.INIT_RECORD).unlink()  # Only the baseline commit vouches now.
    baseline = head(shop)
    assert evaluate(shop, baseline).red == []
    original = (shop / ledger.LEDGER).read_text(encoding='utf-8')
    # A second catch-all in the legacy function cannot be hidden by raising the legacy count.
    write(shop, 'src/shop/stock.py', LEGACY_CODE.rstrip() + '\n    try:\n        return values[key.lower()]\n'
          '    except Exception:\n        return None\n')
    assert texts(evaluate(shop, baseline))[0].startswith('不能登记的写法：src/shop/stock.py:5,9 except Exception')
    write(shop, ledger.LEDGER, original.replace('count = 1', 'count = 2'))
    assert texts(evaluate(shop, baseline))[0].startswith(
        '旧账只能由 ledger init 记下："src/shop/stock.py:old_reader:Exception" 写着旧账 2 处，ledger init 和基准提交只记下 1 处')
    # A new function cannot borrow the legacy marker either.
    write(shop, 'src/shop/stock.py', LEGACY_CODE + SWALLOW)
    write(shop, ledger.LEDGER, original + entry('src/shop/stock.py:swallow:Exception', reason=ledger.LEGACY_REASON,
                                               rule=ledger.LEGACY_RULE))
    assert texts(evaluate(shop, baseline))[0].startswith('旧账只能由 ledger init 记下："src/shop/stock.py:swallow:Exception"')
    # Fixing the legacy handler shrinks the ledger: the stale entry is red until it is removed.
    write(shop, 'src/shop/stock.py', 'def old_reader(values, key):\n    return values.get(key)\n')
    write(shop, ledger.LEDGER, original)
    assert texts(evaluate(shop, baseline)) == [
        '代码已消失：账本条目 "src/shop/stock.py:old_reader:Exception" 记着 1 处，代码里一处也没有']
    write(shop, ledger.LEDGER, ledger.HEADER)
    assert evaluate(shop, baseline).red == []


def test_without_a_baseline_or_init_record_legacy_entries_stay_unverified(tmp_path):
    write(tmp_path, 'app.py', LEGACY_CODE)
    init(tmp_path)
    (tmp_path / '.flowguard/cache' / ledger.INIT_RECORD).unlink()
    result = evaluate(tmp_path)
    assert result.red == [] and result.grey == ['1 条旧账没有核对：基准提交里没有账本，也没有 ledger init 的记录']


def test_deleting_the_ledger_is_red_while_the_baseline_commit_still_has_it(shop):
    (shop / ledger.LEDGER).unlink()
    result = evaluate(shop, head(shop))
    assert not result.present and texts(result) == [
        '兜底账本 .flowguard/ledger.toml 在基准提交里还在，现在没有了：删掉账本不能让兜底变绿']
    git(shop, 'commit', '-qam', 'stop using the ledger')
    assert evaluate(shop, head(shop)).red == []           # Once the deletion is the baseline, nothing is checked.


def test_a_baseline_commit_missing_from_the_clone_leaves_legacy_unverified_not_crashed(shop):
    missing = 'f' * 40
    assert evaluate(shop, missing).red == []              # The init record still vouches for the legacy entry.
    (shop / '.flowguard/cache' / ledger.INIT_RECORD).unlink()
    result = evaluate(shop, missing)
    assert result.red == [] and len(result.grey) == 1
    assert result.grey[0].startswith('1 条旧账没有核对：基准提交里没有账本，也没有 ledger init 的记录；基准提交 ffffffffffff 读不了：')


OWN_LIST = '''
import ast

NON_RAISING_HANDLERS = {
    "app/cli.py:main:ValueError": ("exit-codes", "the command boundary prints the message and exits 2"),
}


def test_handlers():
    found = [node for node in ast.walk(ast.parse("")) if isinstance(node, ast.ExceptHandler)]
    assert found == []
'''


def test_ledger_init_refuses_when_the_project_keeps_its_own_handler_list(tmp_path):
    write(tmp_path, 'tests/test_my_handlers.py', OWN_LIST)
    with pytest.raises(ValueError, match=r'already keeps its own handler list in tests/test_my_handlers.py.*Choose one'):
        init(tmp_path)
    assert not (tmp_path / ledger.LEDGER).exists()
    # Neither the key strings alone nor an AST handler scan alone is such a list.
    write(tmp_path, 'tests/test_my_handlers.py', OWN_LIST.replace('ast.ExceptHandler', 'ast.Try'))
    write(tmp_path, 'tests/test_scan.py', 'import ast\nKINDS = (ast.ExceptHandler,)\nNAMES = {"f:suppress(OSError)": 1}\n')
    assert init(tmp_path)[0].startswith('FlowGuard 兜底账本已建立')


def test_the_scan_scope_is_every_mapped_file_unless_configured(tmp_path):
    write(tmp_path, 'app.py', LOOKUP)
    write(tmp_path, 'scripts/tool.py', LOOKUP)
    write(tmp_path, 'tests/test_app.py', LOOKUP)
    write(tmp_path, 'tests/fixtures/sample.py', LOOKUP)
    write(tmp_path, ledger.LEDGER, ledger.HEADER)
    files = lambda: sorted(text.split()[0].removeprefix('新增兜底未登记：').split(':')[0] for text in texts(evaluate(tmp_path)))
    assert files() == ['app.py', 'scripts/tool.py', 'tests/fixtures/sample.py', 'tests/test_app.py']
    write(tmp_path, 'pyproject.toml', '[tool.flowguard.ledger]\npaths = ["app.py", "tests"]\nexclude = ["tests/fixtures/**"]\n')
    assert files() == ['app.py', 'tests/test_app.py']
    write(tmp_path, ledger.LEDGER, ledger.HEADER + entry('scripts/tool.py:lookup:KeyError'))
    write(tmp_path, 'AGENTS.md', RULE + '\n')
    assert '兜底账本条目 "scripts/tool.py:lookup:KeyError" 所在的文件不在账本的扫描范围里' in texts(evaluate(tmp_path))
    write(tmp_path, 'pyproject.toml', '[tool.flowguard.ledger]\nfiles = ["app.py"]\n')
    with pytest.raises(ValueError, match=r'\[tool.flowguard.ledger\] takes only paths and exclude'):
        load_config(tmp_path)


def test_an_unreadable_source_is_not_checked_rather_than_read_as_empty(tmp_path):
    write(tmp_path, 'app.py', LOOKUP)
    write(tmp_path, '_tmp_x.py', 'def broken(:\n')
    write(tmp_path, ledger.LEDGER, ledger.HEADER + entry('app.py:lookup:KeyError') + entry('_tmp_x.py:broken:KeyError'))
    write(tmp_path, 'AGENTS.md', RULE + '\n')
    result = evaluate(tmp_path)
    assert result.red == []
    assert len(result.grey) == 1 and result.grey[0].startswith('_tmp_x.py:broken:KeyError 没有核对：source parse failed')


def test_other_languages_supply_rows_through_the_same_fields(tmp_path):
    """A foreign reader's handler rows get the same key and their language; no Python-only refusal applies.
    A JS/TS row names its enclosing named function, so an anonymous callback's line never enters the key."""
    class Rows:
        def reset_query_coverage(self):
            pass

        def handlers(self):
            return [dict(node='typescript/src/employee.service.ts:<anonymous@2178>', file='src/employee.service.ts',
                         line=2180, kind='catch', type='any', function='syncEmployee', non_raising=True),
                    dict(node='typescript/src/employee.service.ts:forward', file='src/employee.service.ts', line=9,
                         kind='catch', type='any', function='forward', non_raising=False)]

        def calls(self, *, language=None):
            return []

        def query_coverage(self):
            return dict(queried=['handlers'], complete=True, issues=[])

    found, unread = ledger.fallbacks(load_config(tmp_path), Rows())
    assert found == {'src/employee.service.ts:syncEmployee:any': [ledger.Fallback(
        'src/employee.service.ts:syncEmployee:any', 'src/employee.service.ts', 'syncEmployee', 'any', 2180, 'catch',
        'typescript', '')]} and unread == {}


def test_a_typescript_catch_that_ends_quietly_is_red_and_one_that_hands_the_error_on_is_not(tmp_path):
    write(tmp_path, 'web/read.ts', 'function read(){ try { work(); } catch (error) { return 0; } }\n')
    write(tmp_path, 'web/route.ts', 'function route(req, res, next){ try { work(); } catch (err) { next(err); } }\n'
          'function load(){ return new Promise((resolve, reject) => { try { work(); } catch (e) { reject(e); } }); }\n'
          'function again(){ try { work(); } catch (e) { throw e; } }\n')
    write(tmp_path, ledger.LEDGER, ledger.HEADER)
    result = evaluate(tmp_path)
    assert result.grey == []
    reds = [finding for finding in result.red if 'web/' in finding.text]
    assert len(reds) == 1 and 'web/read.ts:1' in reds[0].text
    assert any('web/read.ts:read:any' in line for line in reds[0].fix)
    add_entry(tmp_path, entry('web/read.ts:read:any', reason='a failed optional read shows zero and the page '
                              'explains that the value could not be loaded'))
    write(tmp_path, 'AGENTS.md', '# Rules\n\n' + RULE + '\n')
    assert evaluate(tmp_path).red == []


# ---- ordinary pytest and the CLI --------------------------------------------------------------------------


def shown(result):
    """A console that cannot encode the text (Windows cp1252) gets the supported escaped display; read it back."""
    result.stdout, result.stderr = display_text(result.stdout), display_text(result.stderr)
    return result


def pytest_run(root, *arguments):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    return shown(subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p', 'flowguard.intent.plugin', *arguments],
                                cwd=root, capture_output=True, text=True, timeout=120))


def cli(root, *arguments):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); from flowguard.__main__ import main; raise SystemExit(main(sys.argv[1:]))'
    return shown(subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '--root', str(root), *arguments],
                                cwd=root, capture_output=True, text=True, timeout=120))


def sentinel(root):
    write(root, 'tests/test_flowguard_intent.py', 'def test_flowguard_intent(request):\n'
          '    from flowguard.intent.plugin import sentinel\n    sentinel(request.config)\n')


def attempt(root):
    import sqlite3
    with closing(sqlite3.connect(root / '.flowguard/cache/map.sqlite')) as connection:
        return json.loads(connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0])


def test_ordinary_pytest_fails_on_a_new_fallback_and_prints_the_entry_to_copy(shop):
    sentinel(shop)
    git(shop, 'add', '-A')
    git(shop, 'commit', '-qm', 'sentinel')
    passed = pytest_run(shop)
    assert passed.returncode == 0 and '2 passed' in passed.stdout, passed.stdout + passed.stderr
    append(shop, LOOKUP)
    failed = pytest_run(shop)
    output = failed.stdout + failed.stderr
    assert failed.returncode == 1, output
    assert 'FAILED tests/test_flowguard_intent.py::test_flowguard_intent' in output and '1 failed, 1 passed' in output
    assert '红：新增兜底未登记：src/shop/stock.py:12 except KeyError 之后能不抛出就结束' in output
    block = output[output.index('    要保留就在 .flowguard/ledger.toml 加：'):]
    assert block.splitlines()[1:5] == ['    ["src/shop/stock.py:lookup:KeyError"]', '    count = 1',
                                      '    reason = ' + ledger._quote(ledger.PLACEHOLDER_REASON),
                                      '    rule = { file = "成文规矩所在的文件", text = "该文件里必须出现的一句话" }']
    assert 'old_reader' not in output                       # The legacy entry is not reported.
    assert attempt(shop)['sentinel'] == 'ok'                # The intent collection itself stayed complete.
    # The plugin route also fails a run that does not collect the sentinel.
    partial = pytest_run(shop, 'tests/test_stock.py')
    assert partial.returncode == 1 and '红：新增兜底未登记' in partial.stdout, partial.stdout + partial.stderr
    add_entry(shop, entry('src/shop/stock.py:lookup:KeyError'))
    green = pytest_run(shop)
    assert green.returncode == 0 and '2 passed' in green.stdout and '红' not in green.stdout, green.stdout + green.stderr
    (shop / ledger.LEDGER).unlink()                         # Deleting the ledger does not turn it off.
    deleted = pytest_run(shop)
    assert deleted.returncode == 1 and '红：兜底账本 .flowguard/ledger.toml 在基准提交里还在，现在没有了' in deleted.stdout, \
        deleted.stdout + deleted.stderr


def test_ledger_check_and_check_list_the_differences_without_running_tests(shop):
    absent = cli(shop.parent, 'ledger', 'check')
    assert absent.returncode == 0 and 'no .flowguard/ledger.toml' in absent.stdout
    clean = cli(shop, 'ledger', 'check')
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert clean.stdout.splitlines() == ['FlowGuard 兜底账本：1 条（旧账 1 条），代码里 1 处兜底；红 0，未核对 0']
    append(shop, SWALLOW)
    red = cli(shop, 'ledger', 'check')
    assert red.returncode == 1 and '红：不能登记的写法：src/shop/stock.py:' in red.stdout, red.stdout + red.stderr
    checked = cli(shop, 'check')
    assert checked.returncode == 1 and '红：不能登记的写法：src/shop/stock.py:' in checked.stdout, checked.stdout + checked.stderr
    again = cli(shop, 'ledger', 'init')
    assert again.returncode == 2 and 'already exists' in again.stderr
    (shop / ledger.LEDGER).unlink()
    deleted = cli(shop, 'ledger', 'check')
    assert deleted.returncode == 1 and '现在没有了' in deleted.stdout, deleted.stdout + deleted.stderr


def test_ledger_init_says_when_pytest_does_not_load_the_plugin(tmp_path):
    write(tmp_path, 'app.py', LOOKUP)
    started = cli(tmp_path, 'ledger', 'init')
    assert started.returncode == 0, started.stdout + started.stderr
    assert started.stdout.splitlines()[-1].startswith('pytest does not load the FlowGuard plugin yet')
    write(tmp_path / 'other', 'app.py', LOOKUP)
    write(tmp_path / 'other', 'tests/conftest.py', 'pytest_plugins = ["flowguard.intent.plugin"]\n')
    started = cli(tmp_path / 'other', 'ledger', 'init')
    assert 'pytest does not load' not in started.stdout, started.stdout + started.stderr
