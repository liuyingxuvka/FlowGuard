"""JS/TS syntax facts. Lexical declarations are facts; runtime dispatch stays unknown."""
from __future__ import annotations
import ast
from .common import blank, parse, text, position, fingerprint

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


def extract(root, rel, data, module, is_test):
    from .registry import language_for
    language = language_for(rel)
    out = blank(module, data, language)
    source, tree = parse(data, language)
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
                       sig=header[:160], doc='', fp=fingerprint(node, source, name), shape=[],
                       size=node.descendant_count, raw=dict(name=name, scope=scope, declared_qual=declared_qual, parameters=arg_names,
                       shadows=sorted(own_shadows), declaration_kind=node.type),
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
                out['assignments'].append(dict(node=owner, file=rel, target=text(target, source), field=key or '',
                    value=val, literal=known, operation='write',
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
    return out
