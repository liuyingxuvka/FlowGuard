"""Shared project fixtures."""
import pytest
from pathlib import Path

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

pytest_plugins = ["flowguard.intent.plugin"]


@pytest.fixture(autouse=True)
def _deprecation_notices_of_one_run():
    """A deprecated feature's notice prints once per process (`deprecation.SAID`); each test is a run of its own,
    so a notice it expects is not withheld because an earlier test in this process already printed it."""
    from flowguard.intent import deprecation
    said = set(deprecation.SAID)
    deprecation.SAID.clear()
    yield
    deprecation.SAID.clear()
    deprecation.SAID.update(said)       # the session's own notices stay printed once


@pytest.fixture(scope='session')
def vitest_home(tmp_path_factory):
    """A folder with vitest installed (`test_vitest_adapter.VITEST`); the test projects live in its subfolders and
    resolve it from there. One install for every test module that runs vitest in a session."""
    import subprocess
    from tests.intent_engine.test_vitest_adapter import VITEST, _tool
    home = tmp_path_factory.mktemp('vitest-home')
    (home / 'package.json').write_text('{"name": "flowguard-vitest-tests", "private": true, "type": "module"}\n', encoding='utf-8')
    run = subprocess.run([_tool('npm'), 'install', '--no-audit', '--no-fund', '--legacy-peer-deps', f'vitest@{VITEST}'],
                         cwd=home, capture_output=True, encoding='utf-8', timeout=600)
    assert run.returncode == 0 and (home / 'node_modules/vitest/vitest.mjs').is_file(), \
        f'npm could not install vitest@{VITEST} for the adapter tests:\n{run.stdout}\n{run.stderr}'
    return home
