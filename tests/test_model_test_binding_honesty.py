"""Binding honesty and source-audit idioms; no nested pytest (git subprocess only)."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import flowguard
from flowguard.model_test_alignment import (
    CodeContract,
    ModelObligation,
    ModelTestAlignmentPlan,
    TestEvidence,
    audit_python_code_contracts,
    audit_python_test_assertions,
    review_python_contract_source_audit,
)

CODE = (
    "class DuplicateOrder(Exception):\n    pass\n\n\n"
    "def place_order(orders, order_id):\n"
    "    if order_id in orders:\n        raise DuplicateOrder(order_id)\n"
    "    orders.append(order_id)\n    return {'ok': True, 'order_id': order_id}\n"
)
HEADER = "import pytest\nfrom unittest import mock\nfrom shop.orders import place_order, DuplicateOrder\n\n"


def _audit_ok(body: str, test_name: str = "test_it", state_writes=()) -> bool:
    src = {"shop/orders.py": CODE, "tests/test_x.py": HEADER + body}
    contract = CodeContract("c", path="shop/orders.py", symbol="place_order", state_writes=tuple(state_writes))
    evidence = TestEvidence("t", test_name=test_name, path="tests/test_x.py", covered_code_contracts=("c",))
    report = review_python_contract_source_audit(
        (contract,), (evidence,),
        audit_python_code_contracts((contract,), src),
        audit_python_test_assertions((evidence,), (contract,), src),
    )
    return report.ok


@pytest.mark.parametrize("body", [
    "def test_it():\n    with pytest.raises(DuplicateOrder):\n        place_order(['a'], 'a')\n",
    "def test_it():\n    pytest.raises(DuplicateOrder, place_order, ['a'], 'a')\n",
    "def test_it():\n    with pytest.raises(DuplicateOrder) as info:\n        place_order(['a'], 'a')\n    assert info.value.args == ('a',)\n",
    "def test_it():\n    for oid in ['a', 'b']:\n        assert place_order([], oid)['order_id'] == oid\n",
    "def test_it():\n    orders = []\n    place_order(orders, 'a')\n    assert orders == ['a']\n",
    "def test_it():\n    r = place_order([], 'a')\n    assert len(r) == 2\n",
])
def test_common_idioms_pass_source_audit(body):
    assert _audit_ok(body)


@pytest.mark.parametrize("body", [
    "def test_it():\n    x = place_order([], 'a')\n    assert x == x\n",
    "@mock.patch('tests.test_x.place_order', return_value={'ok': True})\ndef test_it(fake):\n    assert place_order([], 'a')['ok']\n",
    "def place_order(orders, oid):\n    return {'ok': True}\n\n\ndef test_it():\n    assert place_order([], 'a')['ok']\n",
    "def test_it():\n    x = 'a'\n    place_order([], x)\n    assert x == 'a'\n",
    "def test_it():\n    if False:\n        assert place_order([], 'a')['ok']\n",
    "def test_it():\n    try:\n        assert place_order([], 'a')['ok'] is False\n    except Exception:\n        pass\n",
    "def test_it():\n    place_order([], 'a')\n    assert True\n",
])
def test_tautologies_mocks_shadows_and_dead_asserts_stay_blocked(body):
    assert not _audit_ok(body)


def test_state_write_detection_sees_mutating_calls():
    body = "def test_it():\n    assert place_order([], 'a')['ok']\n"
    assert _audit_ok(body, state_writes=("orders",))


@pytest.mark.parametrize("name,found", [
    ("test_m", True), ("TestK::test_m", True), ("tests/test_x.py::TestK::test_m[1]", True), ("Wrong::test_m", False),
])
def test_class_and_node_id_test_names_are_found(name, found):
    body = "class TestK:\n    def test_m(self):\n        assert place_order([], 'a')['ok']\n"
    assert _audit_ok(body, test_name=name) is found


def _recorder_copy():
    path = Path(flowguard.__file__).with_name("pytest_nodeid_recorder.py")
    spec = importlib.util.spec_from_file_location("recorder_copy_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)   # separate globals: the live session's recorder is untouched
    return module


def test_recorder_keeps_the_worst_phase_outcome():
    rec = _recorder_copy()
    report = lambda when, outcome: SimpleNamespace(nodeid="t.py::a", when=when, passed=outcome == "passed",
                                                   failed=outcome == "failed", skipped=outcome == "skipped")
    rec.pytest_runtest_logreport(report("setup", "passed"))
    rec.pytest_runtest_logreport(report("call", "skipped"))
    rec.pytest_runtest_logreport(report("teardown", "passed"))
    assert rec._STATUSES == {"t.py::a": "skipped"}
    rec.pytest_runtest_logreport(SimpleNamespace(nodeid="t.py::b", when="teardown", passed=False, failed=True, skipped=False))
    assert rec._STATUSES["t.py::b"] == "error"
    rec.pytest_collectreport(SimpleNamespace(nodeid="t2.py", passed=False, skipped=True))
    assert rec._NODEIDS == ["t.py::a", "t.py::b", "t2.py"] and rec._STATUSES["t2.py"] == "skipped"


@pytest.mark.parametrize('source', [
    'def test_it():\n    x = place_order([], "a")\n    self.assertEqual(x, x)\n',
    'def test_it():\n    def place_order(*args):\n        return {"ok": True}\n    assert place_order([], "a")["ok"]\n',
])
def test_equality_assertion_and_nested_shadow_do_not_prove_real_boundary(source):
    assert not _audit_ok(source)


@pytest.mark.parametrize('call', ['obj = Shop()\n    assert obj.place("a") == "placed"',
                                  'assert Shop().place("a") == "placed"'])
def test_src_layout_imported_class_receivers_have_real_owner(call):
    contract = CodeContract('c', path='src/shop/orders.py', symbol='Shop.place')
    evidence = TestEvidence('t', path='tests/test_x.py', test_name='test_it', covered_code_contracts=('c',))
    src = {
        contract.path: 'class Shop:\n    def place(self, order):\n        return "placed"\n',
        evidence.path: 'from shop.orders import Shop\n\ndef test_it():\n    ' + call + '\n',
    }
    report = review_python_contract_source_audit((contract,), (evidence,),
        audit_python_code_contracts((contract,), src), audit_python_test_assertions((evidence,), (contract,), src))
    assert report.ok, report.format_text()




def test_recorder_writes_node_outcomes_and_resets_each_run(tmp_path, monkeypatch):
    rec = _recorder_copy()
    session = SimpleNamespace(config=SimpleNamespace(rootpath=tmp_path, option=SimpleNamespace(xmlpath=None)))
    target = tmp_path / "nodeids.json"
    monkeypatch.setenv("FLOWGUARD_PYTEST_NODEIDS", str(target))
    rec.pytest_sessionstart(session)
    rec.pytest_runtest_logreport(SimpleNamespace(nodeid="t.py::a", when="call", passed=True, failed=False, skipped=False))
    rec.pytest_sessionfinish(session, 0)
    record = json.loads(target.read_text())
    assert record["nodeids"] == ["t.py::a"] and record["statuses"] == {"t.py::a": "passed"}
    assert "input_digest_before" not in record
    rec.pytest_sessionstart(session)
    assert rec._NODEIDS == [] and rec._STATUSES == {}
