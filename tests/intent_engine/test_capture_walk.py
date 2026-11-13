"""Every test's capture walks the anchored modules again: what it finds follows the module as it is now."""
import importlib.util
import uuid
from unittest import mock

from flowguard.intent import sites
from flowguard.intent.runtime import module_codes

SOURCE = '''def plain(x):
    return x

def helper():
    return 1

def make(f):
    def call():
        return f()
    return call

runner = make(helper)       # helper is left only in runner's cell
del helper

def target(z):
    return z

def shell(*args):
    return 0

shell.__wrapped__ = target  # target is left only at the end of shell's __wrapped__
del target

class Policy:
    LIMIT = 3
    @staticmethod
    def fixed():
        return 1
    @classmethod
    def made(cls):
        return cls
    @property
    def limit(self):
        return self.LIMIT
'''


def load(path):
    spec = importlib.util.spec_from_file_location('capture_walk_' + uuid.uuid4().hex, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def found(module, path, *quals):
    return {code.co_qualname for code in module_codes(module, {(str(path), qual) for qual in quals})}


def test_walk_follows_closures_wrappers_and_class_members_as_they_change(tmp_path, monkeypatch):
    path = tmp_path / 'policy.py'
    path.write_text(SOURCE)
    module = load(path)
    quals = ('plain', 'helper', 'target', 'Policy.fixed', 'Policy.made', 'Policy.limit')
    assert found(module, path, *quals) == {'plain', 'helper', 'target', 'Policy.fixed', 'Policy.made', 'Policy.limit'}
    # A cell's holder, a __wrapped__ chain and a class attribute replaced during a test are what the next walk reads.
    monkeypatch.setattr(module, 'runner', 7)
    monkeypatch.setattr(module.shell, '__wrapped__', len)
    monkeypatch.setattr(module.Policy, 'fixed', 'retired')
    assert found(module, path, *quals) == {'plain', 'Policy.made', 'Policy.limit'}
    monkeypatch.setattr(module.Policy, 'LIMIT', module.plain)
    monkeypatch.setattr(module, 'plain', None)
    assert found(module, path, 'plain') == {'plain'}
    monkeypatch.setattr(module.Policy, 'LIMIT', 3)
    assert found(module, path, 'plain') == set()


def test_walk_finds_the_original_under_an_installed_shim(tmp_path):
    path = tmp_path / 'policy.py'
    path.write_text(SOURCE)
    module = load(path)
    original = module.plain.__code__
    with sites.intercepted(module.plain, lambda function, bound: function(*bound.args, **bound.kwargs)):
        codes = module_codes(module, {(str(path), 'plain')})
        assert original in codes and module.plain.__code__ in codes
    assert module_codes(module, {(str(path), 'plain')}) == [original]


def test_walk_asks_a_function_double_what_it_asks_a_function(tmp_path, monkeypatch):
    # mock.patch(..., spec=fn) leaves a double that passes isinstance(value, FunctionType). The walk asks every such
    # value's __code__ for its qualname, whatever file it claims, so the calls the double records (which a test of
    # the double may assert) do not depend on which files are anchored.
    path = tmp_path / 'policy.py'
    path.write_text(SOURCE)
    module = load(path)
    plain = module.plain
    for wanted in ({(str(path), 'plain')}, {('/elsewhere/policy.py', 'plain')}):
        double = mock.MagicMock(spec=plain)
        monkeypatch.setattr(module, 'plain', double)
        assert module_codes(module, wanted) == []
        assert double.method_calls == [mock.call.__code__.co_qualname.replace('.<locals>.', '.')]
        assert double.mock_calls[:3] == [mock.call.__closure__.__bool__(), mock.call.__closure__.__iter__(),
                                         mock.call.__code__.co_qualname.replace('.<locals>.', '.')]
