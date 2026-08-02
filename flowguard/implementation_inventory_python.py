"""Conservative Python AST discovery for implementation inventories."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .implementation_inventory import (
    IMPLEMENTATION_DISPOSITION_UNRESOLVED,
    ImplementationDiscoveryResult,
    ImplementationFileDisposition,
    ImplementationInventoryFinding,
    ImplementationSurface,
    implementation_surface_id,
    implementation_surface_key,
)
from .portable_model import canonical_identity
from .source_identity import source_file_fingerprint


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
            elif name in DYNAMIC_CALLS or final in DYNAMIC_CALLS:
                if final in {"getattr", "setattr", "delattr"} and len(node.args) >= 2:
                    attribute = node.args[1]
                    if isinstance(attribute, ast.Constant) and isinstance(
                        attribute.value, str
                    ):
                        self.dynamic.append(f"{final}:{attribute.value}")
                    else:
                        self.dynamic.append(name)
                else:
                    self.dynamic.append(name)
        self.generic_visit(node)

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
        if isinstance(node.ctx, ast.Load):
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
        source_text = path.read_text(encoding="utf-8")
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
    current_fingerprint = source_file_fingerprint(path)
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
        return id_by_key.get(value, id_by_symbol.get(value, value if value in known_ids else ""))

    surfaces: list[ImplementationSurface] = []
    for spec in specs:
        surface_id = id_by_symbol[spec.symbol]
        key = implementation_surface_key(file_disposition.path, spec.symbol)
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
        roles = set(spec.roles)
        allowed_dynamic = allowance_map.get(
            surface_id,
            allowance_map.get(key, frozenset()),
        )
        unresolved_dynamic = set(spec.facts.dynamic) - set(allowed_dynamic)
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
        structure_fingerprint = canonical_identity(
            {
                "adapter_id": PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
                "ast": ast.dump(spec.node, annotate_fields=True, include_attributes=False),
            }
        )
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

    return ImplementationDiscoveryResult(
        adapter_id=PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
        path=file_disposition.path,
        surfaces=tuple(sorted(surfaces, key=lambda item: (item.line_start, item.symbol))),
        findings=tuple(findings),
    )


__all__ = [
    "PYTHON_AST_IMPLEMENTATION_ADAPTER_ID",
    "SIDE_EFFECT_CALL_PREFIXES",
    "DYNAMIC_CALLS",
    "discover_python_implementation_surfaces",
]
