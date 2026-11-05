"""Shared project fixtures for the model-aligned tests."""
import pytest
from pathlib import Path
RULE = 'a test skips only through @pytest.mark.skipif(<condition>, reason=...) and expects failure only through an xfail marker'

def _marker_holds(item, name):
    """Whether a skipif or xfail marker of this item applies: no condition, or a true one."""
    for mark in item.iter_markers(name):
        conditions = mark.args or ((mark.kwargs['condition'],) if 'condition' in mark.kwargs else ())
        if not conditions or any((bool(condition) for condition in conditions)):
            return True
    return False

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """A skipped or xfailed outcome that no skipif or xfail marker produced fails, and names any swallowed error."""
    outcome = (yield)
    report = outcome.get_result()
    if not report.skipped:
        return
    if hasattr(report, 'wasxfail') and _marker_holds(item, 'xfail'):
        return
    if not hasattr(report, 'wasxfail') and call.when == 'setup' and _marker_holds(item, 'skipif'):
        return
    excinfo = call.excinfo
    hidden = excinfo.value.__cause__ or excinfo.value.__context__ if excinfo is not None else None
    report.outcome = 'failed'
    report.longrepr = (f'skip raised while handling {type(hidden).__name__}: {hidden!r}; ' if hidden is not None else f"{('xfail' if hasattr(report, 'wasxfail') else 'skip')} not from a skipif or xfail marker: ") + RULE
    if hasattr(report, 'wasxfail'):
        del report.wasxfail

@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    """A module skipped while it is collected (importorskip, a module-level skip) is an error, not a skip."""
    outcome = (yield)
    report = outcome.get_result()
    if report.skipped:
        report.outcome = 'failed'
        report.longrepr = f'{collector.nodeid} skipped while collected, not from a skipif or xfail marker: {RULE}'

@pytest.fixture(autouse=True, scope='session')
def _outside_an_agent_session():
    """Tests run as plain processes; only tests that set the agent's session variables see status first."""
    with pytest.MonkeyPatch.context() as patch:
        patch.delenv('CLAUDECODE', raising=False)
        patch.delenv('CLAUDE_CODE_SESSION_ID', raising=False)
        yield

@pytest.fixture(scope='module')
def _project_template(tmp_path_factory) -> Path:
    from _pure_helpers import write as write, git as git
    root = tmp_path_factory.mktemp('project-template') / 'shop'
    write(root, 'shop/__init__.py', '')
    write(root, 'shop/api.py', 'from shop.orders import place_order\n\ndef handle(req):\n    return place_order(req)\n')
    write(root, 'shop/orders.py', 'from typing import TYPE_CHECKING\nfrom shop import storage\nif TYPE_CHECKING:\n    from shop.api import handle\n\nclass OrderService:\n    def place(self, x):\n        return storage.save(x)\n\ndef place_order(x):\n    return OrderService().place(x)\n')
    write(root, 'shop/storage.py', 'DB = {}\n\ndef save(x):\n    DB[x] = True\n    return x\n')
    write(root, 'web/app.js', "import { api } from './client';\nexport const x = 1;\n")
    write(root, 'web/client.js', 'export const api = 2;\n')
    write(root, 'tests/test_orders.py', 'def test_x():\n    assert True\n')
    write(root, 'tests/test_storage.py', 'def test_y():\n    assert True\n')
    git(root, 'init', '-q')
    git(root, 'add', '-A')
    git(root, '-c', 'user.email=a@b', '-c', 'user.name=t', 'commit', '-qm', 'init')
    return root

@pytest.fixture()
def project(tmp_path: Path, _project_template: Path) -> Path:
    import shutil
    from pathlib import Path
    return Path(shutil.copytree(_project_template, tmp_path / 'shop'))
