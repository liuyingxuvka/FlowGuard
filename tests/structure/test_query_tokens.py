"""Query words split camelCase and kebab-case without losing an old match.

4.0 lowered the text before splitting, so ``countWorkingDays`` was one word and
``show "count working days"`` could not find it. The whole identifier remains a
word too: every word the old splitter produced is still produced.
"""
import re

import pytest

from flowguard.intent import cli
from flowguard.intent.config import load_config
from flowguard.structure.query import tokens


def old_tokens(text):
    words = {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}
    cjk = re.findall(r"[一-鿿]", text)
    return words | {a + b for a, b in zip(cjk, cjk[1:])}


@pytest.mark.parametrize('text,expected', [
    ('countWorkingDays', {'countworkingdays', 'count', 'working', 'days'}),
    ('CountWorkingDays', {'countworkingdays', 'count', 'working', 'days'}),
    ('employee-lifecycle', {'employee', 'lifecycle'}),
    ('utils/employee-lifecycle.ts:assessEmployeeLifecycle', {'utils', 'employee', 'lifecycle', 'assess', 'assessemployeelifecycle'}),
    ('HTTPServerError', {'httpservererror', 'http', 'server', 'error'}),
    ('toUTF8String', {'toutf8string', 'utf', 'string'}),
    ('matlab_round', {'matlab', 'round'}),
    ('ROUND', {'round'}),
    ('在职状态', {'在职', '职状', '状态'}),
])
def test_identifier_words_are_split(text, expected):
    assert expected <= tokens(text)


@pytest.mark.parametrize('text', [
    'countWorkingDays', 'employee-lifecycle', 'HTTPServerError', 'matlab_round', 'ROUND', 'v2Value',
    'shop.policy:standing_allowed', 'grace days after expiry', 'OrganizationalUnitId', '在职 employeeStatusId',
    'x', 'a1b2c3', 'ÄpfelBirnen', 'snake_case_and-kebab-and.camelCase',
])
def test_every_old_word_is_still_a_word(text):
    assert old_tokens(text) <= tokens(text)


def test_show_finds_camel_case_functions_by_words_and_by_kebab_name(tmp_path, capsys):
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\n')
    (tmp_path / 'calendar_tools.py').write_text(
        'def countWorkingDays(start, end):\n    """Weekdays between two dates."""\n    return end - start\n\n'
        'def unrelated_total(values):\n    return sum(values)\n')
    (tmp_path / 'people.py').write_text(
        'def assessEmployeeLifecycle(record):\n    return record\n\n'
        'def payroll_export(rows):\n    return rows\n')
    cfg = load_config(tmp_path)
    results = {}
    for query in ('countWorkingDays', 'count working days', 'employee-lifecycle', 'assessEmployeeLifecycle'):
        assert cli.show(cfg, query) == 0
        results[query] = capsys.readouterr().out.splitlines()
    assert 'calendar_tools:countWorkingDays calendar_tools.py:1' in results['countWorkingDays'][1], results
    ranked = results['count working days']
    assert ranked[0] == 'show count working days' and 'calendar_tools:countWorkingDays' in ranked[1], ranked
    ranked = results['employee-lifecycle']
    assert any('people:assessEmployeeLifecycle' in line for line in ranked[1:6]), ranked
    assert 'people:assessEmployeeLifecycle people.py:1' in results['assessEmployeeLifecycle'][1], results


def test_a_text_that_may_share_no_word_shares_none():
    """may_share lets show skip splitting a text: it is False only when tokens(text) has no query word."""
    import random
    from flowguard.structure.query import may_share
    pieces = list('abcXYZ019_-.:/ ') + ['取', '整', '员', '工', '在', '职', 'İ', 'K', 'Working', 'Days', 'HTTP']
    chooser = random.Random(20)
    for _ in range(20000):
        text = ''.join(chooser.choice(pieces) for _ in range(chooser.randint(0, 12)))
        query = ''.join(chooser.choice(pieces) for _ in range(chooser.randint(0, 6)))
        words = tokens(query)
        if words & tokens(text):
            assert may_share(words, text), (query, text)
    assert not may_share(tokens('count working days'), 'utils/payroll.ts:sumHours')
    assert not may_share(tokens('取整'), '员工在职')
    assert may_share(tokens('取整'), '取 的 整')       # CJK pairs ignore what stands between the characters
