"""Strict sources (design 4.4, 4.7): `R74 "words"` and `doc PATH "words"` in rules.toml and known.toml match exactly after
normalize_newlines, against the archive, documents and authority_docs of the commit they are judged at; an intent rule
cites a rule with `rule.<id>`. The intent forms keep their whitespace-folding comparison (D23)."""
from contextlib import closing
import subprocess
import textwrap

import pytest

from flowguard.intent import deps, owners, sources
from flowguard.intent.api import IntentError
from flowguard.intent.config import load_config
from flowguard.intent.engine import Engine
from flowguard.intent.loader import load
from flowguard.map.requests import added_since, exact_quote, quote_matches, retire_request, store_request
from flowguard.structure import build


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), *arguments], check=True, capture_output=True, text=True, timeout=60).stdout


def _write(root, files):
    for name, text in dict(files).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip(), encoding='utf-8', newline='\n')


def _commit(root, files=(), message='fixture'):
    _write(root, {'.gitignore': '.flowguard/cache/\n__pycache__/\n', **dict(files)})
    if not (root / '.git').exists():
        _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '-A')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', message)
    return _git(root, 'rev-parse', 'HEAD').strip()


# ---- exact_quote and the request archive at a commit -----------------------------------------------------------

@pytest.mark.parametrize('raw, quote, matched', [
    (b'Members pay less.\n', 'Members pay less.', True),
    (b'one\r\ntwo\rthree\n', 'one\ntwo\nthree', True),          # CRLF and CR are LF on both sides
    (b'one\ntwo\n', 'one\r\ntwo', True),
    (b'\xef\xbb\xbfMembers pay less.', 'Members pay less.', True),  # a BOM is no word
    (b'Members  pay less.', 'Members pay less.', False),       # whitespace is not folded
    (b'Members pay\nless.', 'Members pay less.', False),
    (b'Members pay less.', 'Members ... less.', False),         # ... is three dots, not an elision
    (b'Members ... less.', 'Members ... less.', True),
    (b'anything', '', False),                                   # an empty quote is no evidence
])
def test_exact_quote_folds_only_line_endings(raw, quote, matched):
    assert exact_quote(raw, quote) is matched
    # The intent forms' matcher stays as it was (its own contract, tests/test_requests.py).
    assert quote_matches('Members  pay\nless.', 'Members pay less.') and quote_matches('Members pay less.', 'Members ... less.')


def test_added_since_names_a_request_this_task_stored(tmp_path):
    store_request(tmp_path, b'old words\n', identifier='R1')
    base = _commit(tmp_path)
    store_request(tmp_path, b'new words\n', identifier='R2', supersedes=['R1'])
    assert not added_since(tmp_path, base, 'R1') and added_since(tmp_path, base, 'R2')


# ---- the source forms ------------------------------------------------------------------------------------------

def test_a_strict_source_is_the_request_or_document_form_read_as_written():
    request = sources.parse('R74 "a \\"quoted\\" word"', strict=True)
    assert (request.kind, request.rids, request.quote, request.strict) == ('request', ('R74',), 'a \\"quoted\\" word', True)
    document = sources.parse('doc docs/spec.md "Weekly (KW 1-53)."', strict=True)
    assert (document.kind, document.path, document.quote, document.strict) == ('doc', 'docs/spec.md', 'Weekly (KW 1-53).', True)
    escaped = sources.parse('doc docs/spec.md "C:\\path"', strict=True)  # no shell unescaping
    assert escaped.quote == 'C:\\path'
    for text, message in (('rule.x', 'not another entry'), ('owner R1: words', 'source is R<id> "exact words"'),
                          ('assumed: x', 'source is R<id>'), ('R1 words', 'source is R<id>'), ('doc "x"', 'source is R<id>')):
        with pytest.raises(IntentError, match=message):
            sources.parse(text, strict=True)


def test_an_intent_rule_may_cite_a_rule_or_the_request_form_and_keeps_its_older_forms():
    cited = sources.parse('rule.english-skill')
    assert (cited.kind, cited.rule, cited.strict) == ('rule', 'english-skill', True)
    assert sources.parse('R74 "words"').strict and sources.parse('R74 "words"').kind == 'request'
    owner = sources.parse('owner R1: some words')
    assert (owner.kind, owner.rids, owner.strict) == ('owner', ('R1',), False)
    document = sources.parse('doc SPEC.md "At most three days."')
    assert (document.kind, document.path, document.quote, document.strict) == ('doc', 'SPEC.md', 'At most three days.', False)
    assert sources.parse('assumed: R3 says so').rids == ('R3',)
    with pytest.raises(IntentError, match=r'rule\.<id>'):
        sources.parse('nothing of the kind')


# ---- catalog_authority now ---------------------------------------------------------------------------------------

def _project(tmp_path, rules='', **files):
    _write(tmp_path, {'pyproject.toml': '[tool.flowguard]\nauthority_docs = ["docs/*.md"]\n',
                      'docs/spec.md': 'At most three days.\nWeekly totals.\n', '.flowguard/rules.toml': rules, **files})
    return load_config(tmp_path)


def _authority(cfg, text, **options):
    return sources.catalog_authority(sources.parse(text, strict=True), cfg, None, **options)


def test_a_strict_request_source_holds_only_for_current_stored_exact_words(tmp_path):
    cfg = _project(tmp_path)
    store_request(tmp_path, b'Members pay\r\nless than others.\n', identifier='R1')
    assert _authority(cfg, 'R1 "Members pay\nless than others."') == (True, 'owner R1')
    assert _authority(cfg, 'R1 "Members pay less than others."') == (
        False, '"Members pay less than others." is not in R1 -> quote the stored words exactly')
    assert _authority(cfg, 'R9 "x"') == (False, "R9 is not stored -> store the owner's words with python -m flowguard req add - --id R9")
    store_request(tmp_path, b'Members pay half.\n', identifier='R2', supersedes=['R1'])
    assert _authority(cfg, 'R1 "Members pay\nless than others."') == (False, "R1 is superseded by R2 -> update it from R2's words")
    retire_request(tmp_path, 'R2')
    assert _authority(cfg, 'R2 "Members pay half."') == (False, "R2 was retired as not the owner's words -> quote the owner's own words")


def test_a_strict_document_source_needs_authority_docs_and_its_exact_words(tmp_path):
    cfg = _project(tmp_path, **{'other/notes.md': 'At most three days.\n'})
    (tmp_path / 'docs/crlf.md').write_bytes(b'Line one\r\nline two\r\n')
    assert _authority(cfg, 'doc docs/spec.md "At most three days.\nWeekly totals."') == (True, 'doc docs/spec.md')
    assert _authority(cfg, 'doc docs/crlf.md "Line one\nline two"') == (True, 'doc docs/crlf.md')
    assert _authority(cfg, 'doc docs/spec.md "At most  three days."') == (
        False, 'docs/spec.md does not contain "At most  three days." -> quote the document exactly')
    assert _authority(cfg, 'doc other/notes.md "At most three days."') == (
        False, 'other/notes.md is not in authority_docs -> list it in [tool.flowguard] authority_docs of pyproject.toml, '
               'or cite a listed document')
    assert _authority(cfg, 'doc docs/gone.md "x"') == (False, 'docs/gone.md is gone -> restore it, or cite the document that holds the words')
    assert _authority(cfg, 'doc ../docs/spec.md "x"')[1].startswith('doc ../docs/spec.md is not a path relative to the repository')


def test_rule_id_resolves_to_the_current_entry_whose_own_source_is_checked_strictly(tmp_path):
    cfg = _project(tmp_path, rules='''
        [rule.days]
        text = "At most three days."
        source = 'doc docs/spec.md "At most three days."'

        [rule.loose]
        text = "Weekly."
        source = 'doc docs/spec.md "Weekly  totals."'

        [rule.broken]
        text = "x"
    ''')
    check = lambda text: sources.authority(sources.parse(text), None, cfg, None)
    assert check('rule.days') == (True, 'rule.days')
    # The permissive matcher would accept the folded whitespace; a strict miss never falls back to it.
    assert check('rule.loose') == (False, 'rule.loose: docs/spec.md does not contain "Weekly  totals." -> quote the document exactly')
    assert check('rule.broken') == (False, 'rule.broken is an invalid entry of .flowguard/rules.toml -> python -m flowguard show rule.broken')
    assert check('rule.gone') == (False, 'rule.gone is not in .flowguard/rules.toml -> add [rule.gone] to .flowguard/rules.toml, '
                                         'or cite a rule it has')
    # The displayed words of a rule citing rule.days are its entry's.
    assert sources.cited(sources.parse('rule.days'), cfg).quote == 'At most three days.'
    assert sources.cited(sources.parse('rule.gone'), cfg).text == 'rule.gone'


# ---- judged at the baseline: the catalog's source findings -----------------------------------------------------

def _source_findings(tmp_path, base):
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, workers=1)) as graph:
        found = sources.findings(cfg, graph, owners.Change(cfg, graph, base))
    return {issue.name: issue for issue in found.issues if issue.family == 'source'}


RULE = '''
    [rule.days]
    text = "At most three days."
    source = 'doc docs/spec.md "At most three days."'
'''


def test_a_quote_this_change_removes_from_its_document_is_new_and_one_gone_at_the_start_is_not(tmp_path):
    _project(tmp_path, rules=RULE)
    base = _commit(tmp_path)
    assert _source_findings(tmp_path, base) == {}
    (tmp_path / 'docs/spec.md').write_text('At most four days.\n', encoding='utf-8')
    found = _source_findings(tmp_path, base)
    assert found['source:rule.days'].fresh == frozenset({''}) and found['source:rule.days'].parts == ((
        '', '.flowguard/rules.toml:rule.days', 'docs/spec.md does not contain "At most three days."', 'quote the document exactly'),)
    assert found['source:rule.days'].files == {'.flowguard/rules.toml', 'docs/spec.md'}
    # Committed, the next task starts with the quote already gone: the finding is old.
    base = _commit(tmp_path, message='quote gone')
    assert _source_findings(tmp_path, base)['source:rule.days'].fresh == frozenset()
    # Without a baseline nothing is new (D13).
    assert _source_findings(tmp_path, None)['source:rule.days'].fresh == frozenset()


def test_authority_docs_are_read_at_each_commit(tmp_path):
    _project(tmp_path, rules=RULE)
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs = ["other/*.md"]\n', encoding='utf-8')
    base = _commit(tmp_path)
    cfg = load_config(tmp_path)
    assert _authority(cfg, 'doc docs/spec.md "At most three days."')[0] is False
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs = ["docs/*.md"]\n', encoding='utf-8')
    cfg = load_config(tmp_path)
    assert _authority(cfg, 'doc docs/spec.md "At most three days."') == (True, 'doc docs/spec.md')
    assert _authority(cfg, 'doc docs/spec.md "At most three days."', revision=base) == (
        False, 'docs/spec.md is not in authority_docs -> list it in [tool.flowguard] authority_docs of pyproject.toml, '
               'or cite a listed document')
    assert _source_findings(tmp_path, base) == {}            # it holds now: nothing to report


def test_a_supersession_stored_in_this_task_is_new_and_one_stored_before_it_is_not(tmp_path):
    _project(tmp_path, rules='''
        [rule.members]
        text = "Members pay less."
        source = 'R14 "Members pay less."'
    ''')
    store_request(tmp_path, b'Members pay less.\n', identifier='R14')
    base = _commit(tmp_path)
    store_request(tmp_path, b'Members pay half.\n', identifier='R15', supersedes=['R14'])
    found = _source_findings(tmp_path, base)['source:rule.members']
    # D27: the owner's new words, stored in this task, replace the cited ones: red (a sanctioned 0 -> 1).
    assert found.fresh == frozenset({''}) and found.parts[0][2:] == (
        'R14 is superseded by R15 (stored in this task)', "update it from R15's words"), found.parts
    base = _commit(tmp_path, message='R15 stored')
    found = _source_findings(tmp_path, base)['source:rule.members']
    assert found.fresh == frozenset() and found.parts[0][2] == 'R14 is superseded by R15', found.parts
    # A request retired in this task makes its citation new as well.
    _write(tmp_path, {'.flowguard/rules.toml': '[rule.members]\ntext = "Members pay half."\nsource = \'R15 "Members pay half."\'\n'})
    base = _commit(tmp_path, message='cite R15')
    retire_request(tmp_path, 'R15')
    found = _source_findings(tmp_path, base)['source:rule.members']
    assert found.fresh == frozenset({''}) and found.parts[0][2] == "R15 was retired as not the owner's words", found.parts


def test_an_entry_whose_source_this_change_rewrote_is_judged_as_new(tmp_path):
    _project(tmp_path, rules=RULE.replace('At most three days."\'', 'At most two days."\''))
    base = _commit(tmp_path)
    assert _source_findings(tmp_path, base)['source:rule.days'].fresh == frozenset()
    _write(tmp_path, {'.flowguard/rules.toml': RULE.replace('At most three days."\'', 'At most 2 days."\'')})
    assert _source_findings(tmp_path, base)['source:rule.days'].fresh == frozenset({''})


# ---- intent declarations: the engine's source state ------------------------------------------------------------

INTENT = '''
    from flowguard.intent import rule


    @rule('DAYS', decides='loan days', fields={{'days': int}}, source={source!r})
    def DAYS(days):
        return days <= 3
'''


def _engine(tmp_path, source, baseline):
    _write(tmp_path, {'tests/intent/days.py': INTENT.format(source=source)})
    engine = Engine(load(load_config(tmp_path)))
    engine.baseline = baseline
    rule = engine.m.rules['DAYS']
    return engine, rule


def _state(tmp_path, source, baseline):
    engine, rule = _engine(tmp_path, source, baseline)
    return sources.source_state(engine, rule, rule.confirmed, rule.quote)


def test_an_intent_rule_citing_a_rule_is_red_when_this_change_broke_it_and_before_when_it_was_broken(tmp_path):
    _project(tmp_path, rules=RULE)
    base = _commit(tmp_path, {'tests/intent/days.py': INTENT.format(source='rule.days')})
    assert _state(tmp_path, 'rule.days', base) == ('ok', 'rule.days')
    (tmp_path / 'docs/spec.md').write_text('At most four days.\n', encoding='utf-8')
    reason = 'rule.days: docs/spec.md does not contain "At most three days." -> quote the document exactly'
    assert _state(tmp_path, 'rule.days', base) == ('red', reason)
    engine, rule = _engine(tmp_path, 'rule.days', base)
    result = engine.run_rules(rule)
    assert result['verdict'] == 'red' and reason in result['red'] and result['source_baseline'] == base, result
    base = _commit(tmp_path, message='quote gone at the start')
    assert _state(tmp_path, 'rule.days', base) == ('before', reason)
    engine, rule = _engine(tmp_path, 'rule.days', base)
    result = engine.run_rules(rule)
    # The old broken citation makes no verdict red: an item failing only on it passes (1 -> 0, design 6.1).
    assert reason not in result['red'] + result['grey'] and result['before'] == [reason] and result['source_baseline'] == base
    # A new intent rule with the same broken citation is this change's: red.
    _write(tmp_path, {'tests/intent/days.py': INTENT.format(source='rule.days').replace("'DAYS'", "'DAYS2'").replace('def DAYS', 'def DAYS2')})
    engine = Engine(load(load_config(tmp_path)))
    engine.baseline = base
    rule = engine.m.rules['DAYS2']
    assert sources.source_state(engine, rule, rule.confirmed, rule.quote)[0] == 'red'
    # Without a baseline a broken strict source stays red, as 4.2.1 kept a gone quote red.
    assert _state(tmp_path, 'rule.days', None) == ('red', reason)


def test_a_missing_rule_is_no_valid_source_for_an_intent_rule(tmp_path):
    _project(tmp_path, rules=RULE)
    base = _commit(tmp_path, {'tests/intent/days.py': INTENT.format(source='rule.days')})
    assert _state(tmp_path, 'rule.weeks', base) == (
        'red', 'rule.weeks is not in .flowguard/rules.toml -> add [rule.weeks] to .flowguard/rules.toml, or cite a rule it has')


def test_the_intent_forms_keep_their_colours_and_an_old_gone_quote_is_before(tmp_path):
    _project(tmp_path)
    base = _commit(tmp_path, {'tests/intent/days.py': INTENT.format(source='doc docs/spec.md "At most   three days."')})
    # The intent form folds whitespace (D23): it holds.
    assert _state(tmp_path, 'doc docs/spec.md "At most   three days."', base)[0] == 'ok'
    assert _state(tmp_path, 'assumed: three days', base) == ('grey', 'assumed -> confirm against actual owner words')
    (tmp_path / 'docs/spec.md').write_text('At most four days.\n', encoding='utf-8')
    gone = 'doc quote gone: docs/spec.md -> update the rule from the original'
    assert _state(tmp_path, 'doc docs/spec.md "At most   three days."', base) == ('red', gone)
    assert _state(tmp_path, 'doc docs/spec.md "At most   three days."', None) == ('red', gone)          # 4.2.1
    base = _commit(tmp_path, message='quote gone')
    assert _state(tmp_path, 'doc docs/spec.md "At most   three days."', base) == ('before', gone)


def test_an_intent_owner_source_superseded_in_this_task_is_red_and_one_superseded_before_it_is_before(tmp_path):
    _project(tmp_path)
    store_request(tmp_path, b'Three days.\n', identifier='R1')
    base = _commit(tmp_path, {'tests/intent/days.py': INTENT.format(source='owner R1')})
    assert _state(tmp_path, 'owner R1', base)[0] == 'ok'
    store_request(tmp_path, b'Four days.\n', identifier='R2', supersedes=['R1'])
    assert _state(tmp_path, 'owner R1', base) == ('red', 'R1 is no longer current -> cite the current request')
    assert _state(tmp_path, 'owner R1', None) == ('grey', 'R1 is no longer current -> cite the current request')   # 4.2.1
    base = _commit(tmp_path, message='R2 stored')
    assert _state(tmp_path, 'owner R1', base)[0] == 'before'


# ---- dependency records ------------------------------------------------------------------------------------------

def test_a_rule_citing_a_catalog_rule_depends_on_rules_toml_its_words_and_its_baseline(tmp_path):
    _project(tmp_path, rules='''
        [rule.members]
        text = "Members pay less."
        source = 'R1 "Members pay less."'
    ''')
    store_request(tmp_path, b'Members pay less.\n', identifier='R1')
    base = _commit(tmp_path, {'tests/intent/days.py': INTENT.format(source='rule.members')})
    cfg = load_config(tmp_path)
    model = load(cfg)
    with closing(build(tmp_path, workers=1)) as graph:
        plain = deps.record(cfg, model, model.rules['DAYS'], [dict(verdict='ok')], graph)['dependencies']
        judged = deps.record(cfg, model, model.rules['DAYS'], [dict(verdict='red', source_baseline=base)], graph)['dependencies']
        assert {'file:.flowguard/rules.toml', 'file:.flowguard/requests/R1.md', 'file:.flowguard/requests/R1.json',
                'authority:R1'} <= plain.keys(), sorted(plain)
        assert not any(key.startswith('baseline:') for key in plain)
        assert judged['baseline:' + base] == 'compared'
        # Reused only by a run that compares with the same commit: new-task or another --base judges it again.
        assert deps.Now(cfg, graph, baseline=base)('baseline:' + base) == 'compared'
        assert deps.Now(cfg, graph, baseline='0' * 40)('baseline:' + base) == 'other'
        assert deps.stale(dict(dependencies=judged), deps.Now(cfg, graph, baseline='0' * 40)) == ['baseline:' + base]


def test_two_rules_citing_the_owners_words_through_the_catalog_that_disagree_ask_the_owner(tmp_path):
    _project(tmp_path, rules='''
        [rule.three]
        text = "Three days."
        source = 'R1 "Three days."'

        [rule.four]
        text = "Four days."
        source = 'R2 "Four days."'
    ''', **{'tests/intent/days.py': '''
        from flowguard.intent import rule


        @rule('THREE', decides='loan days', fields={'days': int}, source='rule.three')
        def THREE(days):
            return days <= 3


        @rule('FOUR', decides='loan days', fields={'days': int}, source='rule.four')
        def FOUR(days):
            return days <= 4
    '''})
    store_request(tmp_path, b'Three days.\n', identifier='R1')
    store_request(tmp_path, b'Four days.\n', identifier='R2')
    engine = Engine(load(load_config(tmp_path)))
    result = engine.run_rules(engine.m.rules['THREE'])
    assert 'conflict THREE vs FOUR at days=4: F vs T (1 of 6 shared cells) (owner R1, R2) -> ask owner' in result['red'], result['red']


def test_check_all_fails_a_grey_rule_that_cites_the_owners_words_through_the_catalog(tmp_path):
    from flowguard.intent.cli import _owner_rules_unverified
    cfg = _project(tmp_path, rules='''
        [rule.limit]
        text = "Three days."
        source = 'R1 "Three days."'

        [rule.doc]
        text = "Three days."
        source = 'doc docs/spec.md "At most three days."'
    ''')
    grey = dict(kind='cells', verdict='grey', grey=['field days could not be read'])
    rules = {'LIMIT': dict(source='rule.limit', decides='limit'), 'DOC': dict(source='rule.doc', decides='doc'),
             'GONE': dict(source='rule.gone', decides='gone')}
    data = dict(summary=dict(rules=rules), results={name: dict(items={'cells': grey}) for name in rules})
    lines = _owner_rules_unverified(cfg, data)
    assert [line.partition(':')[0] for line in lines] == ['red LIMIT'] and '(R1)' in lines[0], lines
