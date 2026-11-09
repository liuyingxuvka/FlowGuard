"""JS/TS syntax facts. Lexical declarations are facts; runtime dispatch stays unknown."""
from __future__ import annotations
import ast
from .common import blank, parse, text, position, fingerprint, walk
from ..analysis import kinds_shape

SHAPE_K = 64                       # the same bottom-k sketch as the Python map (extract.SHAPE_K)

FUNCTIONS = {'function_declaration', 'function_expression', 'generator_function_declaration',
             'generator_function', 'arrow_function', 'method_definition', 'function_signature', 'method_signature'}
CLASSES = {'class_declaration', 'abstract_class_declaration', 'interface_declaration', 'enum_declaration'}


def literal(node, source):
    if node is None:
        return False, None
    value = text(node, source)
    if node.type in ('true', 'false', 'null'):
        return True, {'true':True, 'false':False, 'null':None}[node.type]
    if node.type in ('string', 'number'):
        try:
            return True, ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return False, None
    return False, None


def constant_like(name):
    """A name spelled as a constant (`LIMIT`, `MAX_DAYS`), as decide.named_constant reads Python names."""
    return name.strip('_').isupper()


COMMENTS = {'comment', 'line_comment', 'block_comment', 'html_comment'}
WRAPPERS = {'parenthesized_expression', 'as_expression', 'satisfies_expression', 'non_null_expression',
            'type_assertion', 'await_expression'}
EQUALITY = {'===', '!==', '==', '!='}
LOG_OBJECTS = {'console', 'logger', 'log', 'logging'}
PRISMA_WRITES = {'create', 'createMany', 'createManyAndReturn', 'update', 'updateMany', 'updateManyAndReturn',
                 'upsert', 'delete', 'deleteMany'}
PRISMA_ARGS = {'data', 'where', 'create', 'update', 'select', 'include', 'omit'}
NESTED = {'create', 'createMany', 'connect', 'connectOrCreate', 'disconnect', 'set', 'update', 'updateMany',
          'upsert', 'delete', 'deleteMany'}
SCALAR_OPS = {'set', 'increment', 'decrement', 'multiply', 'divide', 'push', 'unset'}
RAW_WRITES = {'$executeRaw', '$executeRawUnsafe'}
PRISMA_READS = {'count', 'findFirst', 'findFirstOrThrow', 'findMany', 'findUnique', 'findUniqueOrThrow', 'aggregate',
                'groupBy'}
QUERY_ARGS = {'where', 'select', 'include', 'orderBy', 'take', 'skip', 'distinct', 'cursor', 'by', '_count'}
LOGIC = {'AND', 'OR', 'NOT'}
ORDER = {'<', '<=', '>', '>='}


def own_kinds(node):
    """Node kinds of one function body in depth-first order, without the bodies of nested functions or
    classes (as Python's own_nodes); operators count, comments do not."""
    out, stack = [], [node]
    while stack:
        item = stack.pop()
        out.append(item.type)
        if item is not node and item.type in FUNCTIONS | CLASSES:
            continue
        children = [child for index, child in enumerate(item.children)
                    if child.is_named and child.type not in COMMENTS or item.field_name_for_child(index) == 'operator']
        stack.extend(reversed(children))
    return out


def unwrap(node):
    while node is not None and node.type in WRAPPERS and node.named_children:
        node = node.named_children[0]
    return node


def operator(node):
    found = node.child_by_field_name('operator')
    return found.type if found is not None else ''


def named_scope(scope):
    """The enclosing named function for a stable key: anonymous callbacks and overload suffixes drop out."""
    parts = [part.split('@')[0] for part in scope.split('.') if part and not part.startswith('<anonymous')]
    return '.'.join(part for part in parts if part) or '<module>'


def extract(root, rel, data, module, is_test):
    from .registry import language_for
    from .context import propagate_names
    language = language_for(rel)
    out = blank(module, data, language)
    out.update(queries=[], value_sets=[], typed_fields=[], typed_writes=[], numbers=[], compared_names=[],
               const_tables=[], table_lookups=[])
    source, tree = parse(data, language)
    handed_on = set(propagate_names(root))
    if tree.root_node.has_error:
        out['parse_error'] = 'grammar contains ERROR/missing nodes; facts are partial syntax only'
    out['exports'], out['bindings'] = {}, []
    used = set()

    def field(node, name):
        return node.child_by_field_name(name)

    def string(node):
        valid, value = literal(node, source)
        return value if valid and isinstance(value, str) else None

    def add_dep(node, spelling, name='', alias='', kind='import', scope=''):
        row = dict(module=spelling or '', name=name, alias=alias, kind=kind, scope=scope,
                   relative=bool(spelling and spelling.startswith('.')), **position(node, source))
        if not spelling:
            row['reason'] = 'module specifier is not a literal string'
        out['dependencies'].append(row)
        return row

    def imports(node, scope):
        spelling = string(field(node, 'source'))
        if node.type == 'import_statement':
            clause = next((x for x in node.named_children if x.type == 'import_clause'), None)
            if clause is None:
                add_dep(node, spelling, scope=scope)
            else:
                for item in clause.named_children:
                    if item.type == 'identifier':
                        add_dep(item, spelling, 'default', text(item, source), scope=scope)
                    elif item.type == 'namespace_import':
                        add_dep(item, spelling, '*', text(item.named_children[-1], source), scope=scope)
                    else:
                        for spec in item.named_children:
                            if spec.type == 'import_specifier':
                                name = text(field(spec, 'name'), source)
                                add_dep(spec, spelling, name, text(field(spec, 'alias'), source) or name, scope=scope)
        elif spelling is not None:
            clause = next((x for x in node.named_children if x.type == 'export_clause'), None)
            if clause:
                for spec in clause.named_children:
                    name = text(field(spec, 'name'), source)
                    exported = text(field(spec, 'alias'), source) or name
                    add_dep(spec, spelling, name, exported, 'reexport', scope)
                    out['exports'][exported] = dict(module=spelling, name=name)
            else:
                add_dep(node, spelling, '*', '', 'reexport', scope)
        else:
            clause = next((x for x in node.named_children if x.type == 'export_clause'), None)
            if clause:
                for spec in clause.named_children:
                    name = text(field(spec, 'name'), source)
                    out['exports'][text(field(spec, 'alias'), source) or name] = name

    def local_functions(node):
        result=set();stack=list(node.named_children)
        while stack:
            child=stack.pop()
            if child.type in FUNCTIONS:
                result.add(name_of(child));continue
            if child.type in CLASSES:
                continue
            stack.extend(child.named_children)
        return result

    def scoped_names(node):
        names, stack = set(), list(node.named_children)
        while stack:
            child = stack.pop()
            if child.type in FUNCTIONS or child.type in CLASSES:
                continue
            if child.type == 'variable_declarator' and (name := field(child, 'name')) is not None and (field(child, 'value') is None or field(child, 'value').type not in FUNCTIONS):
                names.update(text(x, source) for x in [name, *name.named_children] if x.type in ('identifier', 'shorthand_property_identifier_pattern'))
            if child.type in ('assignment_expression','augmented_assignment_expression','update_expression'):
                target=field(child,'left') or field(child,'argument')
                if target and target.type=='identifier':
                    names.add(text(target,source))
            stack.extend(child.named_children)
        return names

    def name_of(node):
        name = field(node, 'name')
        if name is not None:
            return text(name, source)
        parent = node.parent
        if parent and parent.type == 'variable_declarator':
            return text(field(parent, 'name'), source)
        if parent and parent.type == 'export_statement':
            return 'default'
        return f'<anonymous@{node.start_point.row + 1},{node.start_point.column + 1}>'

    def key_of(node):
        if node.type in ('member_expression', 'optional_member_expression'):
            prop = field(node, 'property')
            return text(prop, source) if prop and prop.type in ('property_identifier', 'identifier', 'private_property_identifier') else None
        if node.type == 'subscript_expression':
            return string(field(node, 'index'))
        return None

    # ---- catch clauses: handed on, or a fallback that ends without raising ----------------------
    def enclosing_parameters(node):
        names, item = set(), node.parent
        while item is not None:
            if item.type in FUNCTIONS:
                params = field(item, 'parameters')
                for arg in (params.named_children if params else [field(item, 'parameter')] if field(item, 'parameter') else []):
                    pattern = field(arg, 'pattern') or field(arg, 'name') or arg
                    if pattern is not None and pattern.type == 'identifier':
                        names.add(text(pattern, source))
            item = item.parent
        return names

    def hands_on(expression, error, callbacks):
        """`next(err)`, `reject(err)`, `callback(err)`, a configured name, or `Promise.reject(...)`."""
        call = unwrap(expression)
        if call is None or call.type != 'call_expression':
            return ''
        callee, args = field(call, 'function'), field(call, 'arguments')
        name = text(callee, source)
        first = args.named_children[0] if args is not None and args.named_children else None
        if name == 'Promise.reject':
            return 'Promise.reject'
        if error and first is not None and first.type == 'identifier' and text(first, source) == error \
                and (name in handed_on or callee.type == 'identifier' and name in callbacks):
            return name
        return ''

    def outcome(statements, error, callbacks, handed, in_loop=False):
        """(can finish normally, can leave without raising): the TS form of query.handler_outcome."""
        falls, leaves = True, False
        for item in statements:
            if not falls:
                break
            if item.type in COMMENTS or not item.is_named:
                continue
            branch = lambda body, loop=in_loop: outcome(body, error, callbacks, handed, loop)
            kind = item.type
            if kind == 'throw_statement':
                handed.add('throw')
                falls = False
            elif kind == 'return_statement':
                value = item.named_children[0] if item.named_children else None
                how = hands_on(value, error, callbacks) if value is not None else ''
                falls, leaves = False, leaves or not how
                if how:
                    handed.add(how)
            elif kind == 'expression_statement':
                how = hands_on(item.named_children[0], error, callbacks) if item.named_children else ''
                if how:
                    handed.add(how)
                    falls = False
            elif kind in ('break_statement', 'continue_statement'):
                falls, leaves = False, leaves or not in_loop
            elif kind == 'statement_block':
                falls, extra = branch(item.named_children)
                leaves |= extra
            elif kind == 'if_statement':
                other = field(item, 'alternative')
                first = branch([field(item, 'consequence')])
                second = branch([x for x in other.named_children if x.type not in COMMENTS]) if other is not None else (True, False)
                falls, leaves = first[0] or second[0], leaves or first[1] or second[1]
            elif kind == 'labeled_statement':
                falls, extra = branch([field(item, 'body')] if field(item, 'body') else [])
                leaves |= extra
            elif kind in ('for_statement', 'for_in_statement', 'while_statement', 'do_statement'):
                leaves |= branch([field(item, 'body')] if field(item, 'body') else [], True)[1]
            elif kind == 'try_statement':
                body, handler, final = field(item, 'body'), field(item, 'handler'), field(item, 'finalizer')
                result = branch(body.named_children if body else [])
                falls, extra = result
                if handler is not None and field(handler, 'body') is not None:
                    caught = branch(field(handler, 'body').named_children)
                    falls, extra = falls or caught[0], extra or caught[1]
                if final is not None and field(final, 'body') is not None:
                    closing = branch(field(final, 'body').named_children)
                    falls, extra = falls and closing[0], extra or closing[1]
                leaves |= extra
            elif kind == 'switch_statement':
                body = field(item, 'body')
                for case in body.named_children if body else []:
                    leaves |= branch([x for x in case.named_children if x != field(case, 'value')], True)[1]
        return falls, leaves

    def own_nodes(node):
        stack = list(node.named_children)
        while stack:
            item = stack.pop()
            yield item
            if item.type not in FUNCTIONS | CLASSES:
                stack.extend(item.named_children)

    def catch(node, owner, scope):
        parameter, body = field(node, 'parameter'), field(node, 'body')
        error = text(parameter, source) if parameter is not None and parameter.type == 'identifier' else ''
        caught = 'any'            # A JS/TS catch takes every thrown value; the parameter name is not a type.
        annotation = field(node, 'type')
        handed = set()
        falls, leaves = outcome(body.named_children if body else [], error, enclosing_parameters(node), handed)
        throws = [item for item in own_nodes(body)] if body is not None else []
        function = named_scope(scope)
        out['handlers'].append(dict(node=owner, file=rel, kind='catch', type=caught, name=error or None,
            annotation=text(annotation.named_children[0], source) if annotation is not None and annotation.named_children else '',
            raises=any(item.type == 'throw_statement' for item in throws),
            reraise=bool(error) and any(item.type == 'throw_statement' and item.named_children
                                        and unwrap(item.named_children[0]) is not None
                                        and text(unwrap(item.named_children[0]), source) == error for item in throws),
            non_raising=falls or leaves, propagates=sorted(handed) if not (falls or leaves) else [],
            hands_on=sorted(handed), function=function, key=f'{rel}:{function}:{caught}',
            body=text(body, source), **position(node, source)))

    # ---- string literals that decide or name a value -----------------------------------------
    def logged_or_raised(node):
        item = node.parent
        while item is not None and item.type not in FUNCTIONS and item.type != 'program':
            if item.type == 'throw_statement':
                return True
            if item.type == 'arguments' and item.parent is not None:
                call = item.parent
                callee = field(call, 'function') or field(call, 'constructor')
                name = text(callee, source) if callee is not None else ''
                if call.type == 'new_expression' and name.rsplit('.', 1)[-1].endswith(('Error', 'Exception')):
                    return True
                if callee is not None and callee.type == 'member_expression':
                    receiver = field(callee, 'object')
                    last = text(receiver, source).rsplit('.', 1)[-1] if receiver is not None else ''
                    if last in LOG_OBJECTS or last.endswith(('Logger', 'logger')):
                        return True
            item = item.parent
        return False

    def literal_context(node):
        child, parent = node, node.parent
        while parent is not None and (parent.type in WRAPPERS or parent.type == 'ternary_expression' and child != field(parent, 'condition')
                                      or parent.type == 'binary_expression' and operator(parent) in ('??', '||', '&&')):
            child, parent = parent, parent.parent
        if parent is None:
            return ''
        kind = parent.type
        context = ''
        if kind == 'literal_type' and parent.parent is not None and parent.parent.type == 'union_type':
            context = 'union'
        elif kind == 'switch_case' and child == field(parent, 'value'):
            context = 'case'
        elif kind == 'binary_expression' and operator(parent) in EQUALITY:
            other = field(parent, 'right') if child == field(parent, 'left') else field(parent, 'left')
            context = '' if other is not None and other.type == 'unary_expression' and operator(other) == 'typeof' else 'compare'
        elif kind == 'return_statement' or kind == 'arrow_function' and child == field(parent, 'body'):
            context = 'return'
        elif kind == 'array' and child == node:
            holder = parent.parent
            constructor = field(holder.parent, 'constructor') if holder is not None and holder.type == 'arguments' \
                and holder.parent is not None and holder.parent.type == 'new_expression' else None
            context = 'set' if constructor is not None and text(constructor, source) in ('Set', 'ReadonlySet', 'WeakSet') else 'array'
        elif kind == 'arguments' and child == node and parent.parent is not None and parent.parent.type == 'call_expression':
            callee = field(parent.parent, 'function')
            prop = field(callee, 'property') if callee is not None and callee.type == 'member_expression' else None
            context = 'member' if prop is not None and text(prop, source) in ('includes', 'has') else ''
        return '' if not context or logged_or_raised(node) else context

    # ---- Prisma client writes and raw SQL ------------------------------------------------------
    def local_value(identifier):
        """The object literal a block-scoped `const name = {...}` holds, with the `name.f = ...` writes
        in that block; a parameter, a reassigned name or several declarations stay unknown."""
        name = text(identifier, source)
        item = identifier.parent
        while item is not None:
            if item.type in FUNCTIONS:
                parameters = field(item, 'parameters') or field(item, 'parameter')
                if parameters is not None and name in {text(x, source) for x in walk(parameters) if x.type == 'identifier'}:
                    return None, [], f'{name} is a parameter'
            if item.type in ('statement_block', 'program', 'switch_case', 'switch_default'):
                declared = [declarator for statement in item.named_children
                            if statement.type in ('lexical_declaration', 'variable_declaration')
                            for declarator in statement.named_children
                            if declarator.type == 'variable_declarator' and text(field(declarator, 'name'), source) == name]
                if declared:
                    members, rebound = [], False
                    for node in own_nodes(item):
                        if node.type in ('assignment_expression', 'augmented_assignment_expression'):
                            left = field(node, 'left')
                            if left is not None and left.type == 'identifier' and text(left, source) == name:
                                rebound = True
                            elif left is not None and left.type == 'member_expression' and text(field(left, 'object'), source) == name:
                                members.append(left)
                    value = field(declared[0], 'value')
                    if len(declared) != 1 or value is None or rebound:
                        return None, [], f'{name} is not one local object literal'
                    return unwrap(value), members, ''
            item = item.parent
        return None, [], f'{name} is not declared in this file'

    def add_write(rows, base, path, leaf, at, reason='', written=None):
        rows.append(dict(base, path=path, leaf=leaf, reason=reason, **(written or {}), **position(at, source)))

    def in_loop(node):
        """Is a call inside a loop of its function: a for/while/do body, or a callback of `.forEach`/`.map`?"""
        child, parent = node, node.parent
        while parent is not None:
            if parent.type in ('for_statement', 'for_in_statement', 'while_statement', 'do_statement') \
                    and child == field(parent, 'body'):
                return True
            if child.type in FUNCTIONS:
                call = parent.parent if parent.type == 'arguments' else None
                callee = field(call, 'function') if call is not None and call.type == 'call_expression' else None
                prop = field(callee, 'property') if callee is not None and callee.type == 'member_expression' else None
                return prop is not None and text(prop, source) in ('forEach', 'map', 'flatMap')
            child, parent = parent, parent.parent
        return False

    def value_parts(node):
        """[('value', v) | ('ref', 'Name.KEY')] an expression can take: a literal, a member of a named
        object (`Status.ACTIVE`), or each branch of `c ? a : b`; None when any part is not spelled. The
        fallback of `x ?? 'v'` is a part, with ('partial', None) when `x` is not spelled."""
        node = unwrap(node)
        if node is None:
            return None
        if node.type == 'ternary_expression':
            first, second = value_parts(field(node, 'consequence')), value_parts(field(node, 'alternative'))
            return first + second if first is not None and second is not None else None
        if node.type == 'binary_expression' and operator(node) == '??':
            first, second = value_parts(field(node, 'left')), value_parts(field(node, 'right'))
            return None if second is None else (first if first is not None else [('partial', None)]) + second
        valid, value = literal(node, source)
        if valid:
            return [('value', value)]
        if node.type == 'member_expression' and field(node, 'object') is not None and field(node, 'object').type == 'identifier' \
                and field(node, 'property') is not None and field(node, 'property').type == 'property_identifier' \
                and text(field(node, 'property'), source).replace('_', '').isupper():
            return [('ref', text(node, source))]
        return None

    def written_of(node):
        """`values` (literals) and `refs` (`Name.KEY` spellings) of a written expression, when every part is spelled;
        `partial` when only the fallback of `x ?? 'v'` is (the value may also be what `x` holds)."""
        parts = value_parts(node)
        if not parts:
            return {}
        return dict(values=[value for kind, value in parts if kind == 'value'], refs=[value for kind, value in parts if kind == 'ref'],
                    **({'partial': True} if ('partial', None) in parts else {}))

    def object_fields(value, base, prefix, rows, depth=0):
        """Write paths of one Prisma data value: fields, nested operations and what stays unclear."""
        value = unwrap(value)
        if value is None or depth > 8:
            return
        if value.type == 'array':
            for item in value.named_children:
                object_fields(item, base, prefix, rows, depth + 1)
            return
        if value.type == 'ternary_expression':
            for item in (field(value, 'consequence'), field(value, 'alternative')):
                object_fields(item, base, prefix, rows, depth + 1)
            return
        if value.type == 'binary_expression' and operator(value) in ('&&', '||', '??'):
            object_fields(field(value, 'right'), base, prefix, rows, depth + 1)
            if operator(value) != '&&':
                object_fields(field(value, 'left'), base, prefix, rows, depth + 1)
            return
        if value.type == 'call_expression':
            callee, args = field(value, 'function'), field(value, 'arguments')
            prop = field(callee, 'property') if callee is not None and callee.type == 'member_expression' else None
            mapper = args.named_children[0] if args is not None and args.named_children else None
            if prop is not None and text(prop, source) == 'map' and mapper is not None and mapper.type in ('arrow_function', 'function_expression'):
                body = unwrap(field(mapper, 'body'))
                if body is not None and body.type == 'statement_block':
                    returned = [item for item in own_nodes(body) if item.type == 'return_statement' and item.named_children]
                    body = returned[0].named_children[0] if len(returned) == 1 else None
                if body is not None:
                    object_fields(body, base, prefix, rows, depth + 1)
                    return
        if value.type in ('identifier', 'shorthand_property_identifier'):
            found, members, reason = local_value(value)
            if found is not None and found != value:
                object_fields(found, base, prefix, rows, depth + 1)
                for member in members:
                    prop = field(member, 'property')
                    add_write(rows, base, prefix + [text(prop, source)], 'field', member,
                              written=written_of(field(member.parent, 'right')) if member.parent is not None else None)
                return
            add_write(rows, base, prefix + ['...'], 'spread', value, reason)
            return
        if value.type != 'object':
            if value.type not in ('undefined', 'null', 'true', 'false'):
                add_write(rows, base, prefix + ['...'], 'opaque', value,
                          'computed value (' + value.type.replace('_', ' ') + '): written fields are not visible')
            return
        for item in value.named_children:
            if item.type in COMMENTS:
                continue
            if item.type == 'shorthand_property_identifier':
                add_write(rows, base, prefix + [text(item, source)], 'field', item)
            elif item.type == 'spread_element':
                inner = unwrap(item.named_children[0]) if item.named_children else None
                if inner is not None and inner.type in ('object', 'ternary_expression', 'binary_expression', 'identifier', 'call_expression'):
                    object_fields(inner, base, prefix, rows, depth + 1)
                else:
                    add_write(rows, base, prefix + ['...'], 'spread', item, 'spread object: written fields are not visible')
            elif item.type == 'pair':
                key = field(item, 'key')
                name = text(key, source) if key.type == 'property_identifier' else string(key)
                if name is None:
                    add_write(rows, base, prefix + ['...'], 'spread', key, 'computed field name')
                    continue
                nested_value(name, field(item, 'value'), base, prefix, rows, key, depth)
            elif item.type == 'method_definition':
                continue

    def nested_value(name, value, base, prefix, rows, key, depth):
        inner = unwrap(value)
        keys = {}
        if inner is not None and inner.type == 'object':
            for pair in inner.named_children:
                if pair.type == 'pair' and field(pair, 'key').type == 'property_identifier':
                    keys[text(field(pair, 'key'), source)] = field(pair, 'value')
                elif pair.type not in COMMENTS:
                    keys = {}
                    break
        if not keys or not set(keys) <= NESTED | SCALAR_OPS or set(keys) <= SCALAR_OPS - {'set'}:
            add_write(rows, base, prefix + [name], 'field', key, written=written_of(value))   # a value, or {increment: 1}
            return
        if set(keys) == {'set'} and unwrap(keys['set']) is not None and unwrap(keys['set']).type != 'array':
            add_write(rows, base, prefix + [name], 'field', key, written=written_of(keys['set']))   # scalar { set: value }
            return
        for op, item in keys.items():
            here = prefix + [name, op]
            add_write(rows, base, here, 'delete' if op in ('delete', 'deleteMany') else 'relation', key)
            if op in ('create', 'createMany'):
                part = unwrap(item)
                if op == 'createMany' and part is not None and part.type == 'object':
                    data = [field(x, 'value') for x in part.named_children if x.type == 'pair' and text(field(x, 'key'), source) == 'data']
                    part = data[0] if data else None
                object_fields(part, base, here, rows, depth + 1)
            elif op == 'connectOrCreate':
                for create in members_named(item, 'create'):
                    object_fields(create, base, here, rows, depth + 1)
            elif op in ('update', 'updateMany'):
                for data in update_data(item):
                    object_fields(data, base, here, rows, depth + 1)
            elif op == 'upsert':
                for branch in ('create', 'update'):
                    for part in members_named(item, branch):
                        object_fields(part, base, prefix + [name, branch], rows, depth + 1)

    def members_named(value, name):
        value = unwrap(value)
        items = value.named_children if value is not None and value.type == 'array' else [value]
        for item in items:
            item = unwrap(item)
            if item is not None and item.type == 'object':
                yield from (field(x, 'value') for x in item.named_children
                            if x.type == 'pair' and text(field(x, 'key'), source) == name)

    def update_data(value):
        value = unwrap(value)
        items = value.named_children if value is not None and value.type == 'array' else [value]
        for item in items:
            item = unwrap(item)
            if item is None or item.type != 'object':
                yield item
                continue
            data = [field(x, 'value') for x in item.named_children if x.type == 'pair' and text(field(x, 'key'), source) == 'data']
            yield data[0] if data else item

    def sql_text(node):
        node = unwrap(node)
        if node is None:
            return None
        if node.type == 'template_string':
            return ''.join('?' if part.type == 'template_substitution' else text(part, source)
                           for part in node.named_children)
        if node.type == 'string':
            return string(node)
        if node.type == 'call_expression' and field(node, 'arguments') is not None:
            args = field(node, 'arguments')
            return sql_text(args if args.type == 'template_string' else args.named_children[0] if args.named_children else None)
        return None

    def prisma_call(node, owner, scope):
        callee, args = field(node, 'function'), field(node, 'arguments')
        if callee is None or callee.type != 'member_expression' or args is None:
            return
        method = text(field(callee, 'property'), source)
        receiver = field(callee, 'object')
        base = dict(node=owner, file=rel, function=named_scope(scope), call_line=node.start_point.row + 1)
        if method in RAW_WRITES:
            from .sql import statements
            query = sql_text(args if args.type == 'template_string' else args.named_children[0] if args.named_children else None)
            if query is None:
                out['writes'].append(dict(base, via='sql', statement='?', table=None, schema='', columns=['*'], unclear=True,
                                          receiver=text(receiver, source), reason='SQL text is not a literal', **position(node, source)))
                return
            for row in statements(query):
                if row['verb'] in ('insert', 'update', 'delete'):
                    out['writes'].append(dict(base, via='sql', statement=row['verb'], table=row['table'], schema=row['schema'],
                                              columns=[c['name'] for c in row['columns']] or ['*'], unclear=False,
                                              receiver=text(receiver, source), reason='', **position(node, source)))
            return
        if method in PRISMA_READS and receiver is not None and receiver.type == 'member_expression':
            prisma_query(node, method, receiver, args, base)
            return
        if method not in PRISMA_WRITES or receiver is None or receiver.type != 'member_expression':
            return
        accessor = field(receiver, 'property')
        first = args.named_children[0] if args.named_children else None
        if accessor is None or accessor.type != 'property_identifier' or first is None:
            return
        arg = unwrap(first)
        keys = {text(field(x, 'key'), source): field(x, 'value') for x in arg.named_children if x.type == 'pair'} \
            if arg.type == 'object' else {}
        shorthand = {text(x, source) for x in arg.named_children if x.type == 'shorthand_property_identifier'} if arg.type == 'object' else set()
        if arg.type == 'object' and not (set(keys) | shorthand) & PRISMA_ARGS:
            return                                 # Map.delete(key), cache.update({...}): not a Prisma argument
        if arg.type not in ('object', 'identifier') or arg.type == 'identifier' and method in ('delete', 'deleteMany'):
            return                                 # map.delete(key), set.delete(item)
        base.update(via='prisma', accessor=text(accessor, source), method=method, receiver=text(field(receiver, 'object'), source))
        rows = []
        if arg.type == 'identifier':
            add_write(rows, base, [], 'opaque', arg, 'Prisma argument is not an object literal')
        elif method in ('delete', 'deleteMany'):
            add_write(rows, dict(base, loop=True) if in_loop(node) else base, [], 'delete', node)
        elif method == 'upsert':
            for branch in ('create', 'update'):
                if branch in keys:
                    object_fields(keys[branch], dict(base, branch=branch), [], rows)
                elif branch in shorthand:
                    object_fields(next(x for x in arg.named_children if text(x, source) == branch), dict(base, branch=branch), [], rows)
        elif 'data' in keys:
            object_fields(keys['data'], base, [], rows)
        elif 'data' in shorthand:
            object_fields(next(x for x in arg.named_children if x.type == 'shorthand_property_identifier' and text(x, source) == 'data'),
                          base, [], rows)
        out['writes'].extend(rows)

    def holder_of(node):
        """The object literal (`const service = { m() {} }`) or class a method belongs to; '' otherwise."""
        if node.type != 'method_definition' or node.parent is None:
            return ''
        body = node.parent
        if body.type == 'class_body' and body.parent is not None and field(body.parent, 'name') is not None:
            return text(field(body.parent, 'name'), source)
        holder = body.parent
        while holder is not None and holder.type in WRAPPERS:
            holder = holder.parent
        if body.type == 'object' and holder is not None and holder.type == 'variable_declarator' and field(holder, 'name') is not None:
            return text(field(holder, 'name'), source)
        return ''

    def object_of(value):
        """The object literal an argument is, also through one local `const x = {...}`."""
        value = unwrap(value)
        if value is not None and value.type == 'identifier':
            found, _, _ = local_value(value)
            value = unwrap(found) if found is not None else value
        return value if value is not None and value.type == 'object' else None

    def object_pairs(value):
        found = object_of(value)
        return {} if found is None else {text(field(x, 'key'), source) if field(x, 'key').type == 'property_identifier'
                                         else string(field(x, 'key')): field(x, 'value')
                                         for x in found.named_children if x.type == 'pair'}

    def filter_keys(value, depth=0):
        """Field names a Prisma `where` filters on, through AND/OR/NOT, arrays, spreads and one local const."""
        found = unwrap(value)
        if found is None or depth > 6:
            return set()
        if found.type == 'array':
            return set().union(*(filter_keys(item, depth + 1) for item in found.named_children))
        found = object_of(found)
        keys = set()
        for item in found.named_children if found is not None else ():
            if item.type == 'shorthand_property_identifier':
                keys.add(text(item, source))
            elif item.type == 'spread_element' and item.named_children:
                keys |= filter_keys(item.named_children[0], depth + 1)
            elif item.type == 'pair':
                key = field(item, 'key')
                name = text(key, source) if key.type == 'property_identifier' else string(key)
                if name in LOGIC:
                    keys |= filter_keys(field(item, 'value'), depth + 1)
                elif name:
                    keys.add(name)
        return keys

    def prisma_query(node, method, receiver, args, base):
        """A Prisma read (`count`, `findMany`, ...): the fields its `where` filters on, the relations its
        `include`/`select` load and the relations its `_count` counts."""
        accessor = field(receiver, 'property')
        if accessor is None or accessor.type != 'property_identifier':
            return
        first = args.named_children[0] if args.named_children else None
        pairs = object_pairs(first) if first is not None else {}
        if first is not None and not set(pairs) & QUERY_ARGS or first is None and method not in ('count', 'findMany', 'findFirst'):
            return
        loads, counts = set(), set()
        for part in ('include', 'select'):
            for key, value in object_pairs(pairs.get(part)).items():
                if key != '_count':
                    loads.add(key)
                    continue
                selected = object_pairs(value).get('select')
                counts |= set(object_pairs(selected)) if selected is not None else {'*'}
        counts |= set(object_pairs(object_pairs(pairs.get('_count')).get('select'))) if '_count' in pairs else set()
        out['queries'].append(dict(base, via='prisma', accessor=text(accessor, source), method=method,
                                   receiver=text(field(receiver, 'object'), source), keys=sorted(filter_keys(pairs.get('where'))),
                                   loads=sorted(loads), counts=sorted(counts), **position(node, source)))

    # ---- declared value sets, annotated fields and the values typed objects give them -----------
    def strings(items):
        values = [string(item) for item in items if item.type not in COMMENTS]
        return values if values and all(isinstance(value, str) for value in values) else None

    def declared_set(value):
        """(kind, values, members) of `[...] as const`, `{K: 'v'} as const` or `new Set([...])`."""
        if value is None:
            return None
        if value.type == 'as_expression' and len(value.named_children) == 1 and text(value, source).rstrip().endswith('const'):
            inner = unwrap(value.named_children[0])
            if inner is not None and inner.type == 'array' and (values := strings(inner.named_children)):
                return 'const-array', values, {}
            if inner is not None and inner.type == 'object':
                pairs = [x for x in inner.named_children if x.type not in COMMENTS]
                members = {text(field(x, 'key'), source): string(field(x, 'value')) for x in pairs if x.type == 'pair'}
                if members and len(members) == len(pairs) and all(isinstance(v, str) for v in members.values()):
                    return 'const-object', list(dict.fromkeys(members.values())), members
            return None
        inner = unwrap(value)
        if inner is not None and inner.type == 'new_expression' and text(field(inner, 'constructor'), source) in ('Set', 'ReadonlySet'):
            arguments = field(inner, 'arguments')
            first = unwrap(arguments.named_children[0]) if arguments is not None and arguments.named_children else None
            if first is not None and first.type == 'array' and (values := strings(first.named_children)):
                return 'set', values, {}
        return None

    def type_set(value):
        """A closed union of string literals (null/undefined allowed), or an alias: `(typeof X)[number]`,
        `(typeof X)[keyof typeof X]` or a plain type name; None for anything else."""
        value = value.named_children[0] if value is not None and value.type == 'parenthesized_type' and value.named_children else value
        if value is None:
            return None
        if value.type in ('union_type', 'literal_type'):
            members, stack = [], [value]
            while stack:
                item = stack.pop(0)
                if item.type == 'union_type':
                    stack[:0] = [x for x in item.named_children if x.type not in COMMENTS]
                elif item.type == 'literal_type' and item.named_children and item.named_children[0].type == 'string':
                    members.append(string(item.named_children[0]))
                elif item.type == 'literal_type' and item.named_children and item.named_children[0].type in ('null', 'undefined'):
                    members.append(None)
                else:
                    return None
            return dict(kind='union', values=[m for m in members if m is not None], optional=None in members) \
                if any(isinstance(m, str) for m in members) else None
        if value.type == 'lookup_type' and len(value.named_children) == 2:
            query = value.named_children[0]
            query = query.named_children[0] if query.type == 'parenthesized_type' and query.named_children else query
            if query.type == 'type_query' and query.named_children and query.named_children[0].type == 'identifier':
                return dict(kind='alias', of=text(query.named_children[0], source))
        if value.type == 'type_identifier':
            return dict(kind='alias', of=text(value, source))
        return None

    def container_of(node):
        """The interface, class or object type alias whose own member `node` is."""
        body = node.parent
        holder = body.parent if body is not None else None
        if body is None or holder is None:
            return ''
        if node.type == 'property_signature' and body.type in ('interface_body', 'object_type') \
                and holder.type in ('interface_declaration', 'type_alias_declaration'):
            return text(field(holder, 'name'), source)
        if node.type == 'public_field_definition' and body.type == 'class_body' and holder.type in CLASSES:
            return text(field(holder, 'name'), source)
        return ''

    def typed_field(node, scope):
        container = container_of(node)
        name, annotation = field(node, 'name'), field(node, 'type')
        if not container or name is None or annotation is None or not annotation.named_children:
            return
        declared = type_set(annotation.named_children[0])
        if declared is None:
            return
        nullable = bool(declared.pop('optional', False))
        optional = nullable or any(not child.is_named and child.type == '?' for child in node.children)
        out['typed_fields'].append(dict(container=container, field=text(name, source), file=rel, optional=optional,
                                        **declared, **position(node, source)))

    def typed_object(value, container, owner, scope):
        """The literal values an object typed as `container` (`const x: T = {...}`, `{...} satisfies T`,
        `{...} as T`) gives its fields."""
        found = unwrap(value) if value is not None and value.type != 'satisfies_expression' else value
        found = found.named_children[0] if found is not None and found.type == 'satisfies_expression' and found.named_children else found
        if found is None or found.type != 'object' or not container:
            return
        for item in found.named_children:
            if item.type == 'pair' and field(item, 'key').type == 'property_identifier' and (values := written_of(field(item, 'value'))):
                out['typed_writes'].append(dict(node=owner, function=named_scope(scope), container=container,
                                                field=text(field(item, 'key'), source), file=rel, **values, **position(item, source)))

    def is_exported(node):
        holder = node.parent
        while holder is not None and holder.type in ('lexical_declaration', 'variable_declaration'):
            holder = holder.parent
        return holder is not None and holder.type == 'export_statement'

    def type_name(node):
        """`T` of a type annotation, `satisfies T` or `as T` that names a type; '' otherwise."""
        node = node.named_children[0] if node is not None and node.type == 'type_annotation' and node.named_children else node
        return text(node, source) if node is not None and node.type == 'type_identifier' else ''

    def number_context(node):
        child, parent = node, node.parent
        while parent is not None and (parent.type in WRAPPERS or parent.type == 'unary_expression' and operator(parent) == '-'):
            child, parent = parent, parent.parent
        if parent is None:
            return '', None
        valid, value = literal(node, source)
        if not valid or isinstance(value, bool) or not isinstance(value, (int, float)):
            return '', None
        value = -value if child is not node and text(child, source).lstrip('( ').startswith('-') else value
        if parent.type == 'binary_expression' and operator(parent) in EQUALITY | ORDER:
            return 'compare', value
        if parent.type == 'switch_case' and child == field(parent, 'value'):
            return 'case', value
        return '', None

    # ---- names a decision compares with, and the module tables it looks values up in -----------------
    # A comparison with `LIMIT` or `Kind.ACTIVE` and a lookup `LABELS[type]` are recorded by name here;
    # the map folds them to values (`MapHandle.numbers()`, `literals()`, `lookup_keys()`), also through imports.
    def compared_name(operand, owner, scope):
        operand = unwrap(operand)
        if operand is None or operand.type not in ('identifier', 'member_expression'):
            return
        spelled = text(operand, source)
        parts = spelled.split('.')
        if operand.type == 'member_expression' and (len(parts) != 2 or not all(part.isidentifier() for part in parts)):
            return
        if not any(constant_like(part) for part in parts):
            return
        out['compared_names'].append(dict(node=owner, file=rel, name=spelled, function=named_scope(scope),
                                          **position(operand, source)))

    def const_table(value):
        """{key: literal or None} of a module-level `const NAME = {...}` (also `as const`/`satisfies`)."""
        value = unwrap(value)
        if value is None or value.type != 'object':
            return None
        table = {}
        for pair in value.named_children:
            if pair.type != 'pair':
                continue
            key = field(pair, 'key')
            known, spelled = literal(key, source)
            name = str(spelled) if known else text(key, source) if key is not None and key.type == 'property_identifier' else None
            if name is not None:
                known, item = literal(unwrap(field(pair, 'value')), source)
                table[name] = item if known else None
        return table or None

    def visit(node, scope='', cls='', parameters=(), shadows=frozenset()):
        if node.type in ('import_statement', 'export_statement'):
            imports(node, scope)
        if node.type in FUNCTIONS | CLASSES:
            name = name_of(node)
            qual = scope + ('.' if scope else '') + name
            declared_qual = qual
            if qual in used:
                qual += '@' + str(node.start_point.row + 1)
            used.add(qual)
            is_class = node.type in CLASSES
            params = field(node, 'parameters')
            arg_names = []
            if params:
                for arg in params.named_children:
                    pattern = field(arg, 'pattern') or field(arg, 'name') or arg
                    if pattern.type == 'identifier':
                        arg_names.append(text(pattern, source))
            elif (arg := field(node, 'parameter')) is not None:
                arg_names.append(text(arg, source))
            own_shadows = scoped_names(node) | ((set(parameters) | set(shadows)) - local_functions(node) - {name})
            body = field(node, 'body')
            header = source[node.start_byte:(body.start_byte if body else node.end_byte)].decode('utf-8')
            row = dict(qual=qual, kind=('interface' if node.type == 'interface_declaration' else 'enum' if node.type == 'enum_declaration' else 'class') if is_class else 'method' if cls else 'function',
                       cls=cls, line=node.start_point.row + 1, end=node.end_point.row + 1,
                       sig=header[:160], doc='', fp=fingerprint(node, source, name),
                       shape=[] if name.startswith('<anonymous') or is_class or body is None
                       else kinds_shape(own_kinds(body))[:SHAPE_K],
                       size=node.descendant_count, raw=dict(name=name, scope=scope, declared_qual=declared_qual, parameters=arg_names,
                       shadows=sorted(own_shadows), declaration_kind=node.type, holder=holder_of(node)),
                       column=position(node, source)['column'], end_column=position(node, source)['end_column'])
            out['nodes'].append(row)
            container = node.parent
            while container and container.type in ('variable_declarator','lexical_declaration','variable_declaration','parenthesized_expression'):
                container = container.parent
            if container and container.type == 'export_statement':
                exported = 'default' if 'default' in text(container, source).split()[:3] else name
                out['exports'][exported] = qual
            if not is_class:
                out['bound'].append(name)
            for child in node.named_children:
                if child is not field(node, 'name'):
                    visit(child, qual, qual if is_class else cls, tuple(arg_names), frozenset(own_shadows))
            return
        owner = module + (':' + scope if scope else '')
        if node.type == 'variable_declarator':
            name_node, value = field(node, 'name'), field(node, 'value')
            name = text(name_node, source)
            valid, number = literal(value, source)
            if valid and name.isupper() and name.replace('_','').isalnum():
                qual = scope + ('.' if scope else '') + name
                at = position(node,source)
                out['nodes'].append(dict(qual=qual,kind='const',cls=cls,line=at['line'],end=at['end_line'],
                    column=at['column'],end_column=at['end_column'],sig=text(value,source),doc='',
                    fp=fingerprint(value,source),shape=[],size=0,raw=dict(name=name,scope=scope)))
                out['keys'].append(('constant',name,at['line'],scope))
        if node.type == 'variable_declarator' and not scope and field(node, 'name') is not None \
                and field(node, 'name').type == 'identifier' and (declared := declared_set(field(node, 'value'))):
            kind, values, members = declared
            out['value_sets'].append(dict(name=text(field(node, 'name'), source), kind=kind, values=values, members=members,
                                          file=rel, exported=is_exported(node), **position(node, source)))
        if node.type == 'type_alias_declaration' and not scope and (declared := type_set(field(node, 'value'))):
            out['value_sets'].append(dict(name=text(field(node, 'name'), source), file=rel, exported=is_exported(node),
                                          **declared, **position(node, source)))
        if node.type in ('property_signature', 'public_field_definition'):
            typed_field(node, scope)
        if node.type == 'public_field_definition' and field(node, 'value') is not None and container_of(node) \
                and field(node, 'name') is not None and (values := written_of(field(node, 'value'))):
            out['typed_writes'].append(dict(node=owner, function=named_scope(scope), container=container_of(node),
                                            field=text(field(node, 'name'), source), file=rel, **values, **position(node, source)))
        if node.type == 'variable_declarator' and (container := type_name(field(node, 'type'))):
            typed_object(field(node, 'value'), container, owner, scope)
        if node.type in ('satisfies_expression', 'as_expression') and len(node.named_children) == 2:
            typed_object(node.named_children[0], type_name(node.named_children[1]), owner, scope)
        if node.type == 'assignment_expression' and cls and (left := field(node, 'left')) is not None \
                and left.type == 'member_expression' and field(left, 'object') is not None and field(left, 'object').type == 'this' \
                and (values := written_of(field(node, 'right'))):
            out['typed_writes'].append(dict(node=owner, function=named_scope(scope), container=cls.rpartition('.')[2],
                                            field=text(field(left, 'property'), source), file=rel, **values, **position(node, source)))
        if node.type == 'catch_clause':
            catch(node, owner, scope)
        if node.type == 'binary_expression' and operator(node) in EQUALITY | ORDER:
            for side in ('left', 'right'):
                compared_name(field(node, side), owner, scope)
        elif node.type == 'switch_case' and field(node, 'value') is not None:
            compared_name(field(node, 'value'), owner, scope)
        elif node.type == 'subscript_expression':
            table, index = unwrap(field(node, 'object')), unwrap(field(node, 'index'))
            if table is not None and table.type == 'identifier' and constant_like(text(table, source)) \
                    and index is not None and not literal(index, source)[0]:
                out['table_lookups'].append(dict(node=owner, file=rel, name=text(table, source),
                                                 function=named_scope(scope), **position(node, source)))
        if node.type == 'variable_declarator' and not scope and field(node, 'name') is not None \
                and field(node, 'name').type == 'identifier' and (table := const_table(field(node, 'value'))) is not None:
            out['const_tables'].append(dict(name=text(field(node, 'name'), source), file=rel, values=table,
                                            **position(node, source)))
        if node.type == 'number' and (found := number_context(node))[0]:
            out['numbers'].append(dict(node=owner, file=rel, value=found[1], context=found[0],
                                       function=named_scope(scope), **position(node, source)))
        elif node.type == 'string' and (context := literal_context(node)):
            valid, value = literal(node, source)
            if valid and isinstance(value, str):
                declared = {}
                if context == 'union':          # the type alias a union member belongs to: type X = 'a' | 'b'
                    holder = node.parent
                    while holder is not None and holder.type not in ('type_alias_declaration', 'program'):
                        holder = holder.parent
                    if holder is not None and holder.type == 'type_alias_declaration' and field(holder, 'name') is not None:
                        declared = {'declaration': text(field(holder, 'name'), source)}
                out['literals'].append(dict(node=owner, file=rel, value=value, context=context,
                                            function=named_scope(scope), **declared, **position(node, source)))
        if node.type == 'call_expression':
            prisma_call(node, owner, scope)
        if node.type in ('call_expression', 'new_expression'):
            callee = field(node, 'function') or field(node, 'constructor')
            spelling = text(callee, source)
            args = field(node, 'arguments')
            if spelling in ('require', 'import'):
                first = args.named_children[0] if args and args.named_children else None
                add_dep(node, string(first), kind='dynamic', scope=scope)
            call = dict(node=owner, file=rel, text=spelling, candidate=spelling, scope=scope,
                        parameters=list(parameters), shadows=sorted(shadows), resolved=None,
                        positional_arg_count=len(args.named_children) if args else 0, keyword_count=0,
                        boolop_or_nonfinal=False, **position(node, source))
            if not callee or callee.type != 'identifier' or node.type == 'new_expression':
                call['reason'] = 'member/computed/constructor dispatch requires semantic context'
            elif spelling in parameters or spelling in shadows:
                call['reason'] = 'callee is a parameter or local value; runtime target is unknown'
            if callee and callee.type == 'member_expression':
                obj, prop = field(callee,'object'), field(callee,'property')
                if obj and prop and obj.type == 'identifier' and prop.type == 'property_identifier':
                    call['namespace_candidate'] = [text(obj,source),text(prop,source)]
            out['syntax_calls'].append(call)
        if node.type in ('assignment_expression', 'augmented_assignment_expression', 'update_expression', 'variable_declarator', 'pair', 'public_field_definition'):
            target = field(node, 'left') or field(node, 'argument') or field(node, 'name') or field(node, 'key')
            value = field(node, 'right') or field(node, 'value')
            if target:
                known, val = literal(value, source)
                key = key_of(target)
                if node.type in ('pair', 'public_field_definition'):
                    key = text(target, source) if target.type in ('property_identifier','identifier') else string(target)
                form = ('member' if target.type in ('member_expression', 'subscript_expression') else
                        'pair' if node.type == 'pair' else 'class-field' if node.type == 'public_field_definition' else
                        'declarator' if node.type == 'variable_declarator' else 'identifier')
                out['assignments'].append(dict(node=owner, file=rel, target=text(target, source), field=key or '',
                    value=val, literal=known, operation='write', form=form,
                    binding_mutation=node.type in ('assignment_expression','augmented_assignment_expression','update_expression') and target.type=='identifier', **position(node, source)))
                if key:
                    out['keys'].append(('field', key, node.start_point.row + 1, scope))
        if node.type in ('jsx_self_closing_element','jsx_opening_element'):
            name = text(field(node,'name'),source)
            if name and name[0].isupper():
                out['syntax_calls'].append(dict(node=owner,file=rel,text=name,candidate=name,scope=scope,
                    parameters=list(parameters),resolved=None,kind='jsx-element',
                    reason='JSX element names a component; factory/runtime dispatch is not executed',
                    **position(node,source)))
        if node.type in ('member_expression', 'subscript_expression'):
            parent = node.parent
            written = parent and parent.type == 'assignment_expression' and field(parent, 'left') == node
            if not written:
                key = key_of(node)
                row = dict(node=owner, file=rel, text=text(node, source), field=key or '',
                           kind='read', resolved=None, **position(node, source))
                if key is None:
                    row['reason'] = 'computed property name is unknown'
                out['symbol_reads'].append(row)
                if key:
                    out['keys'].append(('field', key, node.start_point.row + 1, scope))
        for child in node.named_children:
            visit(child, scope, cls, parameters, shadows)

    visit(tree.root_node,shadows=frozenset(scoped_names(tree.root_node)))
    out['bindings'] = [row for row in out['dependencies'] if row.get('alias') and row['kind'] == 'import']
    if b'flowguard:' in data:
        from flowguard.intent.anchors import foreign_owners
        out.update(foreign_owners(source.decode('utf-8'), module, rel, is_test=is_test, functions=out['nodes']))
    return out
