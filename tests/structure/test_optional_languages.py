"""Optional grammar absence is explicit and never invents parsed source facts."""
from importlib.metadata import PackageNotFoundError
from pathlib import Path
import subprocess
import sys

import pytest


def test_python_map_needs_no_grammar_and_foreign_sources_report_unavailable(tmp_path):
    source = str(Path(__file__).resolve().parents[2])
    program = '''import importlib.metadata, sys
from contextlib import closing
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from flowguard.map.common import MapError
from flowguard.structure import build
from flowguard.structure.readers.registry import available
root = Path(sys.argv[2])
assert not any('tree-sitter' in item.metadata['Name'].lower() for item in importlib.metadata.distributions())
(root/'a.py').write_text('def allowed(x): return x > 3\\n')
with closing(build(root, workers=1)) as graph:
    assert graph.node('a:allowed') is not None
assert not any(name.startswith('tree_sitter') for name in sys.modules)
assert all(not item['installed'] for language, item in available().items() if language != 'python')
for suffix in ('js', 'ts', 'tsx', 'c', 'cpp', 'cs'):
    path = root/('foreign.' + suffix)
    path.write_text('source requires its own optional parser\\n')
    try:
        build(root, workers=1)
    except MapError as error:
        assert str(path.name) in str(error)
        assert 'reader unavailable' in str(error) and 'flowguard[languages]' in str(error)
    else:
        raise AssertionError('missing grammar was presented as parsed source')
    finally:
        path.unlink()
'''
    # -S provides a real standard-library-only interpreter, independent of the
    # host's installed extras; this is the deliberately missing-dependency case.
    result = subprocess.run([sys.executable, '-S', '-c', program, source, str(tmp_path)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('error', [ModuleNotFoundError('internal dependency failed', name='reader_internal_dependency'),
                                  PackageNotFoundError('reader-internal-package'), ImportError('internal import failed')])
def test_foreign_dispatch_does_not_relabel_an_internal_import_bug(monkeypatch, tmp_path, error):
    from flowguard.structure.extract import extract
    from flowguard.structure.readers import registry
    def broken(*args):
        raise error
    monkeypatch.setattr(registry, 'extract', broken)
    with pytest.raises(type(error)) as caught:
        extract(tmp_path, 'a.ts', b'export const value=1;', 'typescript/a.ts', False)
    assert caught.value is error
