"""References preserve identity; only real or possible execution imports effects."""
from contextlib import closing

import pytest

from flowguard.intent import cli, deps
from flowguard.structure import build
from test_cli import project
from test_cli_incremental import calls


def recorded(cfg):
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        return deps.test_dependencies(cfg, graph)['tests/test_value.py']


def prepared(tmp_path, files, imports, expression):
    root, cfg = project(tmp_path)
    for name, text in files.items():
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
    (root / 'tests/test_value.py').write_text(imports + '\ndef test_value(): assert ' + expression + '\n')
    cli.init(cfg)
    return root, cfg


def test_qualified_submodule_does_not_execute_each_ancestor_lazy_hook(tmp_path, monkeypatch):
    root, cfg = prepared(tmp_path, {
        'pkg/__init__.py': 'import os\ndef __getattr__(name): return os.getenv("FG_N3_VALUE", "alpha")\n',
        'pkg/sub.py': 'def value(): return 3\n',
    }, 'from pkg.sub import value', 'value() == 3')
    monkeypatch.setenv('FG_N3_VALUE', 'alpha')
    assert '<unresolved>' not in recorded(cfg)
    assert cli.check(cfg, everything=True) == 0
    selected = calls(monkeypatch)
    monkeypatch.setenv('FG_N3_VALUE', 'beta')
    assert cli.check(cfg) == 0 and not selected


@pytest.mark.parametrize('where', ['parent-lazy', 'parent-initializer', 'leaf-lazy'])
def test_real_lazy_or_initializer_input_still_reruns(tmp_path, monkeypatch, where):
    body = 'import os\ndef __getattr__(name): return os.getenv("FG_N3_VALUE", "alpha")\n'
    if where == 'parent-lazy':
        files, imports, expression = {'pkg/__init__.py': body}, 'from pkg import value', 'value == "alpha"'
    elif where == 'parent-initializer':
        files = {'pkg/__init__.py': 'import os\nVALUE=os.getenv("FG_N3_VALUE", "alpha")\n',
                 'pkg/sub.py': 'from . import VALUE\ndef value(): return VALUE\n'}
        imports, expression = 'from pkg.sub import value', 'value() == "alpha"'
    else:
        files, imports, expression = {'pkg/__init__.py': '', 'pkg/sub.py': body}, 'from pkg.sub import value', 'value == "alpha"'
    root, cfg = prepared(tmp_path, files, imports, expression)
    monkeypatch.setenv('FG_N3_VALUE', 'alpha')
    assert '<unresolved>' in recorded(cfg)
    assert cli.check(cfg, everything=True) == 0
    monkeypatch.setenv('FG_N3_VALUE', 'beta')
    assert cli.check(cfg) == cli.check(cfg, everything=True) == 1


def test_registering_a_callable_literal_keeps_identity_without_executing_its_body(tmp_path, monkeypatch):
    body = 'import os\ndef effect(): return os.getenv("FG_N3_VALUE", "alpha")\nREGISTRY={"effect": effect}\ndef value(): return 3\n'
    root, cfg = prepared(tmp_path, {'owner.py': body}, 'from owner import value', 'value() == 3')
    monkeypatch.setenv('FG_N3_VALUE', 'alpha')
    assert '<unresolved>' not in recorded(cfg)
    assert cli.check(cfg, everything=True) == 0
    selected = calls(monkeypatch)
    monkeypatch.setenv('FG_N3_VALUE', 'beta')
    assert cli.check(cfg) == 0 and not selected
    (root / 'owner.py').write_text(body.replace('return 3', 'return 4'))
    assert cli.check(cfg) == 1 and selected


@pytest.mark.parametrize('style', ['dispatch', 'callback', 'alias'])
def test_invoked_or_escaping_callable_keeps_its_real_input_boundary(tmp_path, monkeypatch, style):
    body = 'import os\ndef effect(): return os.getenv("FG_N3_VALUE", "alpha")\n'
    if style == 'dispatch':
        body += 'REGISTRY={"effect": effect}\ndef value(): return REGISTRY["effect"]()\n'
    elif style == 'callback':
        body += 'def consume(fn): return fn()\ndef value(): return consume(effect)\n'
    else:
        body += 'def value():\n    fn=effect\n    return fn()\n'
    root, cfg = prepared(tmp_path, {'owner.py': body}, 'from owner import value', 'value() == "alpha"')
    monkeypatch.setenv('FG_N3_VALUE', 'alpha')
    assert '<unresolved>' in recorded(cfg)
    assert cli.check(cfg, everything=True) == 0
    monkeypatch.setenv('FG_N3_VALUE', 'beta')
    assert cli.check(cfg) == cli.check(cfg, everything=True) == 1


@pytest.mark.parametrize('style', ['default', 'decorator', 'class'])
def test_definition_time_effects_remain_part_of_module_initialization(tmp_path, monkeypatch, style):
    prefix = 'import os\n'
    if style == 'default':
        body = prefix + 'def value(x=os.getenv("FG_N3_VALUE", "alpha")): return x\n'
    elif style == 'decorator':
        body = prefix + 'def capture(fn):\n    fn.label=os.getenv("FG_N3_VALUE", "alpha")\n    return fn\n@capture\ndef value(): return value.label\n'
    else:
        body = prefix + 'class Captured:\n    label=os.getenv("FG_N3_VALUE", "alpha")\ndef value(): return Captured.label\n'
    root, cfg = prepared(tmp_path, {'owner.py': body}, 'from owner import value', 'value() == "alpha"')
    monkeypatch.setenv('FG_N3_VALUE', 'alpha')
    assert '<unresolved>' in recorded(cfg)
    assert cli.check(cfg, everything=True) == 0
    monkeypatch.setenv('FG_N3_VALUE', 'beta')
    assert cli.check(cfg) == cli.check(cfg, everything=True) == 1


@pytest.mark.parametrize('invoke', [False, True])
def test_lambda_registration_and_execution_have_separate_scopes(tmp_path, monkeypatch, invoke):
    body = 'import os\nREGISTRY={"effect": lambda: os.getenv("FG_N3_VALUE", "alpha")}\n'
    body += 'def value(): return ' + ('REGISTRY["effect"]()' if invoke else '3') + '\n'
    root, cfg = prepared(tmp_path, {'owner.py': body}, 'from owner import value',
                         'value() == ' + ('"alpha"' if invoke else '3'))
    monkeypatch.setenv('FG_N3_VALUE', 'alpha')
    assert ('<unresolved>' in recorded(cfg)) is invoke
    assert cli.check(cfg, everything=True) == 0
    selected = calls(monkeypatch)
    monkeypatch.setenv('FG_N3_VALUE', 'beta')
    assert cli.check(cfg) == (1 if invoke else 0)
    assert bool(selected) is invoke


def test_stdlib_method_rebinding_is_not_a_harmless_function_registration(tmp_path, monkeypatch):
    body = ('import os\nfrom pathlib import Path\n'
            'def fake_read(self, *args, **kwargs): return os.getenv("FG_N3_VALUE", "alpha")\n'
            'def value():\n'
            '    original=Path.read_text\n'
            '    Path.read_text=fake_read\n'
            '    try: return Path("unused.txt").read_text()\n'
            '    finally: Path.read_text=original\n')
    root, cfg = prepared(tmp_path, {'owner.py': body}, 'from owner import value', 'value() == "alpha"')
    monkeypatch.setenv('FG_N3_VALUE', 'alpha')
    assert '<unresolved>' in recorded(cfg)
    assert cli.check(cfg, everything=True) == 0
    monkeypatch.setenv('FG_N3_VALUE', 'beta')
    assert cli.check(cfg) == cli.check(cfg, everything=True) == 1


def test_a_method_on_an_unresolved_parameter_is_not_assumed_closed(tmp_path, monkeypatch):
    body = ('import os\nclass Data:\n'
            '    def read(self): return os.getenv("FG_N3_VALUE", "alpha")\n'
            'def consume(obj): return obj.read()\n'
            'def value(): return consume(Data())\n')
    root, cfg = prepared(tmp_path, {'owner.py': body}, 'from owner import value', 'value() == "alpha"')
    monkeypatch.setenv('FG_N3_VALUE', 'alpha')
    assert '<unresolved>' in recorded(cfg)
    assert cli.check(cfg, everything=True) == 0
    monkeypatch.setenv('FG_N3_VALUE', 'beta')
    assert cli.check(cfg) == cli.check(cfg, everything=True) == 1


def test_an_unmodeled_path_operation_does_not_borrow_the_read_model(tmp_path, monkeypatch):
    body = ('from pathlib import Path\n'
            'def value(): return "alpha" if (Path(__file__).parent / "data.txt").exists() else "beta"\n')
    root, cfg = prepared(tmp_path, {'owner.py': body}, 'from owner import value', 'value() == "alpha"')
    (root / 'data.txt').write_text('present')
    assert '<unresolved>' in recorded(cfg)
    assert cli.check(cfg, everything=True) == 0
    (root / 'data.txt').unlink()
    assert cli.check(cfg) == cli.check(cfg, everything=True) == 1
