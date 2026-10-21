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
