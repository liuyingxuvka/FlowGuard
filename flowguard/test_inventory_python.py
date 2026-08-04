"""Conservative Python AST discovery for project test inventories."""

from __future__ import annotations

__test__ = False

import ast
from pathlib import Path
from typing import Mapping, Sequence

from .portable_model import canonical_identity
from .source_identity import source_file_fingerprint
from .test_inventory import (
    TEST_DISPOSITION_UNRESOLVED,
    TestAssertion,
    TestDiscoveryResult,
    TestFileDisposition,
    TestFileRecord,
    TestInventoryFinding,
    TestNode,
    TestNodeDisposition,
    TestParameterizationMarker,
    test_assertion_id,
    test_node_id,
)


PYTHON_AST_TEST_ADAPTER_ID = "flowguard.python_ast_test.v1"


def _expr_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _expr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        return _expr_name(node.value)
    if isinstance(node, ast.Call):
        return _expr_name(node.func)
    return ""


def _canonical_expression(node: ast.AST | None, *, fallback: str) -> str:
    if node is None:
        return fallback
    try:
        value = ast.unparse(node).strip()
    except (AttributeError, ValueError):
        value = ""
    return value or _expr_name(node) or fallback


def _structure_fingerprint(node: ast.AST) -> str:
    return canonical_identity(
        {
            "adapter_id": PYTHON_AST_TEST_ADAPTER_ID,
            "ast": ast.dump(node, annotate_fields=True, include_attributes=False),
        }
    )


def _is_test_class(node: ast.ClassDef) -> bool:
    if node.name.startswith("Test"):
        return True
    return any(_expr_name(base).endswith("TestCase") for base in node.bases)


def _literal_string_sequence(node: ast.AST | None) -> tuple[str, ...] | None:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    result: list[str] = []
    for item in node.elts:
        if isinstance(item, ast.Constant) and isinstance(item.value, (str, int)):
            result.append(str(item.value))
        elif isinstance(item, ast.Constant) and item.value is None:
            result.append("None")
        else:
            return None
    return tuple(result)


def _argument_names(node: ast.AST | None) -> tuple[str, ...] | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return tuple(
            item.strip()
            for item in node.value.split(",")
            if item.strip()
        )
    return _literal_string_sequence(node)


def _parameterization_marker(
    decorator: ast.AST,
    *,
    pytest_nodeid: str,
) -> TestParameterizationMarker | None:
    if not isinstance(decorator, ast.Call):
        return None
    name = _expr_name(decorator.func)
    if name != "pytest.mark.parametrize" and not name.endswith(".parametrize"):
        return None

    names = _argument_names(decorator.args[0] if decorator.args else None)
    cases_node = decorator.args[1] if len(decorator.args) >= 2 else None
    case_count = (
        len(cases_node.elts)
        if isinstance(cases_node, (ast.List, ast.Tuple))
        else -1
    )
    ids_node = next(
        (item.value for item in decorator.keywords if item.arg == "ids"),
        None,
    )
    case_ids = ()
    ids_dynamic = False
    if ids_node is not None:
        literal_ids = _literal_string_sequence(ids_node)
        if literal_ids is None:
            ids_dynamic = True
        else:
            case_ids = literal_ids
    dynamic = names is None or case_count < 0 or ids_dynamic
    if dynamic:
        case_count = -1
    argument_names = names or ()
    structure = _structure_fingerprint(decorator)
    marker_payload = {
        "pytest_nodeid": pytest_nodeid,
        "line_start": int(getattr(decorator, "lineno", 1)),
        "structure_fingerprint": structure,
    }
    marker_id = (
        "test-parameterization:"
        + canonical_identity(marker_payload).split(":", 1)[1]
    )
    line_start = int(getattr(decorator, "lineno", 1))
    line_end = int(getattr(decorator, "end_lineno", line_start))
    return TestParameterizationMarker(
        marker_id=marker_id,
        argument_names=argument_names,
        case_count=case_count,
        case_ids=case_ids,
        dynamic=dynamic,
        structure_fingerprint=structure,
        line_start=line_start,
        line_end=line_end,
    )


class _TestBodyVisitor(ast.NodeVisitor):
    """Collect calls and explicit assertions without absorbing nested scopes."""

    def __init__(self, *, pytest_nodeid: str) -> None:
        self.pytest_nodeid = pytest_nodeid
        self.calls: list[str] = []
        self.assertions: list[TestAssertion] = []
        self.case_markers: list[TestParameterizationMarker] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return None

    def _append_assertion(
        self,
        node: ast.AST,
        *,
        assertion_kind: str,
        target: str,
    ) -> None:
        line_start = int(getattr(node, "lineno", 1))
        line_end = int(getattr(node, "end_lineno", line_start))
        column_offset = int(getattr(node, "col_offset", 0))
        self.assertions.append(
            TestAssertion(
                assertion_id=test_assertion_id(
                    self.pytest_nodeid,
                    assertion_kind,
                    target,
                    line_start,
                    column_offset,
                ),
                assertion_kind=assertion_kind,
                target=target,
                structure_fingerprint=_structure_fingerprint(node),
                line_start=line_start,
                line_end=line_end,
                column_offset=column_offset,
            )
        )

    def visit_Assert(self, node: ast.Assert) -> None:
        self._append_assertion(
            node,
            assertion_kind="assert",
            target=_canonical_expression(node.test, fallback="assert-expression"),
        )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _expr_name(node.func)
        if name:
            self.calls.append(name)
            final = name.rsplit(".", 1)[-1]
            if name == "pytest.raises":
                target = _canonical_expression(
                    node.args[0] if node.args else None,
                    fallback="raised-exception",
                )
                self._append_assertion(node, assertion_kind="raises", target=target)
            elif name == "pytest.warns":
                target = _canonical_expression(
                    node.args[0] if node.args else None,
                    fallback="warning",
                )
                self._append_assertion(node, assertion_kind="warns", target=target)
            elif name == "pytest.fail":
                target = _canonical_expression(
                    node.args[0] if node.args else None,
                    fallback="pytest.fail",
                )
                self._append_assertion(node, assertion_kind="fail", target=target)
            elif name in {"self.subTest", "cls.subTest"}:
                argument_names = tuple(
                    str(item.arg) for item in node.keywords if item.arg
                ) or ("subtest",)
                static_values = all(
                    isinstance(item.value, ast.Constant) for item in node.keywords
                ) and all(isinstance(item, ast.Constant) for item in node.args)
                case_id = ",".join(
                    (
                        f"{item.arg}={item.value.value!r}"
                        if item.arg and isinstance(item.value, ast.Constant)
                        else _canonical_expression(item.value, fallback="dynamic")
                    )
                    for item in node.keywords
                ) or ",".join(
                    _canonical_expression(item, fallback="dynamic")
                    for item in node.args
                )
                payload = {
                    "pytest_nodeid": self.pytest_nodeid,
                    "kind": "unittest.subTest",
                    "line": int(getattr(node, "lineno", 1)),
                    "case_id": case_id,
                }
                line_start = int(getattr(node, "lineno", 1))
                if static_values:
                    self.case_markers.append(
                        TestParameterizationMarker(
                            marker_id=(
                                "test-parameterization:"
                                + canonical_identity(payload).split(":", 1)[1]
                            ),
                            argument_names=argument_names,
                            case_count=1,
                            case_ids=(case_id,) if case_id else (),
                            dynamic=False,
                            structure_fingerprint=_structure_fingerprint(node),
                            line_start=line_start,
                            line_end=int(getattr(node, "end_lineno", line_start)),
                        )
                    )
            elif final.startswith("assert") and name.startswith(("self.", "cls.")):
                target = ", ".join(
                    _canonical_expression(item, fallback="argument")
                    for item in node.args
                ) or final
                self._append_assertion(
                    node,
                    assertion_kind="unittest_assertion",
                    target=target,
                )
        self.generic_visit(node)


def _function_body_facts(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    pytest_nodeid: str,
) -> _TestBodyVisitor:
    visitor = _TestBodyVisitor(pytest_nodeid=pytest_nodeid)
    for statement in node.body:
        visitor.visit(statement)
    return visitor


def _test_function_specs(
    tree: ast.Module,
) -> tuple[
    tuple[
        ast.FunctionDef | ast.AsyncFunctionDef,
        str,
        str,
        tuple[ast.expr, ...],
    ],
    ...,
]:
    specs: list[
        tuple[
            ast.FunctionDef | ast.AsyncFunctionDef,
            str,
            str,
            tuple[ast.expr, ...],
        ]
    ] = []
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name.startswith("test_"):
                specs.append((item, "", item.name, ()))
            continue
        if not isinstance(item, ast.ClassDef) or not _is_test_class(item):
            continue
        for method in item.body:
            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith(
                "test_"
            ):
                specs.append(
                    (
                        method,
                        item.name,
                        f"{item.name}.{method.name}",
                        tuple(item.decorator_list),
                    )
                )
    return tuple(specs)


def discover_python_test_file(
    *,
    root: str | Path,
    file_disposition: TestFileDisposition,
    node_dispositions: Mapping[str, TestNodeDisposition] | None = None,
) -> TestDiscoveryResult:
    """Discover standard pytest/unittest source structure without collection."""

    root_path = Path(root).resolve()
    path = (root_path / file_disposition.path).resolve()
    findings: list[TestInventoryFinding] = []
    try:
        path.relative_to(root_path)
    except ValueError:
        return TestDiscoveryResult(
            adapter_id=PYTHON_AST_TEST_ADAPTER_ID,
            path=file_disposition.path,
            findings=(
                TestInventoryFinding(
                    "path_escape",
                    "Python test discovery path escapes the project root",
                    path=file_disposition.path,
                ),
            ),
        )
    try:
        source_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return TestDiscoveryResult(
            adapter_id=PYTHON_AST_TEST_ADAPTER_ID,
            path=file_disposition.path,
            findings=(
                TestInventoryFinding(
                    "python_test_source_read_failure",
                    f"cannot read Python test source: {exc.__class__.__name__}: {exc}",
                    path=file_disposition.path,
                ),
            ),
        )

    current_source_fingerprint = source_file_fingerprint(path)
    if current_source_fingerprint != file_disposition.source_fingerprint:
        findings.append(
            TestInventoryFinding(
                "stale_test_source_fingerprint",
                "Python test adapter input fingerprint differs from current content",
                path=file_disposition.path,
            )
        )
    try:
        tree = ast.parse(source_text, filename=file_disposition.path)
    except SyntaxError as exc:
        findings.append(
            TestInventoryFinding(
                "python_test_parse_failure",
                f"SyntaxError at line {exc.lineno or 0}: {exc.msg}",
                path=file_disposition.path,
            )
        )
        return TestDiscoveryResult(
            adapter_id=PYTHON_AST_TEST_ADAPTER_ID,
            path=file_disposition.path,
            findings=tuple(findings),
        )

    declarations = dict(node_dispositions or {})
    nodes: list[TestNode] = []
    class_names: list[str] = []
    function_names: list[str] = []
    for function, class_name, qualified_name, class_decorators in _test_function_specs(tree):
        if class_name:
            class_names.append(class_name)
        function_names.append(qualified_name)
        pytest_nodeid = (
            f"{file_disposition.path}::{class_name}::{function.name}"
            if class_name
            else f"{file_disposition.path}::{function.name}"
        )
        declaration = declarations.get(pytest_nodeid)
        disposition = (
            declaration.disposition
            if declaration is not None
            else TEST_DISPOSITION_UNRESOLVED
        )
        disposition_reason = declaration.reason if declaration is not None else ""
        markers = tuple(
            marker
            for decorator in (*class_decorators, *function.decorator_list)
            if (
                marker := _parameterization_marker(
                    decorator,
                    pytest_nodeid=pytest_nodeid,
                )
            )
            is not None
        )
        facts = _function_body_facts(function, pytest_nodeid=pytest_nodeid)
        markers = tuple((*markers, *facts.case_markers))
        parameter_names = {
            name
            for marker in markers
            for name in marker.argument_names
        }
        fixture_names = tuple(
            argument.arg
            for argument in (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)
            if argument.arg not in {"self", "cls"} and argument.arg not in parameter_names
        )
        line_start = int(getattr(function, "lineno", 1))
        line_end = int(getattr(function, "end_lineno", line_start))
        node = TestNode(
            node_id=test_node_id(pytest_nodeid),
            pytest_nodeid=pytest_nodeid,
            path=file_disposition.path,
            class_name=class_name,
            function_name=function.name,
            source_fingerprint=current_source_fingerprint,
            structure_fingerprint=_structure_fingerprint(function),
            disposition=disposition,
            disposition_reason=disposition_reason,
            fixture_names=fixture_names,
            parameterization_markers=markers,
            calls=tuple(facts.calls),
            assertions=tuple(
                sorted(
                    facts.assertions,
                    key=lambda item: (item.line_start, item.column_offset, item.assertion_id),
                )
            ),
            line_start=line_start,
            line_end=line_end,
            discovery_adapter_id=PYTHON_AST_TEST_ADAPTER_ID,
        )
        nodes.append(node)
        if declaration is None:
            findings.extend(
                (
                    TestInventoryFinding(
                        "orphan_test_node",
                        "discovered pytest node has no explicit project disposition",
                        path=file_disposition.path,
                        node_id=node.node_id,
                    ),
                    TestInventoryFinding(
                        "unresolved_test_node_disposition",
                        "discovered pytest node has no terminal disposition",
                        path=file_disposition.path,
                        node_id=node.node_id,
                    ),
                )
            )
        for marker in markers:
            if marker.dynamic:
                findings.append(
                    TestInventoryFinding(
                        "dynamic_test_parameterization",
                        "parameterized cases cannot be enumerated from current static source",
                        path=file_disposition.path,
                        node_id=node.node_id,
                    )
                )

    ordered_nodes = tuple(
        sorted(nodes, key=lambda item: (item.line_start, item.pytest_nodeid))
    )
    file_record = TestFileRecord(
        path=file_disposition.path,
        source_fingerprint=current_source_fingerprint,
        structure_fingerprint=_structure_fingerprint(tree),
        test_class_names=tuple(class_names),
        test_function_names=tuple(function_names),
        node_ids=tuple(item.node_id for item in ordered_nodes),
        discovery_adapter_id=PYTHON_AST_TEST_ADAPTER_ID,
    )
    return TestDiscoveryResult(
        adapter_id=PYTHON_AST_TEST_ADAPTER_ID,
        path=file_disposition.path,
        file_record=file_record,
        nodes=ordered_nodes,
        findings=tuple(findings),
    )


__all__ = [
    "PYTHON_AST_TEST_ADAPTER_ID",
    "discover_python_test_file",
]
