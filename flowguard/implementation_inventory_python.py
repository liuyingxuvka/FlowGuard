"""Conservative Python AST discovery for implementation inventories."""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Sequence

from .implementation_inventory import (
    DynamicSelectorContract,
    IMPLEMENTATION_DISPOSITION_UNRESOLVED,
    ImplementationDiscoveryResult,
    ImplementationFileDisposition,
    ImplementationInventoryFinding,
    ImplementationSurface,
    implementation_surface_id,
    implementation_surface_key,
)
from .portable_model import canonical_identity


PYTHON_AST_IMPLEMENTATION_ADAPTER_ID = "flowguard.python_ast_implementation.v1"

SIDE_EFFECT_CALL_PREFIXES = (
    "write",
    "save",
    "publish",
    "send",
    "emit",
    "delete",
    "remove",
    "create",
    "update",
    "insert",
    "post",
    "put",
    "patch",
    "commit",
    "execute",
)

DYNAMIC_CALLS = frozenset(
    {
        "eval",
        "exec",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "__import__",
        "importlib.import_module",
        "runpy.run_module",
        "runpy.run_path",
    }
)

ENTRYPOINT_DECORATOR_SUFFIXES = (
    ".route",
    ".command",
    ".callback",
    ".handler",
    ".endpoint",
    ".listener",
)


def _expr_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _expr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        base = _expr_name(node.value)
        key = ""
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, (str, int)):
            key = repr(node.slice.value)
        return f"{base}[{key}]" if base and key else base
    if isinstance(node, ast.Call):
        return _expr_name(node.func)
    return ""


def _literal_error_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Call):
        return _expr_name(node.func)
    return _expr_name(node)


def _is_main_guard(node: ast.If) -> bool:
    compare = node.test
    if not isinstance(compare, ast.Compare) or len(compare.ops) != 1 or len(compare.comparators) != 1:
        return False
    if not isinstance(compare.ops[0], ast.Eq):
        return False
    left = compare.left
    right = compare.comparators[0]
    pairs = ((left, right), (right, left))
    return any(
        isinstance(name, ast.Name)
        and name.id == "__name__"
        and isinstance(value, ast.Constant)
        and value.value == "__main__"
        for name, value in pairs
    )


class _ScopeFactVisitor(ast.NodeVisitor):
    """Collect facts for one lexical scope without absorbing nested scopes."""

    def __init__(self, *, include_plain_name_writes: bool) -> None:
        self.include_plain_name_writes = include_plain_name_writes
        self.nonlocal_names: set[str] = set()
        self.calls: list[str] = []
        self.reads: list[str] = []
        self.writes: list[str] = []
        self.effects: list[str] = []
        self.dynamic: list[str] = []
        self.dynamic_selector_nodes: dict[str, list[ast.AST]] = {}
        self.raised: list[str] = []
        self.returns_value = False

    def _state_target_names(self, node: ast.AST) -> tuple[str, ...]:
        if isinstance(node, ast.Name):
            if self.include_plain_name_writes or node.id in self.nonlocal_names:
                return (node.id,)
            return ()
        if isinstance(node, (ast.Attribute, ast.Subscript)):
            name = _expr_name(node)
            return (name,) if name else ()
        if isinstance(node, (ast.Tuple, ast.List)):
            values: list[str] = []
            for item in node.elts:
                values.extend(self._state_target_names(item))
            return tuple(values)
        return ()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return None

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # Lambda bodies are fully represented in the AST and are not dynamic
        # dispatch merely because they use expression syntax.
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if any(alias.name == "*" for alias in node.names):
            self.dynamic.append("import_star")

    def visit_Global(self, node: ast.Global) -> None:
        self.nonlocal_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocal_names.update(node.names)

    def visit_Call(self, node: ast.Call) -> None:
        name = _expr_name(node.func)
        if name:
            self.calls.append(name)
            final = name.rsplit(".", 1)[-1]
            if any(final.startswith(prefix) for prefix in SIDE_EFFECT_CALL_PREFIXES):
                self.effects.append(name)
            indirect_dynamic = ""
            if isinstance(node.func, ast.Call):
                indirect_dynamic = _expr_name(node.func.func)
            if indirect_dynamic in DYNAMIC_CALLS:
                self.dynamic.append(f"invoke_result:{indirect_dynamic}")
                if (
                    indirect_dynamic in {"getattr", "setattr", "delattr"}
                    and isinstance(node.func, ast.Call)
                    and len(node.func.args) >= 2
                ):
                    self.dynamic_selector_nodes.setdefault(
                        f"invoke_result:{indirect_dynamic}", []
                    ).append(node.func.args[1])
            elif name in DYNAMIC_CALLS or final in DYNAMIC_CALLS:
                if final in {"getattr", "setattr", "delattr"} and len(node.args) >= 2:
                    attribute = node.args[1]
                    if isinstance(attribute, ast.Constant) and isinstance(
                        attribute.value, str
                    ):
                        self.dynamic.append(f"{final}:{attribute.value}")
                    else:
                        self.dynamic.append(name)
                        self.dynamic_selector_nodes.setdefault(final, []).append(
                            attribute
                        )
                else:
                    self.dynamic.append(name)
                    if final in {"globals", "locals"}:
                        self.dynamic_selector_nodes.setdefault(final, []).append(node)
        self.generic_visit(node)

    @property
    def dynamic_selector_source_fingerprints(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (
                operation,
                canonical_identity(
                    {
                        "operation": operation,
                        "selector_asts": sorted(
                            {
                                ast.dump(
                                    node,
                                    annotate_fields=True,
                                    include_attributes=False,
                                )
                                for node in nodes
                            }
                        ),
                    }
                ),
            )
            for operation, nodes in sorted(self.dynamic_selector_nodes.items())
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self.writes.extend(self._state_target_names(target))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.writes.extend(self._state_target_names(node.target))
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.writes.extend(self._state_target_names(node.target))
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.writes.extend(self._state_target_names(node.target))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and (
            self.include_plain_name_writes or node.id in self.nonlocal_names
        ):
            self.reads.append(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load):
            name = _expr_name(node)
            if name:
                self.reads.append(name)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.ctx, ast.Load):
            name = _expr_name(node)
            if name:
                self.reads.append(name)
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        name = _literal_error_name(node.exc)
        if name:
            self.raised.append(name)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is not None:
            self.returns_value = True
        self.generic_visit(node)


def _scope_facts(
    body: Sequence[ast.stmt],
    *,
    include_plain_name_writes: bool = False,
) -> _ScopeFactVisitor:
    visitor = _ScopeFactVisitor(include_plain_name_writes=include_plain_name_writes)
    for statement in body:
        visitor.visit(statement)
    return visitor


class _FiniteSelectorCollector(ast.NodeVisitor):
    """Collect only nodes owned by one lexical surface."""

    def __init__(self, root: ast.AST) -> None:
        self.root = root
        self.calls: list[ast.Call] = []
        self.assignments: dict[str, list[tuple[int, ast.AST]]] = {}

    def _visit_scope(self, node: ast.AST) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.assignments.setdefault(target.id, []).append(
                    (int(getattr(node, "lineno", 0)), node.value)
                )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name) and node.value is not None:
            self.assignments.setdefault(node.target.id, []).append(
                (int(getattr(node, "lineno", 0)), node.value)
            )
        self.generic_visit(node)


def _finite_selector_values(
    root: ast.AST,
    *,
    module: ast.Module | None = None,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Derive finite selector domains from syntax owned by one surface.

    Only literal collections, literal dict keys, finite loop bindings, and an
    exact locals/globals membership expression are admitted.  Function
    parameters and other open strings deliberately produce no domain.
    """

    collector = _FiniteSelectorCollector(root)
    collector.visit(root)
    module_assignments: dict[str, list[tuple[int, ast.AST]]] = {}
    if module is not None:
        for statement in module.body:
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        module_assignments.setdefault(target.id, []).append(
                            (int(getattr(statement, "lineno", 0)), statement.value)
                        )
            elif (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.value is not None
            ):
                module_assignments.setdefault(statement.target.id, []).append(
                    (int(getattr(statement, "lineno", 0)), statement.value)
                )
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(root):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def assignment(name: str, before_line: int) -> ast.AST | None:
        candidates = [
            (line, value)
            for line, value in collector.assignments.get(name, ())
            if line < before_line
        ]
        if candidates:
            return max(candidates, key=lambda row: row[0])[1]
        globals_for_name = module_assignments.get(name, ())
        return max(globals_for_name, default=(0, None), key=lambda row: row[0])[1]

    def raw_items(
        expression: ast.AST,
        *,
        before_line: int,
        seen: frozenset[str] = frozenset(),
    ) -> tuple[ast.AST, ...] | None:
        if isinstance(expression, (ast.Tuple, ast.List, ast.Set)):
            return tuple(expression.elts)
        if isinstance(expression, ast.Dict):
            if any(key is None for key in expression.keys):
                return None
            return tuple(key for key in expression.keys if key is not None)
        if isinstance(expression, ast.Name) and expression.id not in seen:
            value = assignment(expression.id, before_line)
            if value is None:
                return None
            return raw_items(
                value,
                before_line=before_line,
                seen=seen | {expression.id},
            )
        if isinstance(expression, ast.Call) and len(expression.args) == 1:
            name = _expr_name(expression.func).rsplit(".", 1)[-1]
            if name in {"sorted", "tuple", "list", "set", "frozenset"}:
                return raw_items(expression.args[0], before_line=before_line, seen=seen)
        if (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Attribute)
            and expression.func.attr in {"items", "keys"}
            and not expression.args
        ):
            value = expression.func.value
            if isinstance(value, ast.Name):
                value = assignment(value.id, before_line) or value
            if not isinstance(value, ast.Dict) or any(
                key is None for key in value.keys
            ):
                return None
            if expression.func.attr == "keys":
                return tuple(key for key in value.keys if key is not None)
            return tuple(
                ast.Tuple(elts=[key, item], ctx=ast.Load())
                for key, item in zip(value.keys, value.values)
                if key is not None
            )
        return None

    def literal_strings(
        expression: ast.AST,
        *,
        before_line: int,
    ) -> tuple[str, ...] | None:
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
            return (expression.value,)
        items = raw_items(expression, before_line=before_line)
        if items is None:
            return None
        values: list[str] = []
        for item in items:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                return None
            values.append(item.value)
        return tuple(sorted(set(values))) if values else None

    def target_index(target: ast.AST, name: str) -> int | None:
        if isinstance(target, ast.Name):
            return 0 if target.id == name else None
        if isinstance(target, (ast.Tuple, ast.List)):
            for index, item in enumerate(target.elts):
                if isinstance(item, ast.Name) and item.id == name:
                    return index
        return None

    def loop_binding_values(
        loop: ast.For | ast.AsyncFor | ast.comprehension,
        name: str,
        *,
        before_line: int,
    ) -> tuple[str, ...] | None:
        index = target_index(loop.target, name)
        if index is None:
            return None
        items = raw_items(loop.iter, before_line=before_line)
        if items is None:
            return None
        values: list[str] = []
        tuple_target = isinstance(loop.target, (ast.Tuple, ast.List))
        for item in items:
            selected = item
            if tuple_target:
                if not isinstance(item, (ast.Tuple, ast.List)) or index >= len(item.elts):
                    return None
                selected = item.elts[index]
            if not isinstance(selected, ast.Constant) or not isinstance(
                selected.value, str
            ):
                return None
            values.append(selected.value)
        return tuple(sorted(set(values))) if values else None

    def name_domain(call: ast.Call, name: str) -> tuple[str, ...] | None:
        before_line = int(getattr(call, "lineno", 0))
        current: ast.AST = call
        while current in parents:
            current = parents[current]
            if isinstance(current, (ast.For, ast.AsyncFor)):
                values = loop_binding_values(
                    current,
                    name,
                    before_line=before_line,
                )
                if values is not None:
                    return values
            if isinstance(
                current,
                (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp),
            ):
                for generator in current.generators:
                    values = loop_binding_values(
                        generator,
                        name,
                        before_line=before_line,
                    )
                    if values is not None:
                        return values
            if current is root:
                break
        value = assignment(name, before_line)
        if value is not None:
            values = literal_strings(value, before_line=before_line)
            if values is not None:
                return values

        def terminal_guard(statements: Sequence[ast.stmt]) -> bool:
            return bool(statements) and all(
                isinstance(statement, (ast.Raise, ast.Return))
                for statement in statements
            )

        for candidate in ast.walk(root):
            if not isinstance(candidate, ast.If):
                continue
            if int(getattr(candidate, "end_lineno", 0)) >= before_line:
                continue
            if candidate.orelse or not terminal_guard(candidate.body):
                continue
            test = candidate.test
            if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(
                test.comparators
            ) != 1:
                continue
            left = test.left
            right = test.comparators[0]
            if not isinstance(left, ast.Name) or left.id != name:
                continue
            if isinstance(test.ops[0], ast.NotEq):
                if isinstance(right, ast.Constant) and isinstance(right.value, str):
                    return (right.value,)
            if isinstance(test.ops[0], ast.NotIn):
                guarded = literal_strings(right, before_line=before_line)
                if guarded is not None:
                    return guarded
        return None

    def membership_values(call: ast.Call) -> tuple[str, ...] | None:
        current: ast.AST = call
        while current in parents:
            current = parents[current]
            if isinstance(current, ast.Compare):
                expressions = (current.left, *current.comparators)
                values = tuple(
                    expression.value
                    for expression in expressions
                    if isinstance(expression, ast.Constant)
                    and isinstance(expression.value, str)
                )
                if values:
                    return tuple(sorted(set(values)))
            if current is root:
                break
        return None

    values_by_operation: dict[str, set[str]] = {}
    incomplete_operations: set[str] = set()
    for call in collector.calls:
        name = _expr_name(call.func)
        final = name.rsplit(".", 1)[-1]
        operation = ""
        selector: ast.AST | None = None
        if isinstance(call.func, ast.Call):
            indirect = _expr_name(call.func.func).rsplit(".", 1)[-1]
            if indirect in {"getattr", "setattr", "delattr"} and len(call.func.args) >= 2:
                operation = f"invoke_result:{indirect}"
                selector = call.func.args[1]
        elif final in {"getattr", "setattr", "delattr"} and len(call.args) >= 2:
            if not (
                isinstance(call.args[1], ast.Constant)
                and isinstance(call.args[1].value, str)
            ):
                operation = final
                selector = call.args[1]
        elif final in {"locals", "globals"}:
            operation = final

        if not operation:
            continue
        if selector is None:
            values = membership_values(call)
        elif isinstance(selector, ast.Constant) and isinstance(selector.value, str):
            values = (selector.value,)
        elif isinstance(selector, ast.Name):
            values = name_domain(call, selector.id)
        else:
            values = literal_strings(
                selector,
                before_line=int(getattr(call, "lineno", 0)),
            )
        if values is None:
            incomplete_operations.add(operation)
            continue
        values_by_operation.setdefault(operation, set()).update(values)

    return tuple(
        (operation, tuple(sorted(values)))
        for operation, values in sorted(values_by_operation.items())
        if operation not in incomplete_operations and values
    )


def _function_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    values = [
        argument.arg
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        )
        if argument.arg not in {"self", "cls"}
    ]
    if node.args.vararg is not None:
        values.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg is not None:
        values.append(f"**{node.args.kwarg.arg}")
    return tuple(values)


def _decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                name
                for decorator in node.decorator_list
                if (name := _expr_name(decorator))
            }
        )
    )


def _is_decorated_entrypoint(decorators: Sequence[str]) -> bool:
    for decorator in decorators:
        lowered = decorator.casefold()
        if lowered in {"command", "route", "handler", "endpoint", "listener"}:
            return True
        if any(lowered.endswith(suffix) for suffix in ENTRYPOINT_DECORATOR_SUFFIXES):
            return True
    return False


@dataclass(frozen=True)
class _NodeSpec:
    node: ast.AST
    symbol: str
    surface_kind: str
    parent_symbol: str
    roles: tuple[str, ...]
    parameters: tuple[str, ...]
    facts: _ScopeFactVisitor


def _collect_node_specs(tree: ast.Module) -> tuple[_NodeSpec, ...]:
    entrypoint_calls: set[str] = set()
    has_main_guard = False
    for statement in tree.body:
        if isinstance(statement, ast.If) and _is_main_guard(statement):
            has_main_guard = True
            facts = _scope_facts(statement.body, include_plain_name_writes=True)
            entrypoint_calls.update(call.rsplit(".", 1)[-1] for call in facts.calls)

    module_roles = ("entrypoint",) if has_main_guard else ()
    specs: list[_NodeSpec] = [
        _NodeSpec(
            node=tree,
            symbol="<module>",
            surface_kind="module",
            parent_symbol="",
            roles=module_roles,
            parameters=(),
            facts=_scope_facts(tree.body, include_plain_name_writes=True),
        )
    ]

    class_symbols: set[str] = set()

    def visit_body(
        body: Sequence[ast.stmt],
        symbol_prefix: str,
        parent_surface_symbol: str,
        class_depth: int,
    ) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                symbol = f"{symbol_prefix}.{node.name}" if symbol_prefix else node.name
                class_symbols.add(symbol)
                roles = ["helper"] if node.name.startswith("_") else []
                decorators = _decorator_names(node)
                if decorators:
                    roles.extend(f"decorator:{name}" for name in decorators)
                specs.append(
                    _NodeSpec(
                        node=node,
                        symbol=symbol,
                        surface_kind="class",
                        parent_symbol=parent_surface_symbol or "<module>",
                        roles=tuple(roles),
                        parameters=(),
                        facts=_scope_facts(node.body, include_plain_name_writes=True),
                    )
                )
                visit_body(node.body, symbol, symbol, class_depth + 1)
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = f"{symbol_prefix}.{node.name}" if symbol_prefix else node.name
                roles: list[str] = []
                if node.name.startswith("_"):
                    roles.append("helper")
                decorators = _decorator_names(node)
                if node.name in entrypoint_calls or (not symbol_prefix and node.name == "main"):
                    roles.append("entrypoint")
                if _is_decorated_entrypoint(decorators):
                    roles.append("entrypoint")
                if isinstance(node, ast.AsyncFunctionDef):
                    roles.append("async")
                roles.extend(f"decorator:{name}" for name in decorators)
                facts = _scope_facts(node.body)
                if facts.writes:
                    roles.append("state_writer")
                if facts.effects:
                    roles.append("effect_writer")
                specs.append(
                    _NodeSpec(
                        node=node,
                        symbol=symbol,
                        surface_kind="method" if parent_surface_symbol in class_symbols else "function",
                        parent_symbol=parent_surface_symbol or "<module>",
                        roles=tuple(roles),
                        parameters=_function_parameters(node),
                        facts=facts,
                    )
                )
                nested_prefix = f"{symbol}.<locals>"
                visit_body(node.body, nested_prefix, symbol, class_depth)
                continue
            nested_bodies: list[Sequence[ast.stmt]] = []
            for field_name in ("body", "orelse", "finalbody"):
                value = getattr(node, field_name, None)
                if isinstance(value, list):
                    nested_bodies.append(value)
            handlers = getattr(node, "handlers", None)
            if isinstance(handlers, list):
                nested_bodies.extend(handler.body for handler in handlers)
            for nested in nested_bodies:
                visit_body(nested, symbol_prefix, parent_surface_symbol, class_depth)

    visit_body(tree.body, "", "<module>", 0)
    return tuple(specs)


def discover_python_implementation_surfaces(
    *,
    root: str | Path,
    file_disposition: ImplementationFileDisposition,
    surface_dispositions: Mapping[str, str] | None = None,
    supporting_owners: Mapping[str, str] | None = None,
    dynamic_allowances: Mapping[str, Sequence[str]] | None = None,
    dynamic_selector_contracts: Sequence[DynamicSelectorContract] = (),
) -> ImplementationDiscoveryResult:
    """Discover Python surfaces without interpreting them as model bindings."""

    root_path = Path(root).resolve()
    path = (root_path / file_disposition.path).resolve()
    findings: list[ImplementationInventoryFinding] = []
    try:
        path.relative_to(root_path)
    except ValueError:
        return ImplementationDiscoveryResult(
            adapter_id=PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
            path=file_disposition.path,
            findings=(
                ImplementationInventoryFinding(
                    "path_escape",
                    "Python discovery path escapes the repository root",
                    path=file_disposition.path,
                ),
            ),
        )
    try:
        source_bytes = path.read_bytes()
        source_text = source_bytes.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        return ImplementationDiscoveryResult(
            adapter_id=PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
            path=file_disposition.path,
            findings=(
                ImplementationInventoryFinding(
                    "python_source_read_failure",
                    f"cannot read Python source: {exc.__class__.__name__}: {exc}",
                    path=file_disposition.path,
                ),
            ),
        )
    source_text = source_text.replace("\r\n", "\n").replace("\r", "\n")
    current_fingerprint = (
        "sha256:" + hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    )
    if current_fingerprint != file_disposition.content_fingerprint:
        findings.append(
            ImplementationInventoryFinding(
                "stale_file_fingerprint",
                "Python adapter input fingerprint differs from current content",
                path=file_disposition.path,
            )
        )
    try:
        tree = ast.parse(source_text, filename=file_disposition.path)
    except SyntaxError as exc:
        findings.append(
            ImplementationInventoryFinding(
                "python_parse_failure",
                f"SyntaxError at line {exc.lineno or 0}: {exc.msg}",
                path=file_disposition.path,
            )
        )
        return ImplementationDiscoveryResult(
            adapter_id=PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
            path=file_disposition.path,
            findings=tuple(findings),
        )

    disposition_map = dict(surface_dispositions or {})
    owner_map = dict(supporting_owners or {})
    allowance_map = {
        str(key): frozenset(str(item) for item in values)
        for key, values in dict(dynamic_allowances or {}).items()
    }
    contract_map: dict[tuple[str, str], DynamicSelectorContract] = {}
    duplicate_contract_keys: set[tuple[str, str]] = set()
    for contract in dynamic_selector_contracts:
        contract_key = (contract.surface_key, contract.operation)
        if contract_key in contract_map:
            duplicate_contract_keys.add(contract_key)
        else:
            contract_map[contract_key] = contract
    specs = _collect_node_specs(tree)
    id_by_symbol = {
        spec.symbol: implementation_surface_id(
            file_disposition.path,
            spec.symbol,
            spec.surface_kind,
        )
        for spec in specs
    }
    id_by_key = {
        implementation_surface_key(file_disposition.path, symbol): surface_id
        for symbol, surface_id in id_by_symbol.items()
    }
    known_ids = set(id_by_symbol.values())

    def resolve_surface_ref(value: str) -> str:
        return id_by_key.get(
            value,
            id_by_symbol.get(
                value,
                value
                if value in known_ids or value.startswith("implementation-surface:")
                else "",
            ),
        )

    surfaces: list[ImplementationSurface] = []
    discovered_surface_keys: set[str] = set()
    for spec in specs:
        surface_id = id_by_symbol[spec.symbol]
        key = implementation_surface_key(file_disposition.path, spec.symbol)
        discovered_surface_keys.add(key)
        disposition = disposition_map.get(surface_id, disposition_map.get(key, IMPLEMENTATION_DISPOSITION_UNRESOLVED))
        owner_ref = owner_map.get(surface_id, owner_map.get(key, ""))
        owner_id = resolve_surface_ref(owner_ref) if owner_ref else ""
        if owner_ref and not owner_id:
            findings.append(
                ImplementationInventoryFinding(
                    "unknown_supporting_owner",
                    f"supporting owner reference is not a discovered surface: {owner_ref}",
                    path=file_disposition.path,
                    surface_id=surface_id,
                )
            )
        structure_fingerprint = canonical_identity(
            {
                "adapter_id": PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
                "ast": ast.dump(spec.node, annotate_fields=True, include_attributes=False),
            }
        )
        roles = set(spec.roles)
        allowed_dynamic = allowance_map.get(
            surface_id,
            allowance_map.get(key, frozenset()),
        )
        contract_operations: set[str] = set()
        selector_source_fingerprints = dict(
            spec.facts.dynamic_selector_source_fingerprints
        )
        finite_selector_values = dict(
            _finite_selector_values(spec.node, module=tree)
        )
        for operation in sorted(set(spec.facts.dynamic)):
            contract_key = (key, operation)
            contract = contract_map.get(contract_key)
            if contract is None:
                continue
            if contract_key in duplicate_contract_keys:
                findings.append(
                    ImplementationInventoryFinding(
                        "duplicate_dynamic_selector_contract",
                        "dynamic selector surface and operation have more than one contract",
                        path=file_disposition.path,
                        surface_id=surface_id,
                    )
                )
                continue
            effective_owner_id = owner_id or surface_id
            if contract.owner_surface_id != effective_owner_id:
                findings.append(
                    ImplementationInventoryFinding(
                        "dynamic_selector_contract_owner_mismatch",
                        "dynamic selector contract does not bind the current surface owner",
                        path=file_disposition.path,
                        surface_id=surface_id,
                    )
                )
                continue
            if contract.surface_structure_fingerprint != structure_fingerprint:
                findings.append(
                    ImplementationInventoryFinding(
                        "dynamic_selector_contract_stale",
                        "dynamic selector contract does not bind the current surface structure",
                        path=file_disposition.path,
                        surface_id=surface_id,
                    )
                )
                continue
            if (
                selector_source_fingerprints.get(operation)
                != contract.selector_source_fingerprint
            ):
                findings.append(
                    ImplementationInventoryFinding(
                        "dynamic_selector_contract_source_mismatch",
                        "dynamic selector contract does not bind the observed selector source",
                        path=file_disposition.path,
                        surface_id=surface_id,
                    )
                )
                continue
            observed_values = finite_selector_values.get(operation)
            if observed_values is None:
                findings.append(
                    ImplementationInventoryFinding(
                        "dynamic_selector_contract_unbounded",
                        "dynamic selector source is open and has no exact static finite domain",
                        path=file_disposition.path,
                        surface_id=surface_id,
                    )
                )
                continue
            if observed_values != contract.selector_values:
                findings.append(
                    ImplementationInventoryFinding(
                        "dynamic_selector_contract_values_mismatch",
                        "dynamic selector contract values differ from the exact static domain",
                        path=file_disposition.path,
                        surface_id=surface_id,
                    )
                )
                continue
            contract_operations.add(operation)
        unresolved_dynamic = (
            set(spec.facts.dynamic)
            - set(allowed_dynamic)
            - contract_operations
        )
        if spec.facts.writes:
            roles.add("state_writer")
        if spec.facts.effects:
            roles.add("effect_writer")
        if unresolved_dynamic:
            roles.add("dynamic")
        elif spec.facts.dynamic:
            roles.add("dynamic_bounded")
        parent_id = id_by_symbol.get(spec.parent_symbol, "")
        line_start = int(getattr(spec.node, "lineno", 1))
        line_end = int(getattr(spec.node, "end_lineno", line_start))
        surface = ImplementationSurface(
            surface_id=surface_id,
            path=file_disposition.path,
            symbol=spec.symbol,
            surface_kind=spec.surface_kind,
            parent_surface_id=parent_id,
            content_fingerprint=current_fingerprint,
            structure_fingerprint=structure_fingerprint,
            disposition=disposition,
            owning_surface_id=owner_id,
            roles=tuple(roles),
            parameters=spec.parameters,
            calls=tuple(spec.facts.calls),
            state_reads=tuple(spec.facts.reads),
            state_writes=tuple(spec.facts.writes),
            side_effect_candidates=tuple(spec.facts.effects),
            dynamic_operations=tuple(spec.facts.dynamic),
            dynamic_selector_source_fingerprints=(
                spec.facts.dynamic_selector_source_fingerprints
            ),
            dynamic_selector_values=_finite_selector_values(spec.node, module=tree),
            raised_errors=tuple(spec.facts.raised),
            returns_value=spec.facts.returns_value,
            line_start=line_start,
            line_end=line_end,
            discovery_adapter_id=PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
        )
        surfaces.append(surface)
        if disposition == IMPLEMENTATION_DISPOSITION_UNRESOLVED:
            findings.append(
                ImplementationInventoryFinding(
                    "unresolved_surface_disposition",
                    "discovered Python surface has no explicit terminal disposition",
                    path=file_disposition.path,
                    surface_id=surface_id,
                )
            )
        if unresolved_dynamic:
            findings.append(
                ImplementationInventoryFinding(
                    "dynamic_python_surface",
                    "dynamic Python operation requires an explicit bounded interpretation: "
                    + ", ".join(sorted(unresolved_dynamic)),
                    path=file_disposition.path,
                    surface_id=surface_id,
                )
            )

    for (surface_key, operation), contract in sorted(contract_map.items()):
        if surface_key not in discovered_surface_keys:
            findings.append(
                ImplementationInventoryFinding(
                    "unknown_dynamic_selector_contract_surface",
                    f"dynamic selector contract references an undiscovered surface: {operation}",
                    path=file_disposition.path,
                )
            )
            continue
        matching_surface = next(
            surface
            for surface in surfaces
            if implementation_surface_key(surface.path, surface.symbol) == surface_key
        )
        if operation not in matching_surface.dynamic_operations:
            findings.append(
                ImplementationInventoryFinding(
                    "unknown_dynamic_selector_contract_operation",
                    "dynamic selector contract operation is not observed on its bound surface",
                    path=file_disposition.path,
                    surface_id=matching_surface.surface_id,
                )
            )

    return ImplementationDiscoveryResult(
        adapter_id=PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
        path=file_disposition.path,
        surfaces=tuple(sorted(surfaces, key=lambda item: (item.line_start, item.symbol))),
        findings=tuple(findings),
    )


def derive_static_dynamic_selector_contracts(
    observation: ImplementationDiscoveryResult,
    *,
    supporting_owners: Mapping[str, str] | None = None,
) -> tuple[DynamicSelectorContract, ...]:
    """Materialize exact contracts for selector domains proved by observation.

    This is a projection of immutable AST facts, not a second source scan.  An
    operation with no non-empty finite domain remains open and receives no
    contract.  Supporting surfaces bind the generated contract to their exact
    effective owner in the same way as the declaration projection.
    """

    owner_map = dict(supporting_owners or {})
    id_by_key = {
        implementation_surface_key(surface.path, surface.symbol): surface.surface_id
        for surface in observation.surfaces
    }
    known_ids = {surface.surface_id for surface in observation.surfaces}
    contracts: list[DynamicSelectorContract] = []
    for surface in observation.surfaces:
        surface_key = implementation_surface_key(surface.path, surface.symbol)
        owner_ref = owner_map.get(
            surface.surface_id,
            owner_map.get(surface_key, ""),
        )
        owner_surface_id = id_by_key.get(
            owner_ref,
            owner_ref
            if owner_ref in known_ids
            or owner_ref.startswith("implementation-surface:")
            else "",
        )
        if owner_ref and not owner_surface_id:
            # The ordinary declaration projection owns the visible unknown-owner
            # finding.  Do not manufacture a contract with a different owner.
            continue
        effective_owner_id = owner_surface_id or surface.surface_id
        selector_sources = dict(surface.dynamic_selector_source_fingerprints)
        selector_values = dict(surface.dynamic_selector_values)
        for operation in sorted(set(surface.dynamic_operations)):
            values = selector_values.get(operation)
            selector_source_fingerprint = selector_sources.get(operation, "")
            if not values or not selector_source_fingerprint:
                continue
            contracts.append(
                DynamicSelectorContract(
                    surface_key=surface_key,
                    owner_surface_id=effective_owner_id,
                    surface_structure_fingerprint=surface.structure_fingerprint,
                    selector_source_fingerprint=selector_source_fingerprint,
                    operation=operation,
                    selector_values=values,
                    rationale=(
                        "The current Python observation proves this exact finite "
                        "selector domain for the bound surface and owner."
                    ),
                )
            )
    return tuple(
        sorted(
            contracts,
            key=lambda contract: (contract.surface_key, contract.operation),
        )
    )


def project_python_implementation_observation(
    observation: ImplementationDiscoveryResult,
    *,
    surface_dispositions: Mapping[str, str] | None = None,
    supporting_owners: Mapping[str, str] | None = None,
    dynamic_allowances: Mapping[str, Sequence[str]] | None = None,
    dynamic_selector_contracts: Sequence[DynamicSelectorContract] = (),
) -> ImplementationDiscoveryResult:
    """Apply declarations to one immutable AST observation without reparsing.

    Discovery owns source reading and AST facts.  This projection owns only the
    caller-supplied disposition, supporting-owner, and bounded-dynamic choices.
    It deliberately rebuilds the declaration-dependent findings so a raw
    unresolved observation cannot leak stale classification into the inventory.
    """

    disposition_map = dict(surface_dispositions or {})
    owner_map = dict(supporting_owners or {})
    allowance_map = {
        str(key): frozenset(str(item) for item in values)
        for key, values in dict(dynamic_allowances or {}).items()
    }
    contract_map: dict[tuple[str, str], DynamicSelectorContract] = {}
    duplicate_contract_keys: set[tuple[str, str]] = set()
    for contract in dynamic_selector_contracts:
        contract_key = (contract.surface_key, contract.operation)
        if contract_key in contract_map:
            duplicate_contract_keys.add(contract_key)
        else:
            contract_map[contract_key] = contract
    id_by_key = {
        implementation_surface_key(surface.path, surface.symbol): surface.surface_id
        for surface in observation.surfaces
    }
    known_ids = {surface.surface_id for surface in observation.surfaces}
    findings = [
        finding
        for finding in observation.findings
        if finding.code
        not in {
            "unresolved_surface_disposition",
            "dynamic_python_surface",
            "unknown_supporting_owner",
            "duplicate_dynamic_selector_contract",
            "dynamic_selector_contract_owner_mismatch",
            "dynamic_selector_contract_stale",
            "dynamic_selector_contract_source_mismatch",
            "dynamic_selector_contract_unbounded",
            "dynamic_selector_contract_values_mismatch",
            "unknown_dynamic_selector_contract_surface",
            "unknown_dynamic_selector_contract_operation",
        }
    ]
    projected: list[ImplementationSurface] = []
    for surface in observation.surfaces:
        key = implementation_surface_key(surface.path, surface.symbol)
        disposition = disposition_map.get(
            surface.surface_id,
            disposition_map.get(key, IMPLEMENTATION_DISPOSITION_UNRESOLVED),
        )
        owner_ref = owner_map.get(surface.surface_id, owner_map.get(key, ""))
        owner_id = id_by_key.get(
            owner_ref,
            owner_ref
            if owner_ref in known_ids
            or owner_ref.startswith("implementation-surface:")
            else "",
        )
        if owner_ref and not owner_id:
            findings.append(
                ImplementationInventoryFinding(
                    "unknown_supporting_owner",
                    f"supporting owner reference is not a discovered surface: {owner_ref}",
                    path=surface.path,
                    surface_id=surface.surface_id,
                )
            )
        allowed_dynamic = allowance_map.get(
            surface.surface_id,
            allowance_map.get(key, frozenset()),
        )
        contract_operations: set[str] = set()
        selector_source_fingerprints = dict(
            surface.dynamic_selector_source_fingerprints
        )
        finite_selector_values = dict(surface.dynamic_selector_values)
        for operation in sorted(set(surface.dynamic_operations)):
            contract_key = (key, operation)
            contract = contract_map.get(contract_key)
            if contract is None:
                continue
            if contract_key in duplicate_contract_keys:
                findings.append(
                    ImplementationInventoryFinding(
                        "duplicate_dynamic_selector_contract",
                        "dynamic selector surface and operation have more than one contract",
                        path=surface.path,
                        surface_id=surface.surface_id,
                    )
                )
                continue
            effective_owner_id = owner_id or surface.surface_id
            if contract.owner_surface_id != effective_owner_id:
                findings.append(
                    ImplementationInventoryFinding(
                        "dynamic_selector_contract_owner_mismatch",
                        "dynamic selector contract does not bind the current surface owner",
                        path=surface.path,
                        surface_id=surface.surface_id,
                    )
                )
                continue
            if contract.surface_structure_fingerprint != surface.structure_fingerprint:
                findings.append(
                    ImplementationInventoryFinding(
                        "dynamic_selector_contract_stale",
                        "dynamic selector contract does not bind the current surface structure",
                        path=surface.path,
                        surface_id=surface.surface_id,
                    )
                )
                continue
            if (
                selector_source_fingerprints.get(operation)
                != contract.selector_source_fingerprint
            ):
                findings.append(
                    ImplementationInventoryFinding(
                        "dynamic_selector_contract_source_mismatch",
                        "dynamic selector contract does not bind the observed selector source",
                        path=surface.path,
                        surface_id=surface.surface_id,
                    )
                )
                continue
            observed_values = finite_selector_values.get(operation)
            if observed_values is None:
                findings.append(
                    ImplementationInventoryFinding(
                        "dynamic_selector_contract_unbounded",
                        "dynamic selector source is open and has no exact static finite domain",
                        path=surface.path,
                        surface_id=surface.surface_id,
                    )
                )
                continue
            if observed_values != contract.selector_values:
                findings.append(
                    ImplementationInventoryFinding(
                        "dynamic_selector_contract_values_mismatch",
                        "dynamic selector contract values differ from the exact static domain",
                        path=surface.path,
                        surface_id=surface.surface_id,
                    )
                )
                continue
            contract_operations.add(operation)
        unresolved_dynamic = (
            set(surface.dynamic_operations)
            - set(allowed_dynamic)
            - contract_operations
        )
        roles = set(surface.roles) - {"dynamic", "dynamic_bounded"}
        if unresolved_dynamic:
            roles.add("dynamic")
        elif surface.dynamic_operations:
            roles.add("dynamic_bounded")
        projected.append(
            replace(
                surface,
                disposition=disposition,
                owning_surface_id=owner_id,
                roles=tuple(roles),
            )
        )
        if disposition == IMPLEMENTATION_DISPOSITION_UNRESOLVED:
            findings.append(
                ImplementationInventoryFinding(
                    "unresolved_surface_disposition",
                    "discovered Python surface has no explicit terminal disposition",
                    path=surface.path,
                    surface_id=surface.surface_id,
                )
            )
        if unresolved_dynamic:
            findings.append(
                ImplementationInventoryFinding(
                    "dynamic_python_surface",
                    "dynamic Python operation requires an explicit bounded interpretation: "
                    + ", ".join(sorted(unresolved_dynamic)),
                    path=surface.path,
                    surface_id=surface.surface_id,
                )
            )
    surface_by_key = {
        implementation_surface_key(surface.path, surface.symbol): surface
        for surface in projected
    }
    for (surface_key, operation), contract in sorted(contract_map.items()):
        surface = surface_by_key.get(surface_key)
        if surface is None:
            findings.append(
                ImplementationInventoryFinding(
                    "unknown_dynamic_selector_contract_surface",
                    f"dynamic selector contract references an undiscovered surface: {operation}",
                    path=observation.path,
                )
            )
        elif operation not in surface.dynamic_operations:
            findings.append(
                ImplementationInventoryFinding(
                    "unknown_dynamic_selector_contract_operation",
                    "dynamic selector contract operation is not observed on its bound surface",
                    path=surface.path,
                    surface_id=surface.surface_id,
                )
            )
    return ImplementationDiscoveryResult(
        adapter_id=observation.adapter_id,
        path=observation.path,
        surfaces=tuple(sorted(projected, key=lambda item: (item.line_start, item.symbol))),
        findings=tuple(findings),
    )


__all__ = [
    "PYTHON_AST_IMPLEMENTATION_ADAPTER_ID",
    "SIDE_EFFECT_CALL_PREFIXES",
    "DYNAMIC_CALLS",
    "derive_static_dynamic_selector_contracts",
    "discover_python_implementation_surfaces",
    "project_python_implementation_observation",
]
