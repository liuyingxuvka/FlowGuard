"""A test may never become skipped because a handler swallowed an error.

Static half: a skip comes only from a `skipif` on sys.platform, sys.version_info or os.name. A runtime skip
call is refused inside an `except` body and under a None/falsy test: None is what swallowing handlers
return, so a "not ready" state must be a distinct value set by the branch that established it.
Runtime half: tests/conftest.py turns a skip raised while another exception is handled into a failure.
flowguard/behave/ is left out until the behavior engine is reworked or removed.
"""
import ast
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = ("flowguard/behave/",)
SKIPS = {"skip", "xfail", "importorskip", "SkipTest"}
STATIC = {"platform", "version_info", "name"}


def _is_skip(node):
    if isinstance(node, ast.Call):
        function = node.func
        return (isinstance(function, ast.Attribute) and function.attr in SKIPS
                or isinstance(function, ast.Name) and function.id in SKIPS)
    return isinstance(node, ast.Raise) and node.exc is not None and "SkipTest" in ast.unparse(node.exc)


def _none_test(test):
    for node in ast.walk(test):
        if isinstance(node, ast.Compare) and any(isinstance(item, ast.Constant) and item.value is None
                                                 for item in node.comparators):
            return True
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not) and isinstance(node.operand, (ast.Name, ast.Attribute)):
            return True
    return False


def _static_condition(node, parents):
    names = [item for item in ast.walk(node.args[0]) if isinstance(item, ast.Name)] if node.args else []
    return bool(names) and all(name.id in {"sys", "os"} and isinstance(parents.get(name), ast.Attribute)
                               and parents[name].attr in STATIC for name in names)


def violations(source, relative):
    tree = ast.parse(source)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "skipif"
                and not _static_condition(node, parents)):
            found.append(f"{relative}:{node.lineno} skipif on a runtime condition")
        if not _is_skip(node) or isinstance(node, ast.Call) and isinstance(parents.get(node), ast.Call):
            continue
        child = node
        while child in parents:
            parent = parents[child]
            if isinstance(parent, ast.ExceptHandler):
                found.append(f"{relative}:{node.lineno} skip inside an except body")
                break
            if isinstance(parent, ast.If) and child in parent.body and _none_test(parent.test):
                found.append(f"{relative}:{node.lineno} skip chosen from a None/falsy value: {ast.unparse(parent.test)[:80]}")
                break
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) and parent.name.startswith("test_"):
                break
            child = parent
    return found


def test_no_skip_comes_from_a_swallowed_error():
    found = []
    for base in ("flowguard", "tests"):
        for path in sorted((ROOT / base).rglob("*.py")):
            relative = path.relative_to(ROOT).as_posix()
            if relative.startswith(EXCLUDED) or "/fixtures/" in relative:
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
        "skipif on a runtime condition", "skip inside an except body", "skip chosen from a None/falsy value"], found


def test_a_skip_raised_while_handling_an_error_fails(tmp_path):
    (tmp_path / "conftest.py").write_text(textwrap.dedent(f'''
        import importlib.util
        spec = importlib.util.spec_from_file_location("flowguard_tests_conftest", {str(ROOT / "tests/conftest.py")!r})
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        globals().update({{name: value for name, value in vars(module).items() if name.startswith("pytest_")}})
    '''), encoding="utf-8")
    (tmp_path / "test_judge.py").write_text(textwrap.dedent('''
        import pytest
        def test_rule_judged_on_a_broken_path():
            try:
                {}["verdict"]
            except KeyError:
                pytest.skip("rule not ready")
        def test_declared_skip():
            pytest.skip("declared, nothing swallowed")
    '''), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfs", str(tmp_path)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "1 failed, 1 skipped" in result.stdout, result.stdout
    assert "skip raised while handling KeyError" in result.stdout, result.stdout
