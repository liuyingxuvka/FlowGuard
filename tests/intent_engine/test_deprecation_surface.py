"""Removal notices leave the retained SDK declarations and their errors intact."""
import pytest

from flowguard.intent import api
from flowguard.intent.flow import Flow, Transition


@pytest.mark.parametrize('name,args,kwargs', [
    ('precedes', ('SAVED', 'PUBLISHED'), {}),
    ('guarded_by', ('PERMITTED', 'UPDATED'), {}),
    ('transitions', ('Job.status',), {'new': {'saved'}}),
    ('checks', ('FEE', 'FEE_CASE'), {'days': 'arg.days'}),
])
def test_deprecated_templates_still_register_real_flow_declarations(name, args, kwargs, capsys, monkeypatch):
    monkeypatch.setattr(api, 'DECLARED', [])
    declared = getattr(api, name)(*args, source='assumed: retained source contract', **kwargs)
    assert isinstance(declared, Flow) and api.DECLARED == [declared]
    assert declared.source == 'assumed: retained source contract'
    if name == 'transitions':
        assert [(step.state, step.before, step.after, step.on) for step in declared.transitions] == [
            ('Job.status', 'new', 'saved', '*')]
    else:
        assert {node.anchor for node in declared.nodes} == set(args)
    output = capsys.readouterr()
    assert output.out == ''
    assert f'deprecated: {name} goes in 5.0 -> do not use it' in output.err.splitlines()


def test_deprecated_sdk_declarations_keep_their_values_and_predicate(capsys, monkeypatch):
    monkeypatch.setattr(api, 'DECLARED', [])
    def violations(graph):
        return ['one violation'] if graph else []
    structural = api.structure_rule('ONE_SOURCE', source='assumed: one violation')(violations)
    separate = api.distinct('LEFT', 'RIGHT', why='independent answers', source='assumed: keep both')
    step = Transition('Job.status', 'new', 'saved', 'SAVE', initial=True)
    assert structural.pred is violations and structural.pred(True) == ['one violation']
    assert (separate.a, separate.b, separate.why) == ('LEFT', 'RIGHT', 'independent answers')
    assert api.DECLARED == [structural, separate]
    assert (step.state, step.before, step.after, step.on, step.initial) == (
        'Job.status', 'new', 'saved', 'SAVE', True)
    output = capsys.readouterr()
    assert output.out == ''
    for feature in ('structure_rule', 'distinct', 'Transition'):
        assert f'deprecated: {feature} goes in 5.0 -> do not use it' in output.err.splitlines()


@pytest.mark.parametrize('feature,args,kwargs,error', [
    ('transitions', ('Job.status',), {}, 'needs before='),
    ('distinct', ('LEFT', 'RIGHT'), {'why': '', 'source': 'assumed: retained'}, 'needs why='),
])
def test_deprecation_notice_does_not_accept_an_invalid_old_call(feature, args, kwargs, error, capsys):
    with pytest.raises(api.IntentError, match=error):
        getattr(api, feature)(*args, **kwargs)
    output = capsys.readouterr()
    assert output.out == ''
    assert f'deprecated: {feature} goes in 5.0 -> do not use it' in output.err.splitlines()


COPIES = {
    'orders.py': '''
        # flowguard: same ACCEPT ref
        def accept(days: int) -> bool:
            return days <= 3


        # flowguard: same ACCEPT
        def preview_accept(days: int) -> bool:
            return days <= 3


        def quote_accept(days: int) -> bool:
            return days <= 3
    ''',
    'tests/test_orders.py': '''
        from orders import accept, preview_accept, quote_accept

        def test_accept():
            assert accept(3) and preview_accept(2) and quote_accept(1)
    ''',
}


def test_no_deprecation_notice_for_the_leads_and_the_copy_discovery_flowguard_makes_itself(tmp_path):
    """A notice says that the project's own input uses a feature that goes in 5.0. Old-value and
    similar-implementation leads and copy discovery are FlowGuard's own work: a project that writes only 4.3
    spellings sees no notice in pytest, check or check --static, while show --last still keeps the leads."""
    from tests.intent_engine.test_unverified_outcome import _cli, _pytest, _project
    root = _project(tmp_path / 'p', COPIES)
    path = root / 'orders.py'
    path.write_text(path.read_text(encoding='utf-8').replace(
        'def preview_accept(days: int) -> bool:\n    return days <= 3', 'def preview_accept(days: int) -> bool:\n    return days <= 4'),
        encoding='utf-8')
    # the sealed comparison of the copies is red; check --static runs no code and compares none
    for run, red, (result, text) in (('pytest', 1, _pytest(root, '-q')), ('check', 1, _cli(root, 'check')),
                                     ('check --static', 0, _cli(root, 'check', '--static'))):
        assert result.returncode == red and ('red: same ACCEPT: ' in text) == bool(red), (run, text)
        assert 'deprecated:' not in result.stderr, (run, result.stderr)
    result, text = _cli(root, 'show', '--last')
    assert 'deprecated features used' not in text, text


def test_a_pytest_session_says_its_deprecation_notices_once_on_stderr_after_its_block(tmp_path):
    """Review of 4.3: pytest captures its collection's output, so the notices of a deprecated spelling read there (a
    `sensor` comment, an intent file's `precedes`) were lost unless pytest ran with -s. Design 4.7: deprecated goes to
    stderr; the session says each notice once, after its block."""
    import subprocess
    import sys
    from tests.intent_engine._cli_fixture import SOURCE
    root = tmp_path / 'project'
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n')
    (root / 'app.py').write_text('# flowguard: sensor LIMIT\ndef eligible(days: int):\n    return days <= 3\n')
    (root / 'tests/test_app.py').write_text('from app import eligible\n\n\ndef test_limit():\n    assert eligible(3)\n')
    (root / 'tests/intent/order_rules.py').write_text(
        "from flowguard.intent import precedes\n\nprecedes('SAVED', 'PUBLISHED', source='assumed: a draft is saved before it is published')\n")
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n')
    def run(*arguments, pytest_run=False):
        call = ('import pytest; raise SystemExit(pytest.main(sys.argv[1:]))' if pytest_run
                else 'from flowguard.__main__ import main; raise SystemExit(main(sys.argv[1:]))')
        return subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, sys.argv.pop(1)); ' + call, SOURCE, *arguments],
                              cwd=root, capture_output=True, text=True, timeout=180)
    for command in (['init', '-q', '-b', 'main'], ['add', '.']):
        subprocess.run(['git', *command], cwd=root, check=True, capture_output=True)
    done = run('--root', str(root), 'init')
    assert done.returncode == 0, done.stdout + done.stderr
    subprocess.run(['git', 'add', '.'], cwd=root, check=True, capture_output=True)
    subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'base'], cwd=root,
                   check=True, capture_output=True)
    notices = ['deprecated: sensor goes in 5.0 -> write same NAME', 'deprecated: precedes goes in 5.0 -> do not use it']
    done = run('-q', '-p', 'no:cacheprovider', pytest_run=True)
    assert 'FlowGuard ' in done.stdout and not [line for line in done.stdout.splitlines() if line.startswith('deprecated: ')], done.stdout
    assert sorted(done.stderr.strip().splitlines()[-2:]) == sorted(notices), done.stdout + done.stderr
    assert [done.stderr.count(notice) for notice in notices] == [1, 1], done.stderr
