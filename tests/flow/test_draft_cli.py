"""The public draft route is static and never overwrites author-completed files."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = '''raise RuntimeError('draft must never import the application')
class Queue:
    def __init__(self): self.phase = 'ready'
    def submit(self, job, *, urgent=False):
        if self.phase != 'ready': raise ValueError('not ready')
        self.phase = 'busy'
'''


def run(root, *arguments):
    return subprocess.run([sys.executable, '-m', 'flowguard', 'draft', *arguments,
                           '--root', str(root), '--json'], cwd=root,
                          env={**os.environ, 'PYTHONPATH': str(ROOT)},
                          capture_output=True, text=True, timeout=20)


def test_static_vocabulary_and_todos_need_no_project_execution_or_file_writes(tmp_path):
    (tmp_path / 'app.py').write_text(SOURCE)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    answer = run(tmp_path, 'app.py:Queue')
    assert answer.returncode == 0, answer.stderr
    result = json.loads(answer.stdout)
    assert result['vocabulary']['target'] == 'app.py:Queue'
    assert any(row['name'] == 'submit' for row in result['vocabulary']['operations'])
    assert 'TODO' in result['model'] and 'NotImplementedError' in result['adapter']
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before
    assert not (tmp_path / '.flowguard/flow').exists()


def test_write_once_keeps_completed_author_bytes_and_uses_the_same_draft_owner(tmp_path):
    (tmp_path / 'app.py').write_text(SOURCE)
    first = run(tmp_path, 'app.py:Queue', '--write')
    assert first.returncode == 0, first.stderr
    paths = [Path(p) for p in json.loads(first.stdout)['written']]
    assert paths == [tmp_path / '.flowguard/flow/app_Queue.py', tmp_path / '.flowguard/adapters/app_Queue.py']
    paths[0].write_text('# completed independent model\nMODEL = object()\n')
    original = [p.read_bytes() for p in paths]
    again = run(tmp_path, 'app.py:Queue', '--write')
    assert again.returncode == 1 and 'does not overwrite' in json.loads(again.stdout)['error']
    assert [p.read_bytes() for p in paths] == original


def test_explicit_output_paths_and_static_errors_are_actionable(tmp_path):
    (tmp_path / 'app.py').write_text(SOURCE)
    result = run(tmp_path, 'app.py:Queue.submit', '--write', '--model', '.flowguard/flow/submit.py',
                 '--adapter', 'adapters/submit.py')
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'adapters/submit.py').is_file()
    missing = run(tmp_path, 'app.py:Missing')
    assert missing.returncode == 2 and json.loads(missing.stdout)['error']
    assert 'Traceback' not in missing.stderr


def test_known_source_error_keeps_the_json_error_contract(tmp_path, monkeypatch, capsys):
    from flowguard.__main__ import main
    from flowguard.flow import draft as source_draft
    from flowguard.map.common import MapError
    def broken_inventory(*args, **kwargs):
        raise MapError('Git source inventory is unavailable')
    monkeypatch.setattr(source_draft, 'draft', broken_inventory)
    assert main(['draft', 'app.py', '--root', str(tmp_path), '--json']) == 2
    answer = capsys.readouterr()
    assert json.loads(answer.out) == {'error': 'Git source inventory is unavailable'}
    assert not answer.err


def test_getter_and_setter_keep_their_own_static_raise_names(tmp_path):
    (tmp_path / 'app.py').write_text("""class Program:
    @property
    def phase(self): raise GetterUnavailable('not loaded')
    @phase.setter
    def phase(self, value): raise InvalidPhase('bad value')
""")
    answer = run(tmp_path, 'app.py:Program')
    assert answer.returncode == 0, answer.stderr
    rows = json.loads(answer.stdout)['vocabulary']['queries']
    assert len(rows) == 2
    getter = next(row for row in rows if row['decorators'] == ['property'])
    setter = next(row for row in rows if row['decorators'] == ['phase.setter'])
    assert getter['raises'] == ['GetterUnavailable']
    assert setter['raises'] == ['InvalidPhase']
