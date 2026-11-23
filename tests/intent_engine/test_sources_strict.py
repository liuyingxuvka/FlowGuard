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


def test_every_reader_of_a_cited_document_decodes_it_as_the_brief_does(tmp_path, capsys):
    """Z-6 (2026-11): K2-1 taught the brief and init to read AGENTS.md and CLAUDE.md as UTF-8, or UTF-16 by their BOM
    (Windows PowerShell 5.1's `>` writes UTF-16LE with a BOM), but the rule sources that quote AGENTS.md still decoded
    strict UTF-8: with `authority_docs = ["AGENTS.md"]` and a rule `source = 'doc AGENTS.md "Add numbers exactly."'`,
    the brief printed the rule while `show rules` and `check --static` ended with `flowguard: 'utf-8' codec can't decode
    byte 0xff in position 0: invalid start byte`, exit 2, naming no file. Every reader of a document FlowGuard compares
    text from (a strict source, an intent doc source, a ledger entry's rule file, the brief, init) now reads it through
    `common.decode_text`; a document that is no such text is that source's problem, naming the file."""
    from flowguard.intent import cli, ledger
    words = '# Agents\r\n\r\nAdd numbers exactly.\r\nOne route per function.\r\n'
    _write(tmp_path, {'pyproject.toml': '[tool.flowguard]\nauthority_docs = ["AGENTS.md"]\n',
                      '.flowguard/rules.toml': '''
                          [rule.exact-add]
                          text = "add is exact"
                          source = 'doc AGENTS.md "Add numbers exactly."'
                      '''})
    (tmp_path / 'AGENTS.md').write_bytes(b'\xff\xfe' + words.encode('utf-16-le'))
    (tmp_path / 'CLAUDE.md').write_bytes(b'\xff\xfe' + '@AGENTS.md\r\n'.encode('utf-16-le'))
    _commit(tmp_path)
    cfg = load_config(tmp_path)
    assert _authority(cfg, 'doc AGENTS.md "Add numbers exactly."') == (True, 'doc AGENTS.md')
    archive = sources.shared_archive(tmp_path)
    assert sources.authority(sources.parse('doc AGENTS.md "Add   numbers exactly."'), None, cfg, archive) == (
        True, 'doc AGENTS.md')
    assert ledger._sentence_problem(cfg, ('AGENTS.md', 'One route per function.'), {}) == ''
    assert cli.show(cfg, 'rules') == 0
    assert capsys.readouterr().out.splitlines()[1:3] == [
        'rule.exact-add: add is exact', '    source: doc AGENTS.md "Add numbers exactly." (holds)']
    assert cli.static_check(cfg) == 0
    capsys.readouterr()
    # Bytes that are neither: each reader names the file and gives the decoder's own text.
    (tmp_path / 'AGENTS.md').write_bytes(b'Caf\xe9 notes. Add numbers exactly.\n')
    unreadable = ("AGENTS.md is no UTF-8 or UTF-16 text: 'utf-8' codec can't decode byte 0xe9 in position 3: invalid "
                  "continuation byte")
    step = 'save it as UTF-8, or as UTF-16 with its byte order mark'
    assert _authority(cfg, 'doc AGENTS.md "Add numbers exactly."') == (False, f'{unreadable} -> {step}')
    assert sources.authority(sources.parse('doc AGENTS.md "Add numbers exactly."'), None, cfg, archive) == (
        False, f'{unreadable} -> {step}')
    assert ledger._sentence_problem(cfg, ('AGENTS.md', 'One route per function.'), {}) == f'rule file {unreadable}'


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


def test_the_requests_a_run_cites_are_read_with_one_listing_and_once_per_process(tmp_path, monkeypatch):
    from flowguard.map import requests
    _project(tmp_path, rules=''.join(f'''
        [rule.r{index}]
        text = "Words {index}."
        source = 'R{index} "Words {index}."'
    ''' for index in range(1, 4)))
    for index in range(1, 4):
        store_request(tmp_path, f'Words {index}.\n'.encode(), identifier=f'R{index}')
    base = _commit(tmp_path)
    listings, reads = [], []
    listing, states = requests._identifiers, requests.request_states
    monkeypatch.setattr(requests, '_identifiers', lambda root: listings.append(root) or listing(root))
    monkeypatch.setattr(sources, 'request_states', lambda root, rids: reads.append(list(rids)) or states(root, rids))
    assert _source_findings(tmp_path, base) == {}
    assert len(listings) == 1 and reads == [['R1', 'R2', 'R3']], (listings, reads)
    # The engine, the dependency digests and a second static check of the same process share those rows.
    engine = Engine(load(load_config(tmp_path)))
    assert engine.archive is sources.shared_archive(tmp_path) and engine.archive.row('R2')['id'] == 'R2'
    assert _source_findings(tmp_path, base) == {} and reads == [['R1', 'R2', 'R3']]
    # A request stored since is read again: the archive changed.
    store_request(tmp_path, b'Words 1 again.\n', identifier='R4', supersedes=['R1'])
    assert set(_source_findings(tmp_path, base)) == {'source:rule.r1'} and reads[1:] == [['R1', 'R2', 'R3']]


def test_request_states_is_request_state_of_each_identifier(tmp_path):
    from flowguard.map.requests import request_state, request_states
    store_request(tmp_path, b'one\n', identifier='R1')
    store_request(tmp_path, b'two\n', identifier='R2', supersedes=['R1'])
    store_request(tmp_path, b'three\n', identifier='R3', supersedes=['R1', 'R2'])
    store_request(tmp_path, b'four\n', identifier='R4')
    retire_request(tmp_path, 'R4')
    store_request(tmp_path, b'five\n', identifier='R5')
    _commit(tmp_path)
    (tmp_path / '.flowguard/requests/R5.md').write_bytes(b'edited\n')
    identifiers = ['R3', 'R1', 'R9', 'R4', 'R2', 'R5']
    batch = request_states(tmp_path, identifiers)
    assert list(batch) == identifiers and batch == {rid: request_state(tmp_path, rid) for rid in identifiers}
    assert batch['R1']['superseded_by'] == ['R2', 'R3'] and batch['R9'] is None and batch['R4']['retired']
    assert batch['R5']['edited']


def test_dependency_records_read_the_catalog_once_per_session(tmp_path, monkeypatch):
    _project(tmp_path, rules=''.join(f'''
        [rule.r{index}]
        text = "At most three days."
        source = 'doc docs/spec.md "At most three days."'
    ''' for index in range(12)), **{'tests/intent/days.py': 'from flowguard.intent import rule\n' + ''.join(
        f"\n\n@rule('D{index}', decides='days {index}', fields={{'days': int}}, source='rule.r{index}')\n"
        f"def D{index}(days):\n    return days <= 3\n" for index in range(12))})
    cfg = load_config(tmp_path)
    model = load(cfg)
    assert len(model.rules) == 12
    reads = []
    original = sources._read_catalog
    monkeypatch.setattr(sources, '_read_catalog', lambda cfg, revision: reads.append(revision) or original(cfg, revision))
    with closing(build(tmp_path, workers=1)) as graph:
        now, found = deps.Now(cfg, graph), {}
        records = [deps.record(cfg, model, rule, [dict(verdict='ok')], graph, now, found) for rule in model.rules.values()]
    assert reads == [None], reads
    assert all('file:.flowguard/rules.toml' in item['dependencies'] for item in records)


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
    # Without a baseline nothing is compared (plan 2.3, D13, as the static findings): a broken strict source is grey.
    assert _state(tmp_path, 'rule.days', None) == ('grey', reason)
    assert _state(tmp_path, 'R9 "x"', None) == ('grey', "R9 is not stored -> store the owner's words with python -m flowguard req add - --id R9")


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


STATES = '''
    from flowguard.intent import states
    states('shop:Hire.status', ['open'], source={source!r})
'''


def _declarations(tmp_path, source, baseline):
    _write(tmp_path, {'tests/intent/days.py': STATES.format(source=source)})
    engine = Engine(load(load_config(tmp_path)))
    engine.baseline = baseline
    return [engine.run_states(engine.m.states['states:shop:Hire.status'])]


def test_states_judge_their_source_against_the_baseline_too(tmp_path):
    _project(tmp_path, **{'shop.py': 'class Hire:\n    def open(self):\n        self.status = "open"\n'})
    store_request(tmp_path, b'Only open.\n', identifier='R1')
    base = _commit(tmp_path, {'tests/intent/days.py': STATES.format(source='owner R1')})
    assert [result['verdict'] for result in _declarations(tmp_path, 'owner R1', base)] == ['ok']
    store_request(tmp_path, b'Open or held.\n', identifier='R2', supersedes=['R1'])
    gone = 'R1 is no longer current -> cite the current request'
    # D27: a request stored in this task supersedes the cited one: red, as for a rule.
    assert all(gone in result['red'] and result['source_baseline'] == base for result in _declarations(tmp_path, 'owner R1', base))
    # Without a baseline 4.2.1's colour stays: grey.
    assert all(gone in result['grey'] and gone not in result['red'] for result in _declarations(tmp_path, 'owner R1', None))
    base = _commit(tmp_path, message='R2 stored')
    for result in _declarations(tmp_path, 'owner R1', base):
        assert gone not in result['red'] + result['grey'] and result['before'] == [gone], result


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


def test_check_with_a_base_judges_again_a_source_recorded_against_the_task_baseline(tmp_path, capsys, monkeypatch):
    from tests.intent_engine import _cli_fixture as cli_fixture
    from tests.intent_engine.test_cli import project
    from flowguard.intent import cache, cli
    root, cfg = project(tmp_path)
    cli.init(cfg)
    (root / 'policy.txt').write_text('At most four days.\n')          # the quote is gone at the task start, C0
    _commit(root, message='C0')
    assert cli.screen(cfg, new_task=True) == 0
    (root / 'policy.txt').write_text('At most three days.\n')         # C1 restores it
    c1 = _commit(root, message='C1')
    (root / 'policy.txt').write_text('At most four days.\n')          # this change removes it again
    assert cli_fixture.check(cfg) == 0                                # before against C0: it fails nothing
    capsys.readouterr()
    observed = cli_fixture.calls(monkeypatch)
    # Against C1 the quote held, so this change broke it: the result recorded against C0 is not reused.
    assert cli_fixture.check(cfg, base=c1[:12]) == 1, capsys.readouterr()
    assert observed, 'check --base ran pytest again'
    assert cache.read(cfg)['results']['LIMIT']['items'], 'the result judged against C1 is recorded'


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
    assert 'conflict THREE vs FOUR at days=4: F vs T (1 of 6 shared cells) (owner R1, R2) -> the owner\'s words of the two rules disagree; only the owner can settle which holds' in result['red'], result['red']


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
    rules = {name: dict(source=f'rule.{name.lower()}', decides=name.lower(), file='tests/intent/days.py', line=line)
             for line, name in enumerate(('LIMIT', 'DOC', 'GONE'), 3)}
    data = dict(summary=dict(rules=rules), results={name: dict(items={'cells': grey}) for name in rules})
    issues = _owner_rules_unverified(cfg, data)
    assert [(issue.name, issue.family, issue.fresh) for issue in issues] == [('unverified:LIMIT', 'rule', frozenset({''}))], issues
    assert issues[0].text == ('rule LIMIT: cites original words from the owner (R1), but is now grey (unverified): field days could not '
                              'be read'), issues


# ---- R105: words of an option the owner picked (`R106 picked "words"`) ----------------------------------------------

CHOICE_OFFER = '要怎么处理旧的 PSP 字段？\nA. 先保留一个版本，并在 CHANGELOG 写迁移\nB. 直接删除\n'.encode()
CHOICE_PICKED = 'A. 先保留一个版本，并在 CHANGELOG 写迁移'
LABEL = 'Keep one version and write the migration in CHANGELOG'
ASKED = (f'How should the old PSP field be handled?\r\n1. {LABEL} - old exports stay readable\r\n'
         '2. Delete it now - the schema gets smaller\r\n').encode()


def _choices(tmp_path):
    from flowguard.map.requests import store_choice
    store_choice(tmp_path, '选 A'.encode(), CHOICE_OFFER, [CHOICE_PICKED], identifier='R106')
    store_choice(tmp_path, LABEL.encode(), ASKED, [LABEL], identifier='R107', selected=True)
    store_request(tmp_path, b'Members pay less.\n', identifier='R104')


def test_the_picked_form_is_a_strict_source_of_the_catalog_and_of_intent_rules():
    for strict in (True, False):
        source = sources.parse('R106 picked "先保留一个版本"', strict=strict)
        assert (source.kind, source.rids, source.quote, source.strict) == ('picked', ('R106',), '先保留一个版本', True)
    assert sources._source_problems('R106 picked "先保留一个版本"') == []
    # Words that start with `picked` are still the request form; `doc picked "x"` is a document named picked.
    assert sources.parse('R74 "picked \\"x\\""', strict=True).kind == 'request'
    assert sources.parse('doc picked "x"', strict=True).kind == 'doc'
    assert sources.source_text(sources.parse('R106 picked "先保留一个版本"')) == (
        'owner R106 picked "先保留一个版本" (the agent\'s option, the owner\'s pick)')
    assert sources.source_text(sources.parse('R74 "words"')) == 'words'


def test_a_picked_source_holds_only_for_words_of_an_option_the_owner_picked(tmp_path):
    cfg = _project(tmp_path)
    _choices(tmp_path)
    assert _authority(cfg, 'R106 picked "先保留一个版本"') == (
        True, 'owner R106 picked "先保留一个版本" (the agent\'s option, the owner\'s pick)')
    assert _authority(cfg, f'R106 picked "{CHOICE_PICKED}"')[0]
    # Option B was offered, not picked; words in no option are not his pick either.
    assert _authority(cfg, 'R106 picked "直接删除"') == (
        False, '"直接删除" is in the options R106 offered, not in one the owner picked -> quote the option R106 picked')
    assert _authority(cfg, 'R106 picked "保留两个版本"') == (
        False, '"保留两个版本" is not in the option R106 picked -> quote the picked option exactly')
    # His typed reply is his words; a reply he selected without typing holds the agent's option, not his words.
    assert _authority(cfg, 'R106 "选 A"') == (True, 'owner R106')
    assert _authority(cfg, f'R107 "{LABEL}"') == (
        False, 'R107\'s answer was selected, not written by the owner -> quote the option: R107 picked "words"')
    assert _authority(cfg, 'R107 picked "write the migration in CHANGELOG"')[0]
    assert sources.Archive(tmp_path).status('R107', LABEL) == (
        False, 'R107\'s answer was selected, not written by the owner -> quote the option: R107 picked "words"')
    # The counterexample: a plain request holds no options.
    assert _authority(cfg, 'R104 picked "Members pay less."') == (
        False, 'R104 holds no offered options -> quote its words: R104 "words"')
    assert _authority(cfg, 'R104 "Members pay less."') == (True, 'owner R104')


def test_a_picked_source_is_judged_at_a_commit_with_that_commits_sidecar_reply_and_offer(tmp_path):
    cfg = _project(tmp_path)
    base = _commit(tmp_path)
    _choices(tmp_path)
    # Stored in this task: at the baseline the choice is not stored, in the existing words.
    assert _authority(cfg, 'R106 picked "先保留一个版本"', revision=base) == (
        False, "R106 was not stored then -> store the owner's words with python -m flowguard req add - --id R106")
    base = _commit(tmp_path, message='choices stored')
    import shutil
    shutil.rmtree(tmp_path / '.flowguard/requests')         # nothing in the working tree: only the commit's blobs
    assert _authority(cfg, 'R106 picked "先保留一个版本"', revision=base) == (
        True, 'owner R106 picked "先保留一个版本" (the agent\'s option, the owner\'s pick)')
    assert _authority(cfg, 'R106 picked "直接删除"', revision=base)[1].startswith('"直接删除" is in the options R106 offered')
    assert _authority(cfg, f'R107 "{LABEL}"', revision=base)[1].startswith("R107's answer was selected")
    assert _authority(cfg, 'R104 picked "Members"', revision=base)[1].startswith('R104 holds no offered options')
    assert _authority(cfg, 'R106 picked "先保留一个版本"')[1].startswith('R106 is not stored')


def test_a_catalog_rule_citing_a_pick_is_a_source_finding_when_the_pick_does_not_hold(tmp_path, capsys):
    _project(tmp_path, rules='''
        [rule.psp]
        text = "Keep one version of the old PSP field and write its migration in the CHANGELOG."
        source = 'R106 picked "直接删除"'
    ''')
    _choices(tmp_path)
    base = _commit(tmp_path)
    found = _source_findings(tmp_path, base)['source:rule.psp']
    assert found.parts[0][2:] == ('"直接删除" is in the options R106 offered, not in one the owner picked',
                                  'quote the option R106 picked'), found.parts
    assert found.files == {'.flowguard/rules.toml', '.flowguard/requests/R106.md', '.flowguard/requests/offers/R106.md'}
    _write(tmp_path, {'.flowguard/rules.toml': '[rule.psp]\ntext = "Keep one version."\nsource = \'R106 picked "先保留一个版本"\'\n'})
    assert _source_findings(tmp_path, base) == {}
    from flowguard.intent import cli
    assert cli.main(['--root', str(tmp_path), 'show', 'rule.psp']) == 0
    assert capsys.readouterr().out.splitlines() == [
        'rule.psp: Keep one version.',
        '    source: R106 picked "先保留一个版本" (holds: the agent\'s option, the owner\'s pick)']


def test_an_intent_rule_citing_a_pick_holds_and_depends_on_the_offer(tmp_path):
    _project(tmp_path)
    _choices(tmp_path)
    base = _commit(tmp_path, {'tests/intent/days.py': INTENT.format(source='R106 picked "先保留一个版本"')})
    assert _state(tmp_path, 'R106 picked "先保留一个版本"', base) == (
        'ok', 'owner R106 picked "先保留一个版本" (the agent\'s option, the owner\'s pick)')
    assert _state(tmp_path, 'R106 picked "直接删除"', base)[0] == 'red'
    cfg = load_config(tmp_path)
    model = load(cfg)
    with closing(build(tmp_path, workers=1)) as graph:
        keys = deps.record(cfg, model, model.rules['DAYS'], [dict(verdict='ok')], graph)['dependencies']
    assert {'file:.flowguard/requests/R106.md', 'file:.flowguard/requests/R106.json',
            'file:.flowguard/requests/offers/R106.md'} <= set(keys), sorted(keys)


def test_check_all_fails_a_grey_rule_that_cites_the_owners_pick_and_names_it_as_his_pick(tmp_path):
    from flowguard.intent.cli import _owner_rules_unverified
    cfg = _project(tmp_path, rules='''
        [rule.psp]
        text = "Keep one version."
        source = 'R106 picked "先保留一个版本"'
    ''')
    grey = dict(kind='cells', verdict='grey', grey=['field days could not be read'])
    rules = {'PSP': dict(source='rule.psp', decides='psp', file='tests/intent/psp.py', line=3)}
    issues = _owner_rules_unverified(cfg, dict(summary=dict(rules=rules), results={'PSP': dict(items={'cells': grey})}))
    assert [issue.text for issue in issues] == ["rule PSP: cites the owner's pick among the agent's options (R106), but is "
                                                'now grey (unverified): field days could not be read'], issues
