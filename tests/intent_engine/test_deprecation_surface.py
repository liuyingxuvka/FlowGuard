"""A removed spelling is red at its place with its rewrite (5.0; 4.3 printed a removal notice once per run, and 5.0
removed the notices with what they announced), and FlowGuard's own copy discovery is a line of the block."""


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


def test_copies_this_change_made_disagree_are_red_in_pytest_and_check_with_no_notice(tmp_path):
    """Copy discovery and the changed-alone comparison are FlowGuard's own work: a project that writes only 4.3
    spellings gets their red line in the block of pytest and check, and no notice on stderr in pytest, check or
    check --static (4.3 said no deprecation notice for them either)."""
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


def test_a_pytest_session_says_each_removed_spelling_red_at_its_line_with_its_rewrite(tmp_path):
    """Review of 4.3: pytest captures its collection's output, so the notices of a deprecated spelling read there were lost
    unless pytest ran with -s; the session said them once on stderr after its block. 5.0 removed the 4.2 spellings
    (`sensor`, `owner NAME` above a function) and the notices: each spelling is a red line of the block at its
    comment, its step the 4.3 comment."""
    import subprocess
    import sys
    from tests.intent_engine import _cli_fixture
    from tests.intent_engine._cli_fixture import SOURCE
    root = tmp_path / 'project'
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n')
    (root / 'app.py').write_text('# flowguard: sensor LIMIT\ndef eligible(days: int):\n    return days <= 3\n')
    (root / 'grace.py').write_text('# flowguard: owner GRACE\ndef grace(days: int):\n    return days <= 5\n')
    (root / 'tests/test_app.py').write_text('from app import eligible\n\n\ndef test_limit():\n    assert eligible(3)\n')
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
    done = run('-q', '-p', 'no:cacheprovider', pytest_run=True)
    assert done.returncode == 1 and ' passed' in done.stdout and 'failed' not in done.stdout, done.stdout + done.stderr
    assert [line for line in _cli_fixture.block(done)[1:] if line.startswith('red: ')] == [
        'red: comment app.py:1: sensor was removed in 5.0 -> write # flowguard: same LIMIT',
        'red: comment grace.py:1: owner NAME above a function was removed in 5.0 -> write # flowguard: same GRACE ref'], done.stdout
    assert 'deprecated' not in done.stdout + done.stderr, done.stdout + done.stderr
