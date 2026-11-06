"""An installed wheel exposes the decision tool without retired engine resources."""
from pathlib import Path
from email.parser import Parser
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def test_wheel_has_only_current_packages_despite_a_stale_source_manifest(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    shutil.copytree(ROOT / 'flowguard', source / 'flowguard', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT / 'pyproject.toml', source / 'pyproject.toml')
    # A removed stage left in SOURCES.txt must not leak back into the wheel.
    for name in ('_next', 'flow', 'native', 'behave'):
        package = source / 'flowguard' / name
        package.mkdir(exist_ok=True)
        (package / '__init__.py').write_text('raise RuntimeError("retired package")\n')
        (package / 'old-resource.txt').write_text('retired resource\n')
    metadata = source / 'flowguard.egg-info'
    metadata.mkdir()
    (metadata / 'SOURCES.txt').write_text(''.join(path.relative_to(source).as_posix() + '\n'
                                                for path in sorted((source / 'flowguard').rglob('*')) if path.is_file()))
    built = subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation', '--no-index',
                            '--disable-pip-version-check', '-q', '-w', str(tmp_path / 'dist'), str(source)],
                           capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    wheel, = (tmp_path / 'dist').glob('flowguard-*.whl')
    with zipfile.ZipFile(wheel) as package:
        names = package.namelist()
        metadata = Parser().parsestr(package.read(next(name for name in names if name.endswith('.dist-info/METADATA'))).decode())
        requirements = metadata.get_all('Requires-Dist', [])
        assert any(re.match(r'[A-Za-z0-9_.-]+', value)[0].lower() == 'pytest' and 'extra ==' not in value for value in requirements)
        assert 'flowguard/intent/cli.py' in names and 'flowguard/structure/api.py' in names
        assert not any(name.startswith(tuple('flowguard/' + old + '/' for old in ('flow', 'native', 'behave', '_next')))
                       for name in names)
        assert not {'flowguard/map/runner.py', 'flowguard/map/derived.py', 'flowguard/conformance.py',
                    'flowguard/pytest_shards.py', 'flowguard/templates.py'}.intersection(names)
        package.extractall(tmp_path / 'site')
    project = tmp_path / 'project'
    project.mkdir()
    code = '''import importlib.util,sys
sys.path.insert(0,sys.argv[1])
from flowguard.intent import rule,row
from flowguard.structure import build
for name in ('flow','native','behave','_next'):
    assert importlib.util.find_spec('flowguard.'+name) is None
from flowguard.__main__ import main
assert main(['--root',sys.argv[2],'check']) == 0
'''
    probe = subprocess.run([sys.executable, '-I', '-S', '-c', code, str(tmp_path / 'site'), str(project)],
                           capture_output=True, text=True)
    assert probe.returncode == 0, probe.stdout + probe.stderr
    assert probe.stdout.strip() == 'FlowGuard check: no intent rules.'
