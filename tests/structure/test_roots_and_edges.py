"""Roots (pyproject, src layout, sys.path.insert, pytest pythonpath, declared), aliases, missing nodes,
and edge provenance (resolved, guessed, observed)."""


def test_two_root_package_gets_two_names_and_an_alias_edge(repo):
    repo.write({
        "Step8/pyproject.toml": '[tool.setuptools.packages.find]\nwhere = ["src"]\n',
        "Step8/src/core/__init__.py": "",
        "Step8/src/core/rules.py": """
            def grace_ok(days):
                return days <= 3
        """,
        "app/main.py": """
            import os, sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Step8"))
            from src.core.rules import grace_ok
            from core.rules import grace_ok as again

            def run(days):
                return grace_ok(days) and again(days)
        """,
    })
    m = repo.build()
    roots = {r["path"]: r["how"] for r in m.roots()}
    assert roots["Step8/src"].startswith("Step8/pyproject.toml")
    assert roots["Step8"] == "sys.path in app/main.py:2"
    assert m.node("core.rules:grace_ok")["file"] == "Step8/src/core/rules.py"
    alias = m.node("src.core.rules")
    assert alias["kind"] == "alias" and alias["file"] == "Step8/src/core/rules.py"
    assert {(e["dst"], e["kind"]) for e in m.edges("src.core.rules")} == {("core.rules", "alias")}
    imports = {e["dst"] for e in m.edges("app.main", kind="imports")}
    assert imports == {"src.core.rules", "core.rules"}
    calls = {(e["dst"], e["prov"]) for e in m.edges("app.main:run", kind="calls")}
    assert calls == {("core.rules:grace_ok", "resolved")}


def test_syspath_insert_root_and_missing_imports(repo):
    repo.write({
        "tools/run.py": """
            import sys
            from pathlib import Path
            ROOT = Path(__file__).resolve().parents[1]
            sys.path.insert(0, str(ROOT / "lib"))
            import helpers
            from helpers import nope
            import kwp.never_committed
            try:
                import kwp.optional_speedups
            except ImportError:
                pass

            def main():
                return helpers.shout("x")
        """,
        "lib/helpers.py": """
            def shout(text):
                return text.upper()
        """,
        "kwp/__init__.py": "",
    })
    m = repo.build()
    assert {r["path"]: r["how"] for r in m.roots()}["lib"] == "sys.path in tools/run.py:4"
    assert m.node("helpers:shout") is not None
    assert {(e["dst"], e["prov"]) for e in m.edges("tools.run:main", kind="calls")} == {("helpers:shout", "resolved")}
    out = {e["dst"]: e["kind"] for e in m.edges("tools.run")}
    assert out["helpers"] == "imports"
    assert out["missing:helpers:nope"] == "imports"                     # a name helpers does not bind
    assert out["missing:kwp.never_committed"] == "imports"              # KWP's never-committed module
    assert out["missing:kwp.optional_speedups"] == "imports-optional"   # inside try/except ImportError
    assert m.node("missing:kwp.never_committed")["kind"] == "missing"
    assert not any(d.startswith("missing:sys") or d.startswith("missing:pathlib") for d in out)


def test_declared_and_pytest_roots(repo):
    repo.write({
        "pyproject.toml": '[tool.flowguard]\nroots = ["vendor_src"]\n[tool.pytest.ini_options]\npythonpath = ["scripts"]\n',
        "vendor_src/vend.py": "def v():\n    return 1\n",
        "scripts/tool.py": "import vend\n\ndef t():\n    return vend.v()\n",
    })
    m = repo.build()
    roots = {r["path"]: r["how"] for r in m.roots()}
    assert roots["vendor_src"] == "[tool.flowguard] roots"
    assert roots["scripts"] == "pytest pythonpath in pyproject.toml"
    assert {(e["dst"], e["prov"]) for e in m.edges("tool:t", kind="calls")} == {("vend:v", "resolved")}


GUESS = {
    "a.py": """
        from b import f

        def g():
            return f()

        def h(widget):
            return widget.frobnicate()

        def k(page):
            return page.render()
    """,
    "b.py": "def f():\n    return 1\n",
    "c.py": """
        class Widget:
            def frobnicate(self):
                return 2
        class Page:
            def render(self):
                return 3
        class Form:
            def render(self):
                return 4
    """,
}


def test_guessed_edges_do_not_count_as_resolved_callers(repo):
    repo.write(GUESS)
    m = repo.build()
    assert {(e["dst"], e["prov"]) for e in m.edges("a:g", kind="calls")} == {("b:f", "resolved")}
    assert {(e["dst"], e["prov"]) for e in m.edges("a:h", kind="calls")} == {("c:Widget.frobnicate", "guessed")}
    assert m.edges("a:k", kind="calls") == []                  # two functions named render: no guess
    assert m.callers("c:Widget.frobnicate") == []
    assert m.callers("c:Widget.frobnicate", guessed=True) == ["a:h"]
    assert m.callers("b:f") == ["a:g"]
    m.close()
    repo.write({"d.py": "class Gadget:\n    def frobnicate(self):\n        return 5\n"})
    m = repo.build()
    assert m.stats["parsed"] == 1 and m.stats["linked"] == 2   # d.py, and a.py whose guess names frobnicate
    assert [e for e in m.edges("a:h", kind="calls") if e["prov"] == "guessed"] == []
