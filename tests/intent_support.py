"""Small real inputs for FlowGuard's product rules; no expected policy answers."""
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
import ast
import os
import sys
import tempfile


class QuoteCase(Enum):
    EXACT = 'alpha beta'
    WHITESPACE = 'alpha   beta'
    ELISION = 'alpha ... gamma'
    REVERSED = 'beta alpha'
    CHANGED = 'alpha delta'
    EMPTY = ''
    ONLY_ELISION = '...'


@contextmanager
def project_paths():
    with tempfile.TemporaryDirectory(prefix='flowguard-intent-paths-') as directory:
        base = Path(directory)
        root = base / 'project'
        root.mkdir()
        source = root / 'src/app.py'
        source.parent.mkdir()
        source.touch()
        environment = root / 'custom/lib/dependency.py'
        environment.parent.mkdir(parents=True)
        environment.touch()
        (root / 'custom/pyvenv.cfg').write_text('home = interpreter\n')
        dependency = root / 'third_party/site-packages/dependency.py'
        dependency.parent.mkdir(parents=True)
        dependency.touch()
        ordinary = root / '.venv/project.py'
        ordinary.parent.mkdir()
        ordinary.touch()
        interpreter = root / 'plain_interpreter/library.py'
        interpreter.parent.mkdir()
        interpreter.touch()
        paths = {
            'source': (str(source), root),
            'empty': ('', root),
            'sibling': (str(base / 'project_other/app.py'), root),
            'environment': (str(environment), root),
            'site_packages': (str(dependency), root),
            'interpreter': (str(interpreter), root),
            'ordinary_dot_directory': (str(ordinary), root),
            'relative': ('src/app.py', root),
        }
        previous_prefix, previous_directory = sys.prefix, Path.cwd()
        try:
            sys.prefix = str(interpreter.parent)
            os.chdir(root)
            yield paths
        finally:
            os.chdir(previous_directory)
            sys.prefix = previous_prefix


@contextmanager
def quoted_document(quote):
    from flowguard.intent.sources import Source
    with tempfile.TemporaryDirectory(prefix='flowguard-intent-quote-') as directory:
        root = Path(directory)
        (root / 'contract.txt').write_text('alpha beta gamma')
        source = Source('doc', '', path='contract.txt', quote=quote)
        yield source, SimpleNamespace(root=root, authority_docs=['contract.txt'])


def expression_node(expression):
    return ast.parse(expression, mode='eval').body


def row_program(expression, spelling):
    source = {
        'direct': 'row(value={expression}, expect=True, why="retained boundary")\n',
        'alias': 'case(value={expression}, expect=True, why="retained boundary")\n',
        'module': 'intent.row(value={expression}, expect=True, why="retained boundary")\n',
        'helper': 'def helper():\n    return row(value={expression}, expect=True, why="retained boundary")\nhelper()\n',
    }[spelling]
    return ast.parse('from flowguard import intent\nfrom flowguard.intent import row as case\n'
                     'from flowguard.intent import row\nGLOBAL=1\n'
                     + source.format(expression=expression))


@contextmanager
def archive_folder(exists, *, request_api):
    with tempfile.TemporaryDirectory(prefix='flowguard-intent-archive-') as directory:
        root = Path(directory)
        path = root / '.flowguard/requests/Rfixture.md' if request_api else root / 'original.md'
        if exists:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'first record')
        yield root, path


@contextmanager
def sentinel_config(loaded, complete):
    with tempfile.TemporaryDirectory(prefix='flowguard-intent-sentinel-') as directory:
        root = Path(directory)
        config = SimpleNamespace(rootpath=root)
        if loaded:
            declared = {'tests/intent/example.py::EXAMPLE[rules]'}
            received = declared if complete else set()
            model = SimpleNamespace(declared_items=lambda: sorted(declared))
            config._flowguard_intent = SimpleNamespace(get_model=lambda: model, collected=received,
                selected=received, deferred=set(), cfg=SimpleNamespace(cache=root / '.flowguard/cache'), sentinel=None)
        previous = list(sys.path)
        try:
            yield config
        finally:
            sys.path[:] = previous
