"""Shared project fixtures for the model-aligned tests."""
import pytest,os,json
from pathlib import Path


@pytest.fixture(scope="module")
def _project_template(tmp_path_factory) -> Path:
    from _fg_helpers import map_write as write, map_git as git
    root = tmp_path_factory.mktemp("project-template") / "shop"
    write(root, "shop/__init__.py", "")
    write(root, "shop/api.py", "from shop.orders import place_order\n\ndef handle(req):\n    return place_order(req)\n")
    write(root, "shop/orders.py", "from typing import TYPE_CHECKING\nfrom shop import storage\nif TYPE_CHECKING:\n    from shop.api import handle\n\n"
          "class OrderService:\n    def place(self, x):\n        return storage.save(x)\n\ndef place_order(x):\n    return OrderService().place(x)\n")
    write(root, "shop/storage.py", "DB = {}\n\ndef save(x):\n    DB[x] = True\n    return x\n")
    write(root, "web/app.js", "import { api } from './client';\nexport const x = 1;\n")
    write(root, "web/client.js", "export const api = 2;\n")
    write(root, "tests/test_orders.py", "def test_x():\n    assert True\n")
    write(root, "tests/test_storage.py", "def test_y():\n    assert True\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "init")
    return root


@pytest.fixture()
def project(tmp_path: Path, _project_template: Path) -> Path:
    import shutil
    from pathlib import Path
    return Path(shutil.copytree(_project_template, tmp_path / "shop"))


@pytest.fixture(scope="module")
def _impact_project_template(tmp_path_factory, _project_template):
    import io
    import shutil
    from contextlib import redirect_stdout
    from pathlib import Path
    from _fg_helpers import map_write as write, map_fill as fill, map_save as save, map_run as run, map_git as git
    project = Path(shutil.copytree(_project_template, tmp_path_factory.mktemp("impact-template") / "shop"))
    with redirect_stdout(io.StringIO()):
        assert run(project, "scan")[0] == 0
    data = fill(project)
    data["components"][0]["tests"] = ["tests/test_api.py"]
    data["components"][1]["models"] = [".flowguard/models/orders_check.py"]
    data["components"][2]["models"] = [".flowguard/models/persistence.py"]
    write(project, "tests/test_api.py", "def test_api():\n    assert True\n")
    write(project, "tests/test_web.py", "def test_web():\n    assert True\n")
    data["components"][3]["tests"] = ["tests/test_web.py"]
    write(project, ".flowguard/models/orders_check.py", '''from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
MODEL_ID = "orders_check"
COMPONENTS = ["orders"]
IMPLEMENTED_BY = {"Place": "shop/orders.py:OrderService.place"}
TESTED_BY = {}
class Place:
    name = "Place"
    def __init__(self, persists=True): self.persists = persists
    def apply(self, value, state):
        saved = state[1] | {value} if self.persists else state[1]
        return [FunctionResult(value, (value, saved))]
def explorer(persists=True):
    return Explorer(Workflow((Place(persists),)), initial_states=((None, frozenset()),), external_inputs=(0, 1),
                    max_sequence_length=1, progress_steps=0,
                    invariants=(Invariant("placed_is_saved", "placing an order writes its database entry",
                                          lambda s, t: s[0] is None or s[0] in s[1]),))
def build_explorer(): return explorer()
def broken_variants(): return {"does_not_save": explorer(False)}
def conformance():
    from shop.orders import OrderService
    from shop import storage
    storage.DB.clear()
    facts = []
    for value in (0, 1):
        observed = OrderService().place(value)
        facts.extend((Fact("return matches input", observed == value, str(value)),
                      Fact("order stored", storage.DB.get(value) is True, str(value))))
    return CodeFactsReport(tuple(facts))
''')
    write(project, ".flowguard/models/persistence.py", "MODEL_ID = 'storage-proof'\nCOMPONENTS = ['storage']\ndef build_explorer():\n    pass\n")
    save(project, data)
    git(project, "add", "-A")
    git(project, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "map with checks")
    return project


@pytest.fixture()
def impact_project(tmp_path: Path, _impact_project_template: Path):
    import shutil
    from pathlib import Path
    from _fg_helpers import map_load as load
    root = Path(shutil.copytree(_impact_project_template, tmp_path / "shop"))
    return root, load(root)


@pytest.fixture()
def retired_model_project(impact_project):
    from _fg_helpers import map_write as write, map_git as git
    root, data = impact_project
    for mid in ("survivor", "retired"):
        write(root, f"tests/test_{mid}.py", "def test_safe():\n    assert True\n")
        write(root, f".flowguard/models/{mid}.py",
              f"MODEL_ID = {mid!r}\nCOMPONENTS = ['storage']\n"
              "IMPLEMENTED_BY = {'Save': 'shop/storage.py:save'}\n"
              f"TESTED_BY = {{'safe': ['tests/test_{mid}.py:test_safe']}}\n"
              + ("PARENT = 'survivor'\n" if mid == "retired" else "")
              + "def build_explorer(): pass\n")
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "retirement baseline")
    return root, data


@pytest.fixture()
def shop(tmp_path: Path) -> Path:
    import json
    import subprocess
    from flowguard.map import cli
    from _fg_helpers import proof_write as write, proof_BUGGY as BUGGY, proof_MODEL_SOURCE as MODEL_SOURCE
    root = tmp_path / "shop"
    write(root, "shop/__init__.py", "")
    write(root, "shop/orders.py", BUGGY)
    write(root, "tests/test_orders.py", "from shop.orders import OrderService\n\n"
          "def test_place_once():\n    svc = OrderService()\n    assert svc.place('o1', 5) == 'placed'\n")
    (root / ".flowguard/models").mkdir(parents=True)
    (root / ".flowguard/models/order_placement.py").write_text(MODEL_SOURCE, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    cli.main(["--root", str(root), "scan"])
    data = json.loads((root / ".flowguard/map.json").read_text(encoding="utf-8"))
    data["components"] = [{
        "id": "orders", "layer": "", "summary": "Order placement and payment",
        "responsibilities": ["place an order and charge the customer once per order id"],
        "files": ["shop/*.py"], "entrypoints": ["shop/orders.py:OrderService.place"],
        "state": ["orders by id"], "side_effects": ["charges the customer"], "depends_on": [],
        "tests": ["tests/test_orders.py"], "models": [".flowguard/models/order_placement.py"],
        "status": "draft", "fingerprint": ""}]
    (root / ".flowguard/map.json").write_text(json.dumps(data), encoding="utf-8")
    return root


@pytest.fixture()
def _no_model_execution(monkeypatch):
    import pytest
    from flowguard.map import proof

    def forbidden(*args, **kwargs):
        pytest.fail("target storage and static read must not execute a model")

    for name in ("run_models", "run_model", "run_model_in_process"):
        monkeypatch.setattr(proof, name, forbidden)
