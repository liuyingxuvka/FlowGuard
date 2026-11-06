"""C# grammar facts; assembly/type/runtime dispatch is never inferred by suffix."""
from __future__ import annotations

import ast
import math
import re

from .common import blank, fingerprint, parse, position, text, walk

TYPES = {"class_declaration": "class", "struct_declaration": "struct",
         "interface_declaration": "interface", "record_declaration": "record",
         "enum_declaration": "enum"}
FUNCTIONS = {"method_declaration", "constructor_declaration", "destructor_declaration",
             "local_function_statement", "operator_declaration", "conversion_operator_declaration",
             "lambda_expression", "anonymous_method_expression"}
PRIMITIVES = {"bool", "byte", "sbyte", "short", "ushort", "int", "uint", "long", "ulong",
              "nint", "nuint", "float", "double", "decimal", "char", "string", "object"}


def _field(node, name):
    return node.child_by_field_name(name) if node is not None else None


def _literal(node, source):
    if node is None:
        return None, False
    value = text(node, source)
    if value in ("true", "false", "null"):
        return {"true": True, "false": False, "null": None}[value], True
    if node.type in ("string_literal", "verbatim_string_literal", "character_literal"):
        if value.startswith('@"') and value.endswith('"'):
            return value[2:-1].replace('""', '"'), True
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return None, False
        return (parsed, True) if isinstance(parsed, str) else (None, False)
    number = value.replace("_", "")
    if node.type == "integer_literal" or re.fullmatch(r"[+-]?\d+[uUlL]*", number):
        number = re.sub(r"[uUlL]+$", "", number)
        if re.fullmatch(r"[+-]?0[xX][0-9a-fA-F]+|[+-]?0[bB][01]+", number):
            return int(number, 0), True
        if re.fullmatch(r"[+-]?\d+", number):
            return int(number), True
    if (node.type == "real_literal" or re.fullmatch(r"[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?[fFdD]?|[+-]?\d+[eE][+-]?\d+[fFdD]?", number)) and not number.lower().endswith("m"):
        try:
            result = float(re.sub(r"[fFdD]$", "", number))
        except ValueError:
            return None, False
        return (result, True) if math.isfinite(result) else (None, False)
    return None, False


def _initializer(node):
    found = False
    for child in node.children:
        if found and child.is_named:
            return child
        found = found or child.type == "="
    return None


def _conditional(node):
    while node is not None:
        if node.type.startswith(("preproc_if", "preproc_elif", "preproc_else")):
            return True
        node = node.parent
    return False


def extract(root, rel, data, module, is_test):
    source, tree = parse(data, "csharp")
    out = blank(module, source, "csharp")
    if tree.root_node.has_error:
        errors = [node for node in walk(tree.root_node) if node.is_error or node.is_missing]
        at = position(errors[0], source) if errors else {"line": 1, "column": 1}
        out["parse_error"] = f'C# syntax error at {rel}:{at["line"]}:{at["column"]}; facts are partial'
    owners, scopes, declarations, callables, class_fields, used = {}, {}, [], {}, {}, set()

    def modifiers(node):
        return {text(child, source) for child in node.named_children if child.type == "modifier"}

    def add_node(node, base, kind, cls="", **raw):
        at = position(node, source)
        body = _field(node, "body")
        signature = source[node.start_byte:(body.start_byte if body else node.end_byte)].decode("utf-8")
        qual = base
        if qual in used:
            params = text(_field(node, "parameters"), source)
            qual += "@" + re.sub(r"\s+", "", params) if params else f'@L{at["line"]}C{at["column"]}'
            if qual in used:
                qual += f'@L{at["line"]}C{at["column"]}'
        used.add(qual)
        name = text(_field(node, "name"), source)
        row = dict(qual=qual, kind=kind, cls=cls, line=at["line"], end=at["end_line"],
                   column=at["column"], end_column=at["end_column"], sig=signature[:200], doc="",
                   fp=fingerprint(node, source, name), shape=[], size=node.descendant_count,
                   raw=dict(declared_qual=base, declaration_kind=node.type,
                            requires_build_context=_conditional(node), **raw))
        out["nodes"].append(row)
        declarations.append(row)
        owners[node.id] = qual
        return row

    def bindings(body):
        names, dynamic, primitive = set(), set(), set()
        stack = list(body.named_children) if body else []
        while stack:
            node = stack.pop()
            if node.type in FUNCTIONS or node.type in TYPES:
                continue
            if node.type == "variable_declarator":
                name = text(_field(node, "name"), source)
                names.add(name)
                type_node = _field(node.parent, "type")
                declared_type = text(type_node, source)
                if declared_type == "dynamic":
                    dynamic.add(name)
                elif declared_type in PRIMITIVES:
                    primitive.add(name)
                elif declared_type == "var" and _literal(_initializer(node), source)[1]:
                    primitive.add(name)
            elif node.type in ("single_variable_designation", "catch_declaration", "foreach_statement"):
                name = _field(node, "name") or _field(node, "left")
                if name is not None:
                    names.add(text(name, source))
            stack.extend(node.named_children)
        return names, dynamic, primitive

    def visit_children(node, scope="", cls="", type_qual="", namespace="", flags=frozenset(), parent_fn=""):
        current_scope, current_namespace = scope, namespace
        for child in node.named_children:
            if child.type == "file_scoped_namespace_declaration":
                name = text(_field(child, "name"), source)
                current_scope = ".".join(part for part in (scope, name) if part)
                current_namespace = current_scope
                add_node(child, current_scope, "namespace", namespace=current_namespace)
            else:
                visit(child, current_scope, cls, type_qual, current_namespace, flags, parent_fn)

    def visit(node, scope, cls, type_qual, namespace, flags, parent_fn):
        scopes[node.id] = scope
        if node.type == "namespace_declaration":
            name = text(_field(node, "name"), source)
            qual = ".".join(part for part in (scope, name) if part)
            add_node(node, qual, "namespace", namespace=qual)
            visit_children(_field(node, "body") or node, qual, namespace=qual)
            return
        if node.type in TYPES:
            name = text(_field(node, "name"), source)
            if name:
                base = ".".join(part for part in (scope, name) if part)
                own_flags = modifiers(node)
                if any(child.type == "type_parameter_list" for child in node.named_children):
                    own_flags.add("generic")
                if any(child.type == "base_list" for child in node.named_children):
                    own_flags.add("inheritance")
                row = add_node(node, base, TYPES[node.type], cls, namespace=namespace,
                               modifiers=sorted(own_flags), partial="partial" in own_flags)
                class_fields.setdefault(base, {})
                body = _field(node, "body")
                if body:
                    for child in body.named_children:
                        if child.type == "field_declaration":
                            for declaration in child.named_children:
                                if declaration.type == "variable_declaration":
                                    declared_type = text(_field(declaration, "type"), source)
                                    for variable in declaration.named_children:
                                        if variable.type == "variable_declarator":
                                            class_fields[base][text(_field(variable, "name"), source)] = declared_type
                visit_children(node, base, row["qual"], base, namespace,
                               frozenset(own_flags & {"partial", "generic", "inheritance"}), parent_fn)
                return
        if node.type in FUNCTIONS:
            name = text(_field(node, "name"), source)
            if not name:
                operator = _field(node, "operator")
                at = position(node, source)
                name = "operator" + text(operator, source) if operator else f'<anonymous@{at["line"]},{at["column"]}>'
            base = ".".join(part for part in (scope, name) if part)
            arguments = _field(node, "parameters")
            parameters, dynamic, primitive = [], set(), set()
            if arguments:
                for parameter in ([arguments] if arguments.type == "implicit_parameter" else arguments.named_children):
                    name_node = _field(parameter, "name") or (parameter if parameter.type in ("identifier", "implicit_parameter") else None)
                    if name_node:
                        param_name = text(name_node, source)
                        parameters.append(param_name)
                        declared_type = text(_field(parameter, "type"), source)
                        if declared_type == "dynamic":
                            dynamic.add(param_name)
                        elif declared_type in PRIMITIVES:
                            primitive.add(param_name)
            body = _field(node, "body") or next((n for n in node.named_children if n.type == "block"), None)
            local_names, local_dynamic, local_primitive = bindings(body)
            inherited = callables.get(parent_fn, {})
            shadows = set(parameters) | local_names | set(inherited.get("shadows", ()))
            dynamic |= local_dynamic | set(inherited.get("dynamic", ()))
            primitive |= local_primitive | set(inherited.get("primitive", ()))
            own_modifiers = modifiers(node)
            if _field(node, "type_parameters") is not None:
                own_modifiers.add("generic")
            local = node.type in ("local_function_statement", "lambda_expression", "anonymous_method_expression")
            row = add_node(node, base, "function" if local or not cls else "method", cls,
                           namespace=namespace, type_qual=type_qual, modifiers=sorted(own_modifiers),
                           parameters=parameters, shadows=sorted(shadows),
                           declaration_only=body is None, partial="partial" in own_modifiers)
            callables[row["qual"]] = dict(row=row, parameters=parameters, shadows=shadows,
                dynamic=dynamic, primitive=primitive, type_qual=type_qual, type_flags=flags)
            visit_children(node, row["qual"], cls, type_qual, namespace, flags, row["qual"])
            return
        visit_children(node, scope, cls, type_qual, namespace, flags, parent_fn)

    visit_children(tree.root_node)

    def owner(node):
        fallback = scopes.get(node.id, "") if node is not None else ""
        while node is not None:
            if node.id in owners:
                return owners[node.id]
            node = node.parent
        return fallback

    def fact(node, **values):
        scope = owner(node)
        return dict(node=module + (":" + scope if scope else ""), file=rel,
                    **position(node, source), **values)

    def key(node):
        if node is None:
            return ""
        if node.type == "member_access_expression":
            name = _field(node, "name")
            return text(name, source) if name and name.type == "identifier" else ""
        if node.type == "element_access_expression":
            args = _field(node, "subscript")
            if args and len(args.named_children) == 1:
                argument = args.named_children[0]
                value, known = _literal(argument.named_children[-1] if argument.named_children else argument, source)
                return value if known and isinstance(value, str) else ""
        return ""

    def call_reason(node, callee, scope, args):
        spelling = text(callee, source)
        info = callables.get(scope, {})
        if _conditional(node):
            return spelling, "conditional C# code requires preprocessing/build context"
        if callee is None or callee.type != "identifier":
            return spelling, "member, generic, constructor or indirect dispatch requires C# semantic context"
        if spelling in info.get("shadows", ()):
            return spelling, "parameter or local callable shadows the declaration"
        if spelling in class_fields.get(info.get("type_qual", ""), {}):
            return spelling, "field callable requires C# type/runtime binding"
        arguments = list(args.named_children) if args else []
        for argument in arguments:
            value = argument.named_children[-1] if argument.type == "argument" and argument.named_children else argument
            if any(text(n, source) in info.get("dynamic", ()) for n in walk(value) if n.type == "identifier"):
                return spelling, "dynamic argument requires runtime overload binding"
            if not _literal(value, source)[1] and not (value.type == "identifier" and text(value, source) in info.get("primitive", ())):
                return spelling, "argument types require C# semantic overload resolution"
        levels = scope.split(".") if scope else []
        while True:
            expected = ".".join([*levels, spelling])
            targets = [row for row in declarations if row["raw"]["declared_qual"] == expected
                       and row["kind"] in ("method", "function")]
            if targets:
                if len(targets) != 1:
                    return spelling, "overload or partial declarations require C# semantic resolution"
                target = targets[0]
                raw = target["raw"]
                if raw["requires_build_context"] or raw.get("declaration_only") or raw.get("partial") or set(raw.get("modifiers", ())) & {"generic", "virtual", "override", "abstract", "extern"}:
                    return spelling, "partial, generic or conditional declaration requires C# semantic context"
                if raw["declaration_kind"] == "local_function_statement":
                    return expected, ""
                if "static" in raw.get("modifiers", ()) and not info.get("type_flags") and target["cls"]:
                    return expected, ""
                return spelling, "instance, virtual or type-dependent method dispatch requires C# semantic context"
            if not levels:
                break
            levels.pop()
        return spelling, "callee has no proven file-local C# binding"

    for node in walk(tree.root_node):
        scope = owner(node)
        if node.type in ("using_directive", "extern_alias_directive"):
            alias = text(_field(node, "name"), source)
            target = node.named_children[-1] if node.named_children else None
            if alias and target and text(target, source) == alias:
                alias = ""
            out["dependencies"].append(dict(module=text(target, source), name="*" if "static" in [c.type for c in node.children] else "",
                alias=alias, kind="using", scope=scope, relative=False, **position(node, source),
                reason="using/alias resolution requires project and assembly context"))
        elif node.type in ("invocation_expression", "object_creation_expression", "implicit_object_creation_expression", "constructor_initializer"):
            callee = _field(node, "function") or _field(node, "type")
            args = _field(node, "arguments") or next((n for n in node.named_children if n.type == "argument_list"), None)
            spelling = text(callee, source) or text(node, source).split("(", 1)[0]
            candidate, reason = call_reason(node, callee, scope, args)
            if node.type != "invocation_expression":
                reason = "constructor dispatch requires C# type/assembly context"
            info = callables.get(scope, {})
            out["syntax_calls"].append(fact(node, text=spelling, candidate=candidate, scope=scope,
                parameters=info.get("parameters", []), shadows=sorted(info.get("shadows", ())),
                resolved=None, reason=reason, positional_arg_count=len(args.named_children) if args else 0))
        elif node.type in ("assignment_expression", "variable_declarator", "postfix_unary_expression", "prefix_unary_expression"):
            updating = node.type in ("postfix_unary_expression", "prefix_unary_expression")
            if updating and not any(c.type in ("++", "--") for c in node.children):
                continue
            left = _field(node, "left") or _field(node, "name") or (node.named_children[0] if updating and node.named_children else None)
            right = _field(node, "right") if node.type == "assignment_expression" else _initializer(node) if not updating else None
            if left is not None:
                field_name = key(left)
                info = callables.get(scope, {})
                bare = text(left, source)
                declaration = node.parent.parent if node.type == "variable_declarator" and node.parent else None
                field_declaration = declaration is not None and declaration.type == "field_declaration"
                if left.type == "identifier" and (field_declaration or bare in class_fields.get(info.get("type_qual", ""), {}) and bare not in info.get("shadows", ())):
                    field_name = bare
                value, known = _literal(right, source)
                operator = text(_field(node, "operator"), source)
                out["assignments"].append(fact(node, target=bare, field=field_name, value=value,
                    literal=known, operation="update" if updating or operator not in ("", "=") else "write",
                    binding_mutation=node.type != "variable_declarator" and left.type == "identifier"))
                if field_name:
                    out["keys"].append(("field", field_name, node.start_point.row + 1, scope))
                if field_declaration and "const" in modifiers(declaration):
                    add_node(node, ".".join(part for part in (scope, bare) if part), "const", value_type=text(_field(node.parent, "type"), source))
                    out["keys"].append(("constant", bare, node.start_point.row + 1, scope))
        elif node.type in ("member_access_expression", "element_access_expression"):
            parent = node.parent
            call_target = parent and parent.type == "invocation_expression" and _field(parent, "function") == node
            written = parent and parent.type == "assignment_expression" and _field(parent, "left") == node and text(_field(parent, "operator"), source) == "="
            if not call_target and not written:
                field_name = key(node)
                out["symbol_reads"].append(fact(node, text=text(node, source), field=field_name,
                    kind="read", resolved=None, reason="" if field_name else "computed member/index name requires runtime binding"))
                if field_name:
                    out["keys"].append(("field", field_name, node.start_point.row + 1, scope))
        elif node.type == "identifier":
            parent = node.parent
            if parent is None or parent.type in ("qualified_name", "generic_name", "type_argument_list", "using_directive", "name_colon", "explicit_interface_specifier"):
                continue
            if any(_field(parent, name) == node for name in ("name", "type", "returns")):
                continue
            if parent.type == "invocation_expression" and _field(parent, "function") == node:
                continue
            if parent.type == "assignment_expression" and _field(parent, "left") == node and text(_field(parent, "operator"), source) == "=":
                continue
            name = text(node, source)
            info = callables.get(scope, {})
            field_name = name if name in class_fields.get(info.get("type_qual", ""), {}) and name not in info.get("shadows", ()) else ""
            out["symbol_reads"].append(fact(node, text=name, field=field_name, kind="read", resolved=None))
            if field_name:
                out["keys"].append(("field", field_name, node.start_point.row + 1, scope))
        elif node.type in ("string_literal", "verbatim_string_literal", "character_literal"):
            value, known = _literal(node, source)
            if known:
                out["keys"].append(("constant", value, node.start_point.row + 1, scope))
    return out
