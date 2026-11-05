"""Shared source/test fixture writer for native fallback controls."""

def _program(root, source, tests):
    (root / "app.py").write_text(source)
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests/test_app.py").write_text(tests)

