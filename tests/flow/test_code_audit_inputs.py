"""Native devices stay typed footprint inputs, separate from staged file bytes."""
import copy
import os
from pathlib import Path

import pytest

from checkrun import run_check
from flowguard.flow import codeaudit, fallback
from flowguard.flow.parts import PartContext
from flowguard.flow.project import cache_dir
from flowguard.native.inputs import file_stamp, footprint_evidence

CASE = 'tests/test_app.py::test_load'


def test_device_footprint_is_not_project_file_evidence(project, monkeypatch):
    project.file('app.py', 'def load(): return 7\n')
    project.file('tests/test_app.py', 'from app import load\ndef test_load(): assert load() == 7\n')
    analysis = fallback.analyze(project.root, nodeids=[CASE])
    # Windows resolves os.devnull ("nul") below the current project directory.
    # Reuse the native owner's actual device stamp to exercise that projection
    # on every host; the recorded execution above is otherwise unchanged.
    device = file_stamp(os.devnull)
    assert device.get('opaque') and not device.get('sha256')
    native = copy.deepcopy(analysis)
    key = str(project.root / 'nul')
    native['recording']['footprint']['files'][key] = device
    monkeypatch.setattr(fallback, 'analyze', lambda *args, **kwargs: native)
    result = codeaudit.code_part(PartContext(project.root, codeaudit.spec(project.root, [CASE]),
                                           project.root, cache_dir(project.root)))
    assert key in result.info['analysis']['recording']['footprint']['files']
    assert 'nul' not in result.reads
    assert 'nul' not in result.info['inputs']


def test_actual_null_device_is_not_a_project_index_input(project):
    project.file('app.py', 'import os\ndef load():\n    with open(os.devnull, "rb") as source:\n        assert source.read() == b""\n    return 7\n')
    project.file('tests/test_app.py', 'from app import load\ndef test_load(): assert load() == 7\n')
    project.commit()
    checked = run_check(project.root, '--tests', CASE, '--json')
    assert checked.code == 0, checked.out
    receipt = checked.data['code_audit']
    assert 'nul' not in receipt['inputs']
    ready = run_check(project.root, '--commit-ready', '--json')
    assert ready.code == 0 and ready.data['ready'], ready.out
    spec = codeaudit.spec(project.root, [CASE])
    from flowguard.flow.jobs import lookup, Planned
    part = lookup(project.root, Planned(spec, ''))
    assert part is not None
    footprint = part.info['analysis']['recording']['footprint']
    devices = [stamp for name, stamp in footprint['files'].items()
               if Path(name).name.lower() in {'null', 'nul'} and stamp.get('opaque')]
    assert devices, footprint['files']
    assert footprint_evidence(footprint).status == 'current'


@pytest.mark.skipif(os.name == 'nt', reason='Windows reserves nul for its device, so only POSIX has this regular file')
def test_regular_file_named_nul_keeps_byte_cache_and_index_identity(project):
    project.file('nul', 'first\n')
    project.file('app.py', 'from pathlib import Path\ndef load():\n    return Path(__file__).with_name("nul").read_text()\n')
    project.file('tests/test_app.py', 'from app import load\ndef test_load(): assert load() in {"first\\n", "second\\n"}\n')
    project.commit()
    first = run_check(project.root, '--tests', CASE, '--json')
    assert first.code == 0, first.out
    original = first.data['code_audit']['inputs']['nul']
    again = run_check(project.root, '--tests', CASE, '--json')
    assert again.code == 0 and again.data['parts'][0]['cached'], again.out
    project.file('nul', 'second\n')
    project.git('add', 'nul')
    stale = run_check(project.root, '--commit-ready', '--json')
    assert stale.code == 1 and any(row['code'] == 'stale_index' and 'nul' in row['paths']
                                   for row in stale.data['reasons']), stale.out
    changed = run_check(project.root, '--tests', CASE, '--json')
    assert changed.code == 0 and not changed.data['parts'][0]['cached'], changed.out
    assert changed.data['code_audit']['inputs']['nul'] != original
    ready = run_check(project.root, '--commit-ready', '--json')
    assert ready.code == 0 and ready.data['ready'], ready.out


@pytest.mark.skipif(os.name == 'nt', reason='POSIX permits a regular symlink to its absolute null device')
def test_symlink_to_device_remains_an_actual_staged_input(project):
    (project.root / 'null_link').symlink_to(os.devnull)
    project.file('app.py', 'from pathlib import Path\ndef load():\n    return Path(__file__).with_name("null_link").read_bytes()\n')
    project.file('tests/test_app.py', 'from app import load\ndef test_load(): assert load() == b""\n')
    project.commit()
    checked = run_check(project.root, '--tests', CASE, '--json')
    assert checked.code == 0, checked.out
    assert checked.data['code_audit']['inputs']['null_link']['mode'] == '120000'
    ready = run_check(project.root, '--commit-ready', '--json')
    assert ready.code == 0 and ready.data['ready'], ready.out
