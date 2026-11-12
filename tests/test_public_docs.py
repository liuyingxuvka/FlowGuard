"""Public documentation and release gates describe the current small product."""
from __future__ import annotations

import ast
import io
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

import pytest

from flowguard.intent import cache, cli, signals
from flowguard.intent.config import load_config

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / '.agents/skills/flowguard'


class InstallerTests(unittest.TestCase):
    def test_installer_expands_literal_environment_variable_and_rejects_unset(self) -> None:
            with tempfile.TemporaryDirectory() as directory:
                env = dict(os.environ, FLOWGUARD_SKILL_TEST_TARGET=directory)
                command = [sys.executable, "scripts/install_skill.py", "--target",
                           "$FLOWGUARD_SKILL_TEST_TARGET/skills", "--dry-run"]
                good = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
                self.assertEqual(0, good.returncode, good.stderr)
                self.assertIn(str(Path(directory) / "skills" / "flowguard"), good.stdout)
                env.pop("FLOWGUARD_SKILL_TEST_TARGET")
                bad = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
                self.assertNotEqual(0, bad.returncode)
                self.assertIn("environment variable is unset", bad.stderr)

    def test_installer_copies_the_skill(self) -> None:
            with tempfile.TemporaryDirectory() as directory:
                run = lambda *extra: subprocess.run([sys.executable, "scripts/install_skill.py", "--target", directory, *extra],
                                                    cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(0, run().returncode)
                check = run("--check")
                self.assertEqual(0, check.returncode, check.stdout)
                skill = Path(directory) / "flowguard" / "SKILL.md"
                self.assertTrue(skill.is_file())
                self.assertFalse((skill.parent / "assets").exists())
                original = skill.read_bytes()
                stat = skill.stat()
                skill.write_bytes(bytes([original[0] ^ 1]) + original[1:])
                os.utime(skill, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                self.assertEqual(stat.st_size, skill.stat().st_size)
                self.assertEqual(stat.st_mtime_ns, skill.stat().st_mtime_ns)
                changed = run("--check")
                self.assertEqual(1, changed.returncode, changed.stdout)
                self.assertIn("differs: SKILL.md", changed.stdout)
                skill.write_bytes(original)
                os.utime(skill, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                cache = skill.parent / "__pycache__"
                cache.mkdir(exist_ok=True)
                (cache / "ignored.pyc").write_bytes(b"ignored")
                self.assertEqual(0, run("--check").returncode)


def test_skill_limits_modeling_and_points_to_one_local_guide():
    text = (SKILL / 'SKILL.md').read_text(encoding='utf-8')
    for condition in ('ordinary tests', 'same-name', 'independent', 'context'):
        assert condition in text.lower()
    assert 'Do not model the development task' in text
    assert not re.search(r'python -m flowguard (?:status|where|draft|decide|release)\b', text)
    assert 'show "what it decides"' in text
    assert 'not success' in text and 'No source change stays quiet unless a constraint fails.' in text
    guide = SKILL / 'reference.md'
    assert re.search(r'\[[^\]]+\]\(reference.md\)', text) and guide.is_file()
    assert 'def WINDOW(days):' in guide.read_text(encoding='utf-8')
    # The executable API example has one owner instead of copied manuals.
    for path in (ROOT / 'README.md', ROOT / 'README.zh-CN.md', ROOT / 'docs/intent-guide.md', SKILL / 'SKILL.md'):
        assert 'def WINDOW(days):' not in path.read_text(encoding='utf-8')
    prompt = (SKILL / 'agents/openai.yaml').read_text(encoding='utf-8')
    assert 'No source change stays quiet unless a' in prompt and 'python -m flowguard show' in prompt
    assert 'ordinary tests' in prompt and 'Do not model the development task' in prompt


def test_readme_no_rule_output_and_two_real_homes(tmp_path, capsys):
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    shown = re.search(r'```text\n(.*?)\n```', text, re.S)[1]
    # The README's first line exactly, but for this FlowGuard's version, the task's start commit and the seconds.
    readme = re.fullmatch(r'FlowGuard \d+\.\d+ \(since [0-9a-f]{7}\)(: .*; )\d+\.\d s', shown)
    assert readme, shown
    bare = tmp_path / 'bare'
    bare.mkdir()
    for command in (['init', '-q', '-b', 'main'], ['-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-q',
                                                   '--allow-empty', '-m', 'start']):
        subprocess.run(['git', '-C', str(bare), *command], check=True, capture_output=True)
    head = subprocess.run(['git', '-C', str(bare), 'rev-parse', 'HEAD'], check=True, capture_output=True, text=True).stdout
    assert cli.screen(load_config(bare), new_task=True) == 0
    capsys.readouterr()
    assert cli.check(load_config(bare)) == 0
    printed = capsys.readouterr().out.strip()
    assert re.fullmatch(re.escape(f'FlowGuard {signals.version()} (since {head[:7]}){readme[1]}') + r'\d+\.\d s', printed), printed
    # Start from exactly the reference the skill installer gives a fresh user.
    target = tmp_path / 'installed-skills'
    installed = subprocess.run([sys.executable, 'scripts/install_skill.py', '--target', str(target)],
                               cwd=ROOT, capture_output=True, text=True)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    guide = (target / 'flowguard/reference.md').read_text(encoding='utf-8')
    (tmp_path / 'policy.txt').write_text(re.search(r'```text\n(.*?)\n```', guide, re.S)[1] + '\n', encoding='utf-8')
    (tmp_path / 'pyproject.toml').write_text(re.search(r'```toml\n(.*?)\n```', guide, re.S)[1] + '\n', encoding='utf-8')
    implementation, rule = re.findall(r'```python\n(.*?)\n```', guide, re.S)[:2]
    (tmp_path / 'orders.py').write_text(implementation + '\n', encoding='utf-8')
    folder = tmp_path / 'tests/intent'
    folder.mkdir(parents=True)
    (folder / 'window.py').write_text(rule + '\n', encoding='utf-8')
    cfg = load_config(tmp_path)
    cli.init(cfg)
    capsys.readouterr()
    checked = subprocess.run([sys.executable, '-m', 'flowguard', '--root', str(tmp_path), 'check'],
                             cwd=ROOT, capture_output=True, text=True)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    saved = cache.read(cfg)['results']['WINDOW']['items']
    assert saved and all(item['verdict'] == 'ok' for item in saved.values())
    wrong = implementation.replace('def preview_accept(days: int) -> bool:\n    return days <= 3',
                                   'def preview_accept(days: int) -> bool:\n    return days <= 4')
    assert wrong != implementation
    (tmp_path / 'orders.py').write_text(wrong + '\n', encoding='utf-8')
    checked = subprocess.run([sys.executable, '-m', 'flowguard', '--root', str(tmp_path), 'check'],
                             cwd=ROOT, capture_output=True, text=True)
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert 'WINDOW' in checked.stdout
    assert any(item['verdict'] == 'red' for item in cache.read(cfg)['results']['WINDOW']['items'].values())


def test_documented_commands_use_the_real_current_parser(tmp_path, monkeypatch):
    for name in ('show', 'check', 'static_check', 'ledger', 'init', 'requests', 'screen', 'draft_anchor', 'draft_model',
                 'try_anchor', 'watch'):
        monkeypatch.setattr(cli, name, lambda *args, **kwargs: 0)
    docs = [ROOT / 'README.md', ROOT / 'README.zh-CN.md', ROOT / 'AGENTS.md', SKILL / 'SKILL.md',
            ROOT / 'docs/intent-guide.md', ROOT / 'docs/upgrade-2.0.md', ROOT / 'docs/upgrade-4.0.md', ROOT / 'docs/upgrade-4.1.md', ROOT / 'docs/upgrade-4.2.md',
            ROOT / 'docs/upgrade-4.3.md',
            SKILL / 'reference.md']
    for path in docs:
        text = path.read_text(encoding='utf-8')
        commands = re.findall(r'`python -m flowguard([^`\n]*)`', text)
        commands += [line.removeprefix('python -m flowguard') for line in text.splitlines() if line.startswith('python -m flowguard')]
        for command in commands:
            command = re.sub(r'<file\|->', 'owner.txt', command)
            command = re.sub(r'<[^>]+>', 'R1', command)
            assert cli.main(['--root', str(tmp_path), *shlex.split(command)]) == 0, (path, command)


def _publish_gate():
    workflow = (ROOT / '.github/workflows/publish-release.yml').read_text(encoding='utf-8')
    script = workflow.split("python - <<'PY'\n", 1)[1].rsplit('\n          PY', 1)[0]
    script = '\n'.join(line[10:] if line.startswith('          ') else line for line in script.splitlines())
    tree = ast.parse(script)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'successful_ci')
    import importlib.util
    spec = importlib.util.spec_from_file_location('flowguard_ci_coverage', ROOT / '.github/scripts/ci_coverage.py')
    coverage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(coverage)
    return coverage.required_jobs(), function, coverage


@pytest.mark.parametrize('defect', [None, 'sha', 'branch', 'event', 'path', 'incomplete', 'failed', 'missing_job', 'skipped_job'])
def test_publication_requires_all_current_jobs_on_the_exact_source(defect):
    required, function, coverage = _publish_gate()
    platforms = [('ubuntu-latest', '3.11'), ('ubuntu-latest', '3.13'), ('windows-latest', '3.12')]
    assert required == {f'Complete tests ({platform}, py{python})' for platform, python in platforms}
    source_sha = 'a' * 40
    repository = 'owner/FlowGuard'
    current = dict(id=42, run_attempt=1, head_sha=source_sha, head_branch='main', event='push',
                   repository={'full_name': repository}, head_repository={'full_name': repository},
                   path='.github/workflows/ci.yml', status='completed', conclusion='success', html_url='https://example/42')
    steps = {'Verify the active virtual environment before installation',
             'Verify the frozen source before execution', 'Complete unsharded intent and project tests',
             'Verify the frozen source after execution'}
    jobs = [dict(name=name, status='completed', conclusion='success', head_sha=source_sha, run_id=42, run_attempt=1,
                 steps=[dict(name=step, status='completed', conclusion='success')
                        for step in sorted(steps | ({'Verify the distributable skill in a temporary directory'}
                                                   if name == 'Complete tests (ubuntu-latest, py3.11)' else set()))])
            for name in sorted(required)]
    if defect in {'sha', 'branch', 'event', 'path', 'incomplete', 'failed'}:
        key, value = {'sha': ('head_sha', 'b' * 40), 'branch': ('head_branch', 'other'),
                      'event': ('event', 'pull_request'), 'path': ('path', '.github/workflows/partial.yml'),
                      'incomplete': ('status', 'in_progress'), 'failed': ('conclusion', 'failure')}[defect]
        current[key] = value
    elif defect == 'missing_job':
        jobs.pop()
    elif defect == 'skipped_job':
        jobs[0]['conclusion'] = 'skipped'
    calls = []
    def api(path):
        calls.append(path)
        return {'jobs': jobs}
    namespace = dict(source_sha=source_sha, required_jobs=required, api=api, coverage=coverage,
                     repository=repository, ci_run_id=42, ci_run_attempt=1)
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), '<published CI gate>', 'exec'), namespace)
    if defect:
        with pytest.raises(AssertionError):
            namespace['successful_ci'](current)
    else:
        assert namespace['successful_ci'](current) == 'https://example/42'
        assert calls == ['actions/runs/42/attempts/1/jobs?per_page=100']


def test_each_supported_ci_platform_runs_the_full_pytest_route():
    text = (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'fetch-depth: 0' in text and 'ref: ${{ github.sha }}' in text
    plan = re.findall(r'- os: ([^\s]+)\s+python: "([^"]+)"', text)
    assert len(plan) == 3 and set(plan) == {
        ('ubuntu-latest', '3.11'), ('ubuntu-latest', '3.13'), ('windows-latest', '3.12')}
    assert 'run: python -m flowguard check --all --deep' in text
    assert all(step in text for step in ('Verify the active virtual environment before installation',
           'Verify the frozen source before execution', 'Complete unsharded intent and project tests',
           'Verify the frozen source after execution'))
    assert not any(old in text for old in ('--shard', 'aggregate', 'tests/native', 'playwright', 'tests/flow', 'cancel-in-progress: true'))
    assert 'matrix.full' not in text
