"""A test may never become skipped because a handler swallowed an error.

Static half: a test skips only through a `@pytest.mark.skipif(<condition>, reason=...)` marker whose
condition reads sys.platform, sys.version_info or os.name. Every other way to skip or expect failure from
inside a test (pytest.skip, pytest.xfail, pytest.importorskip, pytest.mark.skip, unittest skips, skipTest,
raising SkipTest) is refused, so no helper that swallowed an error can choose a skip.
Runtime half: tests/conftest.py fails any skipped or xfailed outcome that no skipif or xfail marker produced.
The same rule covers every shipped engine and test helper.
"""
import ast
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = {"platform", "version_info", "name"}
CALLS = {"pytest.skip": "skip call", "skip": "skip call", "pytest.xfail": "xfail call", "xfail": "xfail call",
         "pytest.importorskip": "importorskip call", "importorskip": "importorskip call",
         "unittest.skip": "unittest skip decorator", "unittest.skipIf": "unittest skip decorator",
         "unittest.skipUnless": "unittest skip decorator"}


def _static_condition(node, parents):
    names = [item for item in ast.walk(node.args[0]) if isinstance(item, ast.Name)] if node.args else []
    return bool(names) and all(name.id in {"sys", "os"} and isinstance(parents.get(name), ast.Attribute)
                               and parents[name].attr in STATIC for name in names)


def violations(source, relative):
    tree = ast.parse(source)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and ast.unparse(node) == "pytest.mark.skip":
            found.append(f"{relative}:{node.lineno} skip marker")
        if isinstance(node, ast.Raise) and node.exc is not None and (
                "SkipTest" in ast.unparse(node.exc) or "skip.Exception" in ast.unparse(node.exc)):
            found.append(f"{relative}:{node.lineno} SkipTest raised")
        if not isinstance(node, ast.Call):
            continue
        name = ast.unparse(node.func)
        if name in CALLS:
            found.append(f"{relative}:{node.lineno} {CALLS[name]}")
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "skipTest":
            found.append(f"{relative}:{node.lineno} skipTest call")
        elif name.endswith("mark.skipif"):
            if not _static_condition(node, parents):
                found.append(f"{relative}:{node.lineno} skipif on a runtime condition")
            if not any(keyword.arg == "reason" for keyword in node.keywords):
                found.append(f"{relative}:{node.lineno} skipif without a reason")
    return found


def test_no_skip_comes_from_a_swallowed_error():
    found = []
    for base in ("flowguard", "tests"):
        for path in sorted((ROOT / base).rglob("*.py")):
            relative = path.relative_to(ROOT).as_posix()
            if "/fixtures/" in relative:
                continue
            found += violations(path.read_text(encoding="utf-8"), relative)
    assert not found, "\n".join(found)


def test_the_static_rule_sees_each_refused_shape():
    source = textwrap.dedent('''
        import os, sys, pytest
        @pytest.mark.skipif(os.name == "nt", reason="POSIX only")
        def test_static():
            pass
        @pytest.mark.skipif(not ready(), reason="runtime")
        def test_runtime():
            pass
        def judge():
            try:
                check()
            except KeyError:
                pytest.skip("not ready")
            if verdict() is None:
                pytest.skip("not ready")
    ''')
    found = sorted(violations(source, "x.py"), key=lambda line: int(line.split(":")[1].split(" ")[0]))
    assert [line.split(" ", 1)[1].split(":")[0] for line in found] == [
        "skipif on a runtime condition", "skip call", "skip call"], found


def test_a_skip_raised_while_handling_an_error_fails(tmp_path):
    (tmp_path / "conftest.py").write_text(textwrap.dedent(f'''
        import importlib.util
        spec = importlib.util.spec_from_file_location("flowguard_tests_conftest", {str(ROOT / "tests/conftest.py")!r})
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        globals().update({{name: value for name, value in vars(module).items() if name.startswith("pytest_")}})
    '''), encoding="utf-8")
    (tmp_path / "test_judge.py").write_text(textwrap.dedent('''
        import sys
        import pytest
        def test_rule_judged_on_a_broken_path():
            try:
                {}["verdict"]
            except KeyError:
                pytest.skip("rule not ready")
        @pytest.mark.skipif(sys.platform != "no-such-platform", reason="declared, nothing swallowed")
        def test_declared_skip():
            pass
    '''), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfs", str(tmp_path)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "1 failed, 1 skipped" in result.stdout, result.stdout
    assert "skip raised while handling KeyError" in result.stdout, result.stdout


def test_the_static_rule_refuses_every_skip_that_is_not_a_skipif_marker():
    source = textwrap.dedent('''
        import os, sys, unittest, pytest
        numpy = pytest.importorskip("numpy")
        def _ready():
            try:
                return probe()
            except KeyError:
                return False
        def test_plain_call():
            if not _ready():
                pytest.skip("not ready")
        def test_xfail_call():
            pytest.xfail("not ready")
        @pytest.mark.skip(reason="always")
        def test_skip_marker():
            pass
        @pytest.mark.skipif(os.name == "nt")
        def test_skipif_without_reason():
            pass
        class Case(unittest.TestCase):
            def test_unittest(self):
                self.skipTest("not ready")
        def test_raise():
            raise unittest.SkipTest("not ready")
    ''')
    found = sorted(violations(source, "x.py"), key=lambda line: int(line.split(":")[1].split(" ")[0]))
    assert [line.split(" ", 1)[1].split(":")[0] for line in found] == [
        "importorskip call", "skip call", "xfail call", "skip marker", "skipif without a reason", "skipTest call",
        "SkipTest raised"], found


def test_a_skip_or_xfail_that_did_not_come_from_a_marker_fails(tmp_path):
    (tmp_path / "conftest.py").write_text(textwrap.dedent(f'''
        import importlib.util
        spec = importlib.util.spec_from_file_location("flowguard_tests_conftest", {str(ROOT / "tests/conftest.py")!r})
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        globals().update({{name: value for name, value in vars(module).items() if name.startswith("pytest_")}})
    '''), encoding="utf-8")
    (tmp_path / "test_outcomes.py").write_text(textwrap.dedent('''
        import sys
        import pytest
        def _ready():
            try:
                return {}["ready"]
            except KeyError:
                return False
        def test_skip_after_a_swallowing_helper():
            if not _ready():
                pytest.skip("not ready")
        def test_imperative_xfail():
            pytest.xfail("not ready")
        @pytest.fixture
        def needs_service():
            pytest.skip("service missing")
        def test_skip_from_a_fixture(needs_service):
            pass
        @pytest.mark.skipif(sys.platform != "no-such-platform", reason="declared platform skip")
        def test_marker_skip():
            pass
        @pytest.mark.xfail(reason="declared known failure")
        def test_marker_xfail():
            assert False
    '''), encoding="utf-8")
    (tmp_path / "test_optional_import.py").write_text("import pytest\nmodule = pytest.importorskip('no_such_module_xyz')\n",
                                                      encoding="utf-8")
    def run(name):
        return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfEsx", name],
                              cwd=tmp_path, capture_output=True, text=True)
    result = run("test_outcomes.py")
    summary = result.stdout.strip().splitlines()[-1]
    assert result.returncode == 1, result.stdout + result.stderr
    for part in ("2 failed", "1 skipped", "1 xfailed", "1 error"):
        assert part in summary, result.stdout
    assert result.stdout.count("not from a skipif or xfail marker") >= 3, result.stdout
    result = run("test_optional_import.py")
    assert result.returncode == 2 and "1 error" in result.stdout, result.stdout + result.stderr
    assert "skipped while collected, not from a skipif or xfail marker" in result.stdout, result.stdout
