"""Code binding helpers: anchors resolve, placeholders fail, and a model's consultation of real code is observed."""

from __future__ import annotations

import sys
from pathlib import Path

from flowguard.map.check import anchor_problems
from flowguard.map.facts import AnchorWatch, CodeFacts


def _project(tmp_path: Path) -> Path:
    (tmp_path / "shop").mkdir()
    (tmp_path / "shop/orders.py").write_text("class Order:\n    mode = 'fast'\n\n\ndef place(order):\n    return order.mode\n",
                                             encoding="utf-8")
    (tmp_path / "web").mkdir()
    (tmp_path / "web/app.js").write_text("document.getElementById('save').onclick = saveOrder;\n", encoding="utf-8")
    return tmp_path


def test_anchor_problems_name_missing_files_symbols_and_placeholders(tmp_path):
    root = _project(tmp_path)
    problems = anchor_problems(root, ["shop/orders.py:place", "shop/orders.py:Order", "shop/orders.py:cancel",
                                      "shop/gone.py:place", "REPLACE_ME/module.py:function", "web/app.js:saveOrder"])
    assert sorted(problems) == ["REPLACE_ME/module.py:function", "shop/gone.py:place", "shop/orders.py:cancel"]
    assert "placeholder anchor" in problems["REPLACE_ME/module.py:function"]
    assert problems["shop/gone.py:place"] == "anchor file missing: shop/gone.py"


def test_code_facts_compare_words_and_anchors_with_the_code(tmp_path):
    root = _project(tmp_path)
    facts = CodeFacts(root)
    assert facts.anchors_exist({"Place": "shop/orders.py:place", "Save": "web/app.js:saveOrder"})
    assert facts.present("mode", ["shop/orders.py"]) and facts.absent("old_mode", ["shop/orders.py"])
    assert facts.report().ok and facts.report().format_text() == "code facts: 4 of 4 hold"
    assert not facts.absent("mode", ["shop/orders.py"], name="removed field mode is gone")
    assert not facts.present("save", ["shop/orders.py"])
    text = facts.report().format_text()
    assert not facts.report().ok and "removed field mode is gone: still referenced at shop/orders.py:2" in text
    assert not CodeFacts(root).report().ok


def test_symbol_references_follow_imports_and_strings_outside_the_own_file(tmp_path):
    files = {"shop/__init__.py": "",
             "shop/orders.py": "def validate(order):\n    return order\n\n\ndef place(order):\n    return validate(order)\n",
             "shop/api.py": "from shop.orders import validate\n\n\ndef create(order):\n    return validate(order)\n",
             "shop/relative.py": "from . import orders\n\n\ndef check(order):\n    return orders.validate(order)\n",
             "shop/other.py": "def validate(value):\n    return value\n",
             "shop/registry.py": "HANDLERS = {'place': 'shop.orders:place'}\n",
             "tests/test_orders.py": "import shop.orders as o\n\n\ndef test_validate():\n    assert o.validate(1)\n"}
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    facts = CodeFacts(tmp_path)
    assert facts.symbol_references("shop/orders.py:validate") == [
        "shop/api.py:1", "shop/api.py:5", "shop/relative.py:5", "tests/test_orders.py:5"]   # not shop/other.py
    assert facts.symbol_references("shop/orders.py:place") == ["shop/registry.py:1"]
    assert facts.symbol_references("shop/orders.py:validate", ["tests/test_orders.py"]) == ["tests/test_orders.py:5"]
    assert not facts.unreferenced("shop/orders.py:validate")
    (tmp_path / "shop/registry.py").unlink()
    assert facts.unreferenced("shop/orders.py:place")
    assert "- shop/orders.py:validate has no reference outside shop/orders.py: still referenced at shop/api.py:1" in \
        facts.report().format_text()


def test_anchor_watch_counts_calls_and_reads_but_not_imports(tmp_path):
    root = _project(tmp_path)
    sys.path.insert(0, str(root))
    try:
        anchors = ["shop/orders.py:place", "web/app.js:saveOrder"]
        with AnchorWatch(root, anchors) as imported_only:
            import shop.orders  # noqa: F401  (opening a file to import it is not a read)
        assert imported_only.consulted() == set()
        assert imported_only.missing() == ["shop/orders.py:place"]
        assert imported_only.unobserved() == ["web/app.js:saveOrder"]
        with AnchorWatch(root, anchors) as called:
            shop.orders.place(shop.orders.Order())
        assert called.consulted() == {"shop/orders.py:place"}
        with AnchorWatch(root, anchors) as read:
            CodeFacts(root).present("saveOrder", ["web/app.js"])
            (root / "shop/orders.py").read_text(encoding="utf-8")
        assert read.consulted() == set(anchors) and read.missing() == [] and read.unobserved() == []
    finally:
        sys.path.remove(str(root))
        sys.modules.pop("shop.orders", None)
        sys.modules.pop("shop", None)


def test_load_anchor_imports_the_named_code_and_rejects_placeholders(tmp_path):
    import pytest

    from flowguard.map.facts import load_anchor

    root = _project(tmp_path)
    sys.path.insert(0, str(root))
    try:
        assert load_anchor("shop/orders.py:Order.mode") == "fast"
        assert load_anchor("shop/orders.py:place", root)(load_anchor("shop/orders.py:Order")()) == "fast"
        with pytest.raises(ValueError, match="placeholder anchor"):
            load_anchor("REPLACE_ME/orders.py:place")
    finally:
        sys.path.remove(str(root))
        sys.modules.pop("shop.orders", None)
        sys.modules.pop("shop", None)


def test_planned_facts_hold_only_under_design_only(tmp_path):
    root = _project(tmp_path)
    facts = CodeFacts(root, planned=True)
    assert facts.anchors_exist(["shop/orders.py:place"])
    assert not facts.check("future module", (root / "future.py").exists(), "does not exist")
    report = facts.report()
    assert report.ok and not report.violations
    assert [fact.name for fact in report.planned] == ["future module"]
    assert report.format_text() == ("code facts: 1 of 1 hold; 1 planned (DESIGN_ONLY: they must hold after the change)\n"
                                    "- planned: future module")
    assert not facts.anchors_exist(["shop/missing.py:place"])
    assert not facts.report().ok and not facts.report().violations[0].planned
    empty = CodeFacts(root, planned=True)
    assert not empty.report().ok
    empty.check("planned only", False)
    assert not empty.report().ok
    for i in range(8):
        empty.check(f"later{i}", False)
    assert empty.report().format_text().count("later") == 4  # at most five planned names, including planned only
