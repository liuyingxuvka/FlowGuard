"""The fallback ledger: handlers that may end without raising are counted per function against
`.flowguard/ledger.toml`, each kept with a reason and a written rule whose sentence must still exist."""
from contextlib import closing
from pathlib import Path
import json
import re
import subprocess
import sys
import textwrap
import tomllib

import pytest

from flowguard.intent import ledger
from flowguard.intent.config import load_config
from tests.intent_engine._cli_fixture import last
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
    assert ledger.LEGACY_RULE == '旧账'
    assert ledger.words(ledger.LEGACY_REASON) >= ledger.MIN_WORDS
    result = evaluate(shop, head(shop))
    assert result.present and result.red == [] and result.grey == []
    assert (result.entries, result.legacy, result.fallbacks) == (1, 1, 1)


def test_a_new_catch_all_handler_is_red_and_no_entry_makes_it_green(shop):
    append(shop, SWALLOW)
    found = texts(evaluate(shop, head(shop)))
    assert len(found) == 1 and found[0].startswith('Form cannot be registered: src/shop/stock.py:') and 'swallow:Exception' in found[0]
    add_entry(shop, entry('src/shop/stock.py:swallow:Exception',
                          reason='a background job must never stop the loop, so every error is ignored here'))
    found = texts(evaluate(shop, head(shop)))
    assert len(found) == 1 and 'a ledger entry cannot clear this failure' in found[0]
    # The legacy marker is reserved for ledger init: a hand-written legacy entry stays red.
    text = (shop / ledger.LEDGER).read_text(encoding='utf-8')
    (shop / ledger.LEDGER).write_text(text[:text.index('\n["src/shop/stock.py:swallow')]
                                      + entry('src/shop/stock.py:swallow:Exception', reason=ledger.LEGACY_REASON,
                                              rule=ledger.LEGACY_RULE), encoding='utf-8')
    found = texts(evaluate(shop, head(shop)))
    assert len(found) == 1 and found[0].startswith('Only ledger init may record legacy entries')


def test_a_handler_raising_on_one_branch_is_red_until_its_reason_and_rule_are_listed(shop):
    append(shop, LOOKUP)
    result = evaluate(shop, head(shop))
    assert texts(result) == ['New unregistered fallback: src/shop/stock.py:12 except KeyError can end without raising']
    copy = [line for line in result.red[0].fix if line.startswith(('[', 'count', 'reason', 'rule'))]
    assert copy[0] == '["src/shop/stock.py:lookup:KeyError"]' and copy[1] == 'count = 1'
    # Copied as printed, the placeholders keep it red; with a real reason and rule it turns green.
    add_entry(shop, '\n' + '\n'.join(copy) + '\n')
    assert any('reason is still a placeholder' in text for text in texts(evaluate(shop, head(shop))))
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
        'Code disappeared: ledger entry "src/shop/stock.py:lookup:KeyError" records 1 handlers, but none remain in the code']


def test_a_rule_sentence_missing_from_its_file_is_red(shop):
    append(shop, LOOKUP)
    add_entry(shop, entry('src/shop/stock.py:lookup:KeyError'))
    write(shop, 'AGENTS.md', '# Rules\n\nErrors reach the caller.\n')
    found = texts(evaluate(shop, head(shop)))
    assert found == ['Fallback ledger entry "src/shop/stock.py:lookup:KeyError": rule sentence ' + ledger._quote(RULE) + ' is missing from AGENTS.md']
    write(shop, 'AGENTS.md', '# Rules\n\nOne route per function: when a step fails,\nthe error reaches the caller or is reported with its text.\n')
    assert evaluate(shop, head(shop)).red == []  # white space is normalised, as in the owners' lists


@pytest.mark.parametrize('rule, problem', [
    (dict(file='missing.md', text=RULE), 'rule file missing.md does not exist'),
    (dict(file='../outside.md', text=RULE), 'rule file ../outside.md is outside the project'),
    (dict(file=ledger.LEDGER, text='count = 1'), 'rule cannot refer to the ledger itself'),
])
def test_a_rule_must_quote_a_written_rule_inside_the_project(shop, rule, problem):
    append(shop, LOOKUP)
    add_entry(shop, entry('src/shop/stock.py:lookup:KeyError', rule=rule))
    assert texts(evaluate(shop, head(shop))) == [f'Fallback ledger entry "src/shop/stock.py:lookup:KeyError": {problem}']


def test_counts_must_be_equal_in_both_directions(shop):
    append(shop, LOOKUP + LOOKUP.replace('def lookup', 'def lookup_again'))
    add_entry(shop, entry('src/shop/stock.py:lookup:KeyError') + entry('src/shop/stock.py:lookup_again:KeyError'))
    assert evaluate(shop, head(shop)).red == []
    # A second handler of the same kind in one function needs the count raised.
    write(shop, 'src/shop/stock.py', LEGACY_CODE + LOOKUP.rstrip() + '\n    try:\n        return values[key.lower()]\n'
          '    except KeyError:\n        return None\n')
    result = evaluate(shop, head(shop))
    assert texts(result)[0] == 'More fallbacks: src/shop/stock.py:12,18 except KeyError now has 2 handlers; the ledger records 1'
    assert 'count = 2' in result.red[0].fix and ledger._quote(REASON) in ' '.join(result.red[0].fix)
    assert texts(result)[1] == 'Code disappeared: ledger entry "src/shop/stock.py:lookup_again:KeyError" records 1 handlers, but none remain in the code'
    write(shop, ledger.LEDGER, (shop / ledger.LEDGER).read_text(encoding='utf-8').replace(
        'count = 1\nreason = ' + ledger._quote(REASON), 'count = 3\nreason = ' + ledger._quote(REASON), 1))
    assert 'Fewer fallbacks: "src/shop/stock.py:lookup:KeyError" records 3 handlers, but only 2 remain (src/shop/stock.py:12,18)' in texts(evaluate(shop, head(shop)))


@pytest.mark.parametrize('reason, problem', [
    ('swallows the error', 'reason has 3 words; at least 8 are required'),
    ('吞掉错误', 'reason has 2 words; at least 8 are required'),
    (ledger.PLACEHOLDER_REASON, 'reason is still a placeholder'),
    ('换成真实的理由：这处做了什么、为什么可以留（不少于 8 个词）', 'reason is still a placeholder'),
])
def test_a_reason_states_what_the_handler_does_in_at_least_eight_words(shop, reason, problem):
    append(shop, LOOKUP)
    add_entry(shop, entry('src/shop/stock.py:lookup:KeyError', reason=reason))
    found = texts(evaluate(shop, head(shop)))
    assert len(found) == 1 and found[0].startswith('Fallback ledger entry "src/shop/stock.py:lookup:KeyError": ') and problem in found[0]


@pytest.mark.parametrize('rule', [
    ledger.PLACEHOLDER_RULE,
    dict(file='成文规矩所在的文件', text='该文件里必须出现的一句话'),
])
def test_old_and_current_rule_placeholders_stay_invalid_even_when_the_file_exists(shop, rule):
    append(shop, LOOKUP)
    write(shop, rule['file'], rule['text'])
    add_entry(shop, entry('src/shop/stock.py:lookup:KeyError', rule=rule))
    found = texts(evaluate(shop, head(shop)))
    assert found == ['Fallback ledger entry "src/shop/stock.py:lookup:KeyError": '
                     'rule is still a placeholder: name the file containing the written rule and quote an exact sentence']


@pytest.mark.parametrize('reason', [
    ledger.PLACEHOLDER_UNVERIFIED,
    '换成真实的理由：为什么这个判断不再回放、由什么守住它（不少于 8 个词）',
])
def test_old_and_current_unverified_placeholders_stay_invalid(shop, reason):
    add_entry(shop, '\n[unverified]\nLIMIT = ' + ledger._quote(reason) + '\n')
    entries, red = ledger.unverified(load_config(shop))
    assert entries == {}
    assert [finding.text for finding in red] == [
        'Fallback ledger [unverified] item "LIMIT": '
        'reason is still a placeholder: explain why replay is unavailable and what checks it instead']


@pytest.mark.parametrize('section, reader, empty, replacement', [
    ('unverified', ledger.unverified, ({}, []), ' -> do not use it'),
    # a [structure] decision names its 4.3 replacement
    ('structure', ledger.structure_decisions, ({}, [], []),
     ' -> write [known.<id>] in .flowguard/known.toml with act = "ignore" or "leave"'),
])
def test_legacy_ledger_sections_warn_only_when_present(shop, capsys, section, reader, empty, replacement):
    assert reader(load_config(shop)) == empty
    assert capsys.readouterr().err == ''
    add_entry(shop, '\n[' + section + ']\n')
    assert reader(load_config(shop)) == empty
    assert capsys.readouterr().err.splitlines() == [
        'deprecated: ledger [' + section + '] goes in 5.0' + replacement]


def test_word_count_reads_latin_words_and_cjk_characters():
    assert ledger.words('the caller shows the value as unknown here') == 8
    assert ledger.words('调用方把缺失值显示为未知') == 6
    assert ledger.words('(finding, ...) os.path') == 2


def test_malformed_entries_are_red_without_a_second_report_for_their_key(shop):
    append(shop, LOOKUP)
    add_entry(shop, '\n["src/shop/stock.py:lookup:KeyError"]\ncount = 0\nreason = 3\nwhy = "x"\n\n[options]\nx = 1\n')
    assert texts(evaluate(shop, head(shop))) == [
        'Fallback ledger entry "src/shop/stock.py:lookup:KeyError": unknown field why；missing rule；count must be a positive integer；reason must be a string',
        'Fallback ledger item "options" is not an entry: the key must be "file:function:caught type" and the value a table']
    write(shop, ledger.LEDGER, 'not toml = = 1\n')
    found = texts(evaluate(shop, head(shop)))
    assert len(found) == 1 and found[0].startswith('Cannot read fallback ledger .flowguard/ledger.toml: ')


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
    assert len(result.red) == len(found) and all(text.startswith('Form cannot be registered: ') for text in texts(result))


def test_ledger_init_also_covers_refused_forms_and_round_trips_its_toml(tmp_path):
    write(tmp_path, 'forms.py', FORMS)
    for text in ('tab\there "quoted" \\ back', 'delete\x7f and \x01', '中文：键'):
        assert tomllib.loads('key = ' + ledger._quote(text))['key'] == text
    report = init(tmp_path)
    assert report[0].startswith('FlowGuard fallback ledger created: .flowguard/ledger.toml, 14 legacy entries, 14 handlers (14 forms cannot be newly registered)')
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
    assert texts(evaluate(shop, baseline))[0].startswith('Form cannot be registered: src/shop/stock.py:5,9 except Exception')
    write(shop, ledger.LEDGER, original.replace('count = 1', 'count = 2'))
    assert texts(evaluate(shop, baseline))[0].startswith(
        'Only ledger init may record legacy entries: "src/shop/stock.py:old_reader:Exception" claims 2 legacy handlers, but ledger init and the baseline record only 1')
    # A new function cannot borrow the legacy marker either.
    write(shop, 'src/shop/stock.py', LEGACY_CODE + SWALLOW)
    write(shop, ledger.LEDGER, original + entry('src/shop/stock.py:swallow:Exception', reason=ledger.LEGACY_REASON,
                                               rule=ledger.LEGACY_RULE))
    assert texts(evaluate(shop, baseline))[0].startswith('Only ledger init may record legacy entries: "src/shop/stock.py:swallow:Exception"')
    # Fixing the legacy handler shrinks the ledger: the stale entry is red until it is removed.
    write(shop, 'src/shop/stock.py', 'def old_reader(values, key):\n    return values.get(key)\n')
    write(shop, ledger.LEDGER, original)
    assert texts(evaluate(shop, baseline)) == [
        'Code disappeared: ledger entry "src/shop/stock.py:old_reader:Exception" records 1 handlers, but none remain in the code']
    write(shop, ledger.LEDGER, ledger.HEADER)
    assert evaluate(shop, baseline).red == []


def test_without_a_baseline_or_init_record_legacy_entries_stay_unverified(tmp_path):
    write(tmp_path, 'app.py', LEGACY_CODE)
    init(tmp_path)
    (tmp_path / '.flowguard/cache' / ledger.INIT_RECORD).unlink()
    result = evaluate(tmp_path)
    assert result.red == [] and result.grey == ['1 legacy entries are unverified: the baseline contains neither a ledger nor a ledger init record']


def test_deleting_the_ledger_is_red_while_the_baseline_commit_still_has_it(shop):
    (shop / ledger.LEDGER).unlink()
    result = evaluate(shop, head(shop))
    assert not result.present and texts(result) == [
        'Fallback ledger .flowguard/ledger.toml existed at the baseline but is now missing: deleting the ledger cannot clear a fallback failure']
    # Commits keep a task's baseline, so the step names the command that starts the next task there.
    assert result.red[0].fix[0].endswith('if the ledger is intentionally retired, commit its removal and start a new task with python -m flowguard new-task')
    git(shop, 'commit', '-qam', 'stop using the ledger')
    assert evaluate(shop, head(shop)).red == []           # Once the deletion is the baseline, nothing is checked.


def test_a_baseline_commit_missing_from_the_clone_leaves_legacy_unverified_not_crashed(shop):
    missing = 'f' * 40
    assert evaluate(shop, missing).red == []              # The init record still vouches for the legacy entry.
    (shop / '.flowguard/cache' / ledger.INIT_RECORD).unlink()
    result = evaluate(shop, missing)
    assert result.red == [] and len(result.grey) == 1
    assert result.grey[0].startswith('1 legacy entries are unverified: the baseline contains neither a ledger nor a ledger init record；Cannot read baseline commit ffffffffffff: ')


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
    assert init(tmp_path)[0].startswith('FlowGuard fallback ledger created')


def test_the_scan_scope_is_every_mapped_file_unless_configured(tmp_path):
    write(tmp_path, 'app.py', LOOKUP)
    write(tmp_path, 'scripts/tool.py', LOOKUP)
    write(tmp_path, 'tests/test_app.py', LOOKUP)
    write(tmp_path, 'tests/fixtures/sample.py', LOOKUP)
    write(tmp_path, ledger.LEDGER, ledger.HEADER)
    files = lambda: sorted(text.removeprefix('New unregistered fallback: ').split()[0].split(':')[0] for text in texts(evaluate(tmp_path)))
    assert files() == ['app.py', 'scripts/tool.py', 'tests/fixtures/sample.py', 'tests/test_app.py']
    write(tmp_path, 'pyproject.toml', '[tool.flowguard.ledger]\npaths = ["app.py", "tests"]\nexclude = ["tests/fixtures/**"]\n')
    assert files() == ['app.py', 'tests/test_app.py']
    write(tmp_path, ledger.LEDGER, ledger.HEADER + entry('scripts/tool.py:lookup:KeyError'))
    write(tmp_path, 'AGENTS.md', RULE + '\n')
    assert 'File for fallback ledger entry "scripts/tool.py:lookup:KeyError" is outside the ledger scan scope' in texts(evaluate(tmp_path))
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
    assert len(result.grey) == 1 and result.grey[0].startswith('_tmp_x.py:broken:KeyError is unverified: source parse failed')


def test_other_languages_supply_rows_through_the_same_fields(tmp_path):
    """A foreign reader's handler rows get the same key and their language; no Python-only refusal applies.
    A JS/TS row names its enclosing named function, so an anonymous callback's line never enters the key."""
    class Rows:
        def reset_query_coverage(self):
            pass

        def handlers(self):
            return [dict(node='typescript/src/employee.service.ts:<anonymous@2178>', file='src/employee.service.ts',
                         line=2180, kind='catch', type='any', function='syncEmployee', non_raising=True, ends='log'),
                    dict(node='typescript/src/employee.service.ts:forward', file='src/employee.service.ts', line=9,
                         kind='catch', type='any', function='forward', non_raising=False, ends='handed')]

        def python_calls(self):
            return []

        def query_coverage(self):
            return dict(queried=['handlers'], complete=True, issues=[])

    found, unread = ledger.fallbacks(load_config(tmp_path), Rows())
    assert found == {'src/employee.service.ts:syncEmployee:any': [ledger.Fallback(
        'src/employee.service.ts:syncEmployee:any', 'src/employee.service.ts', 'syncEmployee', 'any', 2180, 'catch',
        'typescript', '', 'log')]} and unread == {}


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
    assert ('red: ledger: New unregistered fallback: stock.py:12 except KeyError can end without raising '
            '-> python -m flowguard ledger check prints what to change') in output.splitlines(), output
    # The entry to copy is the red's detail: show --last prints it under the line, as ledger check does.
    shown_last = last(shop)
    block = shown_last[shown_last.index('    to retain this handler, in .flowguard/ledger.toml add:'):]
    assert block.splitlines()[1:5] == ['    ["src/shop/stock.py:lookup:KeyError"]', '    count = 1',
                                      '    reason = ' + ledger._quote(ledger.PLACEHOLDER_REASON),
                                      '    rule = { file = "file containing the written rule", text = "an exact sentence that must occur in that file" }']
    assert 'old_reader' not in output                       # The legacy entry is not reported.
    assert attempt(shop)['sentinel'] == 'ok'                # The intent collection itself stayed complete.
    # The plugin route also fails a run that does not collect the sentinel.
    partial = pytest_run(shop, 'tests/test_stock.py')
    assert partial.returncode == 1 and 'red: ledger: New unregistered fallback' in partial.stdout, partial.stdout + partial.stderr
    add_entry(shop, entry('src/shop/stock.py:lookup:KeyError'))
    green = pytest_run(shop)
    assert green.returncode == 0 and '2 passed' in green.stdout and not re.search(r'^red: ', green.stdout, re.M), green.stdout + green.stderr
    (shop / ledger.LEDGER).unlink()                         # Deleting the ledger does not turn it off.
    deleted = pytest_run(shop)
    assert deleted.returncode == 1 and 'red: ledger: Fallback ledger ledger.toml existed at the baseline but is now missing' in deleted.stdout, \
        deleted.stdout + deleted.stderr


def test_ledger_check_and_check_list_the_differences_without_running_tests(shop):
    absent = cli(shop.parent, 'ledger', 'check')
    assert absent.returncode == 0 and 'no .flowguard/ledger.toml' in absent.stdout
    clean = cli(shop, 'ledger', 'check')
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert clean.stdout.splitlines() == ['FlowGuard fallback ledger: 1 entries (1 legacy), 1 code handlers; 0 red, 0 unverified']
    append(shop, SWALLOW)
    red = cli(shop, 'ledger', 'check')
    assert red.returncode == 1 and 'red: Form cannot be registered: src/shop/stock.py:' in red.stdout, red.stdout + red.stderr
    checked = cli(shop, 'check')
    assert checked.returncode == 1 and 'red: ledger: Form cannot be registered: stock.py:12 except Exception' in checked.stdout, \
        checked.stdout + checked.stderr
    again = cli(shop, 'ledger', 'init')
    assert again.returncode == 2 and 'already exists' in again.stderr
    (shop / ledger.LEDGER).unlink()
    deleted = cli(shop, 'ledger', 'check')
    assert deleted.returncode == 1 and 'is now missing' in deleted.stdout, deleted.stdout + deleted.stderr


def test_check_base_compares_the_ledger_with_the_named_commit_in_a_project_without_rules(shop):
    """check --base X without intent rules reads the ledger against X, like check --static --base X, not against the
    task baseline: a ledger deleted after X stays red."""
    (shop / ledger.LEDGER).unlink()
    git(shop, 'commit', '-qam', 'stop using the ledger')
    cli(shop, 'new-task')                                   # the task baseline is the commit without a ledger
    assert cli(shop, 'check').returncode == 0
    for command in (('check', '--base', 'HEAD~1'), ('check', '--static', '--base', 'HEAD~1')):
        run = cli(shop, *command)
        assert run.returncode == 1 and 'is now missing' in run.stdout, (command, run.stdout + run.stderr)
        # the first line names the option that gave the baseline, with FlowGuard's own seconds
        assert re.fullmatch(r'FlowGuard \d+\.\d+ \(since --base HEAD~1\): 1 red; \d+\.\d s', run.stdout.splitlines()[0]), run.stdout


def test_ledger_init_says_when_pytest_does_not_load_the_plugin(tmp_path):
    write(tmp_path, 'app.py', LOOKUP)
    started = cli(tmp_path, 'ledger', 'init')
    assert started.returncode == 0, started.stdout + started.stderr
    assert started.stdout.splitlines()[-1].startswith('pytest does not load the FlowGuard plugin yet')
    write(tmp_path / 'other', 'app.py', LOOKUP)
    write(tmp_path / 'other', 'tests/conftest.py', 'pytest_plugins = ["flowguard.intent.plugin"]\n')
    started = cli(tmp_path / 'other', 'ledger', 'init')
    assert 'pytest does not load' not in started.stdout, started.stdout + started.stderr


def test_junit_xml_has_the_ledger_red_once_with_or_without_the_sentinel(shop, tmp_path):
    import xml.etree.ElementTree as ET

    def failed(path):
        suite = ET.parse(path).getroot().find('testsuite')
        return suite.get('failures'), sorted(case.get('classname') + '::' + case.get('name')
                                             for case in suite.iter('testcase') if case.find('failure') is not None)
    sentinel(shop)
    git(shop, 'add', '-A')
    git(shop, 'commit', '-qm', 'sentinel')
    append(shop, LOOKUP)
    whole = pytest_run(shop, f'--junitxml={tmp_path / "whole.xml"}')
    assert whole.returncode == 1 and 'red: ledger: New unregistered fallback' in whole.stdout, whole.stdout + whole.stderr
    # The sentinel test fails on the ledger: the session adds no second failure for the same red.
    assert failed(tmp_path / 'whole.xml') == ('1', ['tests.test_flowguard_intent::test_flowguard_intent'])
    partial = pytest_run(shop, 'tests/test_stock.py', f'--junitxml={tmp_path / "partial.xml"}')
    assert partial.returncode == 1 and 'red: ledger: New unregistered fallback' in partial.stdout, partial.stdout + partial.stderr
    assert failed(tmp_path / 'partial.xml') == ('1', ['flowguard::session'])


ENDINGS_TS = '''export function allowedRoles(code: string) {
  try { return readRoles(code); } catch (error) { return DEFAULTS[code] ?? []; }
}
export function syncAll(items: string[]) {
  for (const item of items) { try { sync(item); } catch { /* skip the item */ } }
}
export function notify(id: string) {
  try { send(id); } catch (error) { console.error('notify failed', id); this.logger.warn('again'); }
}
export function load(setError: (text: string) => void) {
  try { fetchAll(); } catch (error) { setError(String(error)); }
}
export function maybe(flag: boolean) {
  try { work(); } catch (error) { if (flag) { throw error; } }
}
let cached: string[] = [];
export function scopes() { try { cached = readScopes(); } catch { cached = defaultScopes(); } return cached; }
'''
ENDINGS_PY = '''def old_reader(values, key):
    try:
        return values[key]
    except KeyError:
        return None


def quiet(work, log):
    try:
        work()
    except ValueError:
        log.warning('work failed')


def nothing(work):
    try:
        work()
    except OSError:
        pass


def told(work, show):
    try:
        work()
    except LookupError as error:
        show(str(error))
'''


def test_check_all_lists_unreviewed_legacy_fallbacks_of_production_code_by_how_they_end(tmp_path):
    # Planning Tool 0.6.28 kept 232 legacy entries, all "旧账，未审", the permission read that falls back to the
    # code's default table among test-script catches, with nothing that told them apart.
    root = tmp_path / 'shop'
    write(root, 'web/roles.ts', ENDINGS_TS)
    write(root, 'src/shop/__init__.py', '')
    write(root, 'src/shop/stock.py', ENDINGS_PY)
    write(root, 'tests/roles.test.ts', "export function probe() { try { run(); } catch { } }\n")
    write(root, 'docs/archive/old.ts', "export function old() { try { run(); } catch { } }\n")
    write(root, 'AGENTS.md', '# Rules\n\n' + RULE + '\n')
    write(root, 'pyproject.toml', '[tool.pytest.ini_options]\npythonpath = ["src"]\n')
    git(root, 'init', '-q')
    cfg = load_config(root)
    with closing(build(root, workers=1)) as graph:
        ends = sorted((row['file'], row['line'], row['ends']) for row in graph.handlers() if row['file'] != 'docs/archive/old.ts')
        assert ends == [('src/shop/stock.py', 4, 'substitute'), ('src/shop/stock.py', 11, 'log'), ('src/shop/stock.py', 18, 'empty'),
                        ('src/shop/stock.py', 25, 'other'), ('tests/roles.test.ts', 1, 'empty'),
                        ('web/roles.ts', 2, 'substitute'), ('web/roles.ts', 5, 'empty'), ('web/roles.ts', 8, 'log'),
                        ('web/roles.ts', 11, 'other'), ('web/roles.ts', 14, 'handed'), ('web/roles.ts', 17, 'substitute')], ends
        ledger.init(cfg, graph)
    # A reviewed entry (a real reason and rule) is no longer legacy and is not listed.
    path = root / ledger.LEDGER
    text = path.read_text(encoding='utf-8')
    legacy = '\n'.join(ledger._entry_lines('src/shop/stock.py:quiet:ValueError', 1, reason=ledger.LEGACY_REASON, rule=ledger.LEGACY_RULE))
    assert legacy in text
    path.write_text(text.replace(legacy, entry('src/shop/stock.py:quiet:ValueError').strip()), encoding='utf-8')
    expected = [
        '6 legacy production handlers do not propagate errors (.flowguard/ledger.toml, rule = "旧账", unreviewed; grouped by handler body):',
        '   returns or substitutes another value: 3 handlers:src/shop/stock.py:4 old_reader、web/roles.ts:2 allowedRoles、web/roles.ts:17 scopes',
        '   only logs: 1 handlers:web/roles.ts:8 notify',
        '   empty body: 2 handlers:src/shop/stock.py:18 nothing、web/roles.ts:5 syncAll',
        '   Next: review each handler. If callers need the error, let it raise or propagate; otherwise make reason explain what it does, why it may remain, and point rule to a written rule']
    with closing(build(root, workers=1)) as graph:
        assert ledger.open_legacy(cfg, graph) == expected
    # check --all and check --static --all print them as before lines, one per kind of handler body; without --all
    # none
    from flowguard.intent.cli import _legacy_lines, _owner_findings
    legacy = lambda found: [line for line in found.lines if line.name.startswith('ledger:legacy:')]
    assert legacy(_owner_findings(cfg, everything=True)) == _legacy_lines(expected) and not legacy(_owner_findings(cfg))
    assert [(line.kind, line.text, line.step) for line in _legacy_lines(expected)] == [
        ('before', f'ledger legacy: {text}', 'leave it unless your task is about it') for text in (
            'returns or substitutes another value: 3 handlers: src/shop/stock.py:4 old_reader, web/roles.ts:2 allowedRoles, web/roles.ts:17 scopes',
            'only logs: 1 handlers: web/roles.ts:8 notify', 'empty body: 2 handlers: src/shop/stock.py:18 nothing, web/roles.ts:5 syncAll')]


def test_a_catch_that_only_leaves_is_empty_and_one_that_logs_and_leaves_only_logs(tmp_path):
    # Planning Tool 0.6.28's auth.routes.ts revokePrevious ends `catch { return; }`: a bare return, continue or break
    # leaves without a value or a word, like an empty block, so check --all lists it with the empty ones.
    root = tmp_path / 'shop'
    write(root, 'web/leave.ts', '''export function revoke(token: string) {
  try { verify(token); } catch { return; }
  revokeAll(token);
}
export function each(items: string[]) {
  for (const item of items) { try { sync(item); } catch (error) { console.warn('skipped', item); continue; } }
  outer: for (const item of items) { try { sync(item); } catch { break outer; } }
}
export function stop() { try { halt(); } catch { return /* already stopped */; } }
''')
    write(root, 'src/shop/__init__.py', '')
    write(root, 'src/shop/leave.py', '''def each(items, log):
    for item in items:
        try:
            item.sync()
        except KeyError:
            continue


def first(items, log):
    try:
        items[0].sync()
    except IndexError:
        log.warning('nothing to sync')
        return
''')
    with closing(build(root, workers=1)) as graph:
        ends = sorted((row['file'], row['line'], row['ends']) for row in graph.handlers())
    assert ends == [('src/shop/leave.py', 5, 'empty'), ('src/shop/leave.py', 12, 'log'),
                    ('web/leave.ts', 2, 'empty'), ('web/leave.ts', 6, 'log'), ('web/leave.ts', 7, 'empty'),
                    ('web/leave.ts', 9, 'empty')], ends     # a comment is not a returned value


def test_a_catch_that_returns_its_answer_to_the_request_answers_it_and_a_python_return_stays_a_substitute(tmp_path):
    # An Express or Fastify route that ends `catch (error) { return res.status(500).json({...}); }` answers the
    # request with the error, so check --all does not list it with the substitutes, the way the same call without
    # `return` already was not. A value besides the answer, or a fetched body read another way, is still one.
    # Python cannot tell a response it answers with from a stand-in value: every returned value is a substitute.
    root = tmp_path / 'shop'
    write(root, 'web/routes.ts', '''export async function list(req: any, res: any) {
  try { res.json(await all()); } catch (error) { return res.status(500).json({ error: 'LIST_FAILED' }); }
}
export async function one(request: any, reply: any) {
  try { return await find(request.id); } catch (error) { return await reply.code(500).send({ error: String(error) }); }
}
export async function edit(req: any, res: any) {
  try { await save(req.body); } catch (error: any) {
    console.error('save failed', error);
    if (error.code === 'P2025') return res.status(404).json({ error: 'NOT_FOUND' });
    return res.sendStatus(500);
  }
}
export async function close(req: any, res: any) { try { await stop(); } catch { return res.end(); } }
export async function hono(ctx: any) { try { await work(); } catch (error) { return ctx.json({ error: 'FAILED' }, 500); } }
export async function guess(req: any, res: any) {
  try { await save(req.body); } catch (error) { if (req.quiet) return null; return res.status(500).json({}); }
}
export async function body(res: Response) { try { return await res.json(); } catch { return res.text(); } }
''')
    write(root, 'src/shop/__init__.py', '')
    write(root, 'src/shop/routes.py', '''def read(request, load, JSONResponse):
    try:
        return load(request)
    except LookupError:
        return JSONResponse(status_code=404, content={'error': 'NOT_FOUND'})
''')
    with closing(build(root, workers=1)) as graph:
        ends = sorted((row['file'], row['line'], row['ends']) for row in graph.handlers())
    assert ends == [('src/shop/routes.py', 4, 'substitute'),
                    ('web/routes.ts', 2, 'other'), ('web/routes.ts', 5, 'other'), ('web/routes.ts', 8, 'other'),
                    ('web/routes.ts', 14, 'other'), ('web/routes.ts', 15, 'other'), ('web/routes.ts', 17, 'substitute'),
                    ('web/routes.ts', 19, 'substitute')], ends


def test_a_catch_that_returns_its_answer_under_void_answers_the_request(tmp_path):
    # Round 24 review: `return void res.status(500).json(...)`, the Express 5 + TypeScript way to keep a handler's
    # Promise<void> type, was listed with the substitutes, while the same answer without `void` was not. Under `void`
    # a status without an answer, or a local named res, still returns a stand-in.
    root = tmp_path / 'shop'
    write(root, 'web/r.ts', '''export async function a(req: any, res: any) { try { await x(); } catch (e) { return void res.status(500).json({ error: 'X' }); } }
export async function b(req: any, res: any) { try { await x(); } catch (e) { return void (res.status(500).json({ error: 'X' })); } }
export async function c(request: any, reply: any) { try { await x(); } catch (e) { return void await reply.code(500).send({ error: 'X' }); } }
export async function d(req: any, res: any) { try { await x(); } catch (e) { return void res.status(500); } }
export async function e(db: any) { const res = await db.query('q'); try { return res.rows; } catch { return void res.json({}); } }
''')
    with closing(build(root, workers=1)) as graph:
        ends = sorted((row['line'], row['ends']) for row in graph.handlers())
    assert ends == [(1, 'other'), (2, 'other'), (3, 'other'), (4, 'substitute'), (5, 'substitute')], ends


def test_a_returned_read_through_a_response_name_or_a_response_value_stays_a_substitute(tmp_path):
    # Only method calls made one on another directly on a parameter named res, reply, response or ctx, the last one
    # sending the answer, answer the request. A query result or a fetched response kept under such a name, a
    # property on the way, a read (a header, a context value), a status without an answer, and a returned or assigned
    # response value return a stand-in: check --all lists them with the substitutes.
    root = tmp_path / 'shop'
    write(root, 'web/data.ts', '''export async function loadRows(db: any) {
  const res = await db.query('SELECT * FROM item');
  try { return res.rows.map(toItem); } catch (error) { return res.rows.filter(Boolean); }
}
export async function fetchConfig(url: string) {
  const response = await fetch(url);
  try { return await response.json(); } catch { return response.headers.get('x-default-config'); }
}
export async function user(ctx: any) { try { return await load(ctx); } catch { return ctx.get('cachedUser'); } }
export async function kind(req: any, res: any) { try { await save(req.body); } catch { return res.get('Content-Type'); } }
export async function page(req: any, res: any) { try { await save(req.body); } catch (error) { return res.app.render('error', { error }); } }
export async function hold(req: any, res: any) { try { await save(req.body); } catch { return res.status(500); } }
export async function stale(key: string) { const res = cache.read(key); try { return decode(res); } catch { return res.json({ stale: true }); } }
export async function hono(c: any) { try { return await work(); } catch (error) { return c.json({ error: 'FAILED' }, 500); } }
export async function GET(request: Request) { try { return Response.json(await load()); } catch { return Response.json({ error: 'FAILED' }, { status: 500 }); } }
export async function koa(ctx: any, next: any) { try { await next(); } catch (err: any) { ctx.status = 500; ctx.body = { error: 'FAILED' }; } }
export async function list(req: any, res: any) { try { res.json(await all()); } catch { return res.status(500).json({ error: 'LIST_FAILED' }); } }
''')
    write(root, 'pyproject.toml', '[tool.pytest.ini_options]\n')
    git(root, 'init', '-q')
    cfg = load_config(root)
    with closing(build(root, workers=1)) as graph:
        ends = sorted((row['line'], row['ends']) for row in graph.handlers())
        assert ends == [(3, 'substitute'), (7, 'substitute'), (9, 'substitute'), (10, 'substitute'), (11, 'substitute'),
                        (12, 'substitute'), (13, 'substitute'), (14, 'substitute'), (15, 'substitute'), (16, 'substitute'),
                        (17, 'other')], ends
        ledger.init(cfg, graph)
    with closing(build(root, workers=1)) as graph:
        listed = ledger.open_legacy(cfg, graph)
    assert listed[1] == ('   returns or substitutes another value: 10 handlers:web/data.ts:15 GET、web/data.ts:7 fetchConfig、web/data.ts:12 hold、web/data.ts:14 hono、web/data.ts:10 kind、web/data.ts:16 koa、web/data.ts:3 loadRows、web/data.ts:11 page、web/data.ts:13 stale、web/data.ts:9 user'), listed


def test_a_comment_before_the_returned_or_thrown_value_or_the_handed_error_is_not_that_value(tmp_path):
    # `return /* to the error middleware */ next(error)` hands the error on like `return next(error)`; a comment
    # inside the call or before a rethrown error does not hide it either.
    root = tmp_path / 'shop'
    write(root, 'web/forward.ts', '''export async function plain(req: any, res: any, next: any) { try { await work(); } catch (error) { return next(error); } }
export async function noted(req: any, res: any, next: any) { try { await work(); } catch (error) { return /* to the error middleware */ next(error); } }
export async function inside(req: any, res: any, next: any) { try { await work(); } catch (error) { next(/* to the error middleware */ error); } }
export async function again() { try { await work(); } catch (error) { throw /* as it came */ error; } }
''')
    with closing(build(root, workers=1)) as graph:
        rows = sorted((row['line'], row['ends'], row['non_raising'], row['hands_on'], row['reraise']) for row in graph.handlers())
    assert rows == [(1, 'handed', False, ['next'], False), (2, 'handed', False, ['next'], False),
                    (3, 'handed', False, ['next'], False), (4, 'handed', False, ['throw'], True)], rows
