"""C/C++ source facts, without preprocessing, type inference or project execution."""
from __future__ import annotations

import re
import math
from pathlib import Path

from .common import blank, fingerprint, parse, parser, position, text, walk

CLASSES = {'class_specifier', 'struct_specifier', 'union_specifier'}
NAMES = {'identifier', 'field_identifier', 'type_identifier', 'qualified_identifier',
         'namespace_identifier', 'destructor_name', 'operator_name'}


def _declarator_child(node):
    child = node.child_by_field_name('declarator') or node.child_by_field_name('name')
    # C++ reference_declarator has an unnamed child in the packaged grammar.
    if child is None and node.type in {'reference_declarator', 'parenthesized_declarator'}:
        children = [n for n in node.named_children if n.type != 'comment']
        child = children[0] if len(children) == 1 else None
    return child


def _name(node, source):
    while node is not None:
        if node.type in NAMES:
            return text(node, source)
        child = _declarator_child(node)
        if child is None:
            return ''
        node = child
    return ''


def _literal(node, source):
    if node is None:
        return None, False
    value = text(node, source)
    if value in ('true', 'false', 'nullptr', 'NULL'):
        return {'true': True, 'false': False, 'nullptr': None, 'NULL': None}[value], True
    if node.type == 'string_literal' and value.startswith('"') and value.endswith('"') and '\\' not in value:
        return value[1:-1], True
    number = re.sub(r'[uUlL]+$', '', value)
    if re.fullmatch(r'[+-]?0[xX][0-9a-fA-F]+', number):
        return int(number, 16), True
    if re.fullmatch(r'0[0-7]+', number):
        return int(number, 8), True
    if re.fullmatch(r'[+-]?\d+', number):
        return int(number), True
    number = re.sub(r'[fFlL]$', '', value)
    if re.fullmatch(r'[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|[+-]?\d+[eE][+-]?\d+', number):
        value = float(number)
        return (value, True) if math.isfinite(value) else (None, False)
    return None, False


def _conditional(node):
    while node is not None:
        if node.type.startswith(('preproc_if', 'preproc_elif', 'preproc_else')):
            return True
        node = node.parent
    return False


def _syntax_errors(node):
    """Missing punctuation is not necessarily named, but is still an error."""
    if node.is_error or node.is_missing:
        yield node
    for child in node.children:
        if child.has_error or child.is_error or child.is_missing:
            yield from _syntax_errors(child)


def _prior_bindings(declaration, source):
    """Only lexical names before this declaration; no execution or type inference."""
    known = {}
    def collect(node, local):
        if node.type in CLASSES or node.type == 'enum_specifier':
            name = text(node.child_by_field_name('name'), source)
            if name:
                local.setdefault(name, set()).add('type')
        elif node.type in {'type_definition', 'alias_declaration'}:
            names = node.children_by_field_name('declarator') or [node.child_by_field_name('name')]
            for target in names:
                if target is not None and (name := _name(target, source)):
                    local.setdefault(name, set()).add('type')
        elif node.type in {'declaration', 'field_declaration', 'function_definition'}:
            type_node = node.child_by_field_name('type')
            if type_node is not None:
                collect(type_node, local)
                for target in node.children_by_field_name('declarator'):
                    if name := _name(target, source):
                        local.setdefault(name, set()).add('value')
    child, parent = declaration, declaration.parent
    while parent is not None:
        local = {}
        if parent.type in {'translation_unit', 'declaration_list', 'compound_statement', 'field_declaration_list'}:
            for sibling in parent.named_children:
                if sibling.start_byte >= child.start_byte:
                    break
                collect(sibling, local)
        if parent.type in CLASSES:
            collect(parent, local)
        if parent.type == 'function_definition':
            declarator = parent.child_by_field_name('declarator')
            for parameter in walk(declarator) if declarator is not None else ():
                if parameter.type in {'parameter_declaration', 'optional_parameter_declaration'}:
                    target = parameter.child_by_field_name('declarator')
                    if target is not None and (name := _name(target, source)):
                        local.setdefault(name, set()).add('value')
        for name, kinds in local.items():
            known.setdefault(name, kinds)  # The nearest lexical scope wins.
        child, parent = parent, parent.parent
    return known


def _reference_initializers(root, source):
    """Disambiguate one known C++ grammar gap from the original source ranges.

    tree-sitter-cpp 0.23.4 (and upstream c0092228) reads reference initializers
    such as a conditional or ``*this`` as erroneous function parameter lists.
    C++ init-declarator syntax permits ``T& name(expression);``. Decode that
    shape only with a complete parenthesized-expression parse; syntax-valid
    type/value ambiguities additionally need an earlier lexical binding. Unknown
    names stay explicitly unclassified. Require the parenthesized
    expression plus its real semicolon to parse completely. No source is edited,
    and an error outside that exact initializer suffix remains an error.
    """
    from tree_sitter import Parser, Range
    found, unknown = {}, {}
    for declaration in walk(root):
        if declaration.type != 'declaration':
            continue
        declarators = declaration.children_by_field_name('declarator')
        if len(declarators) != 1 or declarators[0].type not in {'reference_declarator', 'pointer_declarator'}:
            continue
        reference = declarators[0]
        function = _declarator_child(reference)
        if function is None or function.type != 'function_declarator':
            continue
        name = function.child_by_field_name('declarator')
        parameters = function.child_by_field_name('parameters')
        type_node = declaration.child_by_field_name('type')
        semicolon = declaration.children[-1]
        if (name is None or name.type != 'identifier' or name.has_error
                or parameters is None
                or type_node is None or type_node.has_error
                or semicolon.type != ';' or semicolon.is_missing):
            continue
        errors = list(_syntax_errors(declaration))
        if any(n.start_byte < name.end_byte or n.end_byte > semicolon.start_byte for n in errors):
            continue
        # included_ranges preserves original bytes, rows and byte offsets. The
        # fragment is already a parenthesized-expression statement in the file;
        # no artificial declaration, replacement operator or wrapper is inserted.
        expression_parser = Parser(parser('cpp').language)
        expression_parser.included_ranges = [Range(name.end_point, declaration.end_point,
                                                    name.end_byte, declaration.end_byte)]
        tree = expression_parser.parse(source)
        statements = [n for n in tree.root_node.named_children if n.type != 'comment']
        if tree.root_node.has_error or len(statements) != 1 or statements[0].type != 'expression_statement':
            continue
        expressions = [n for n in statements[0].named_children if n.type != 'comment']
        if len(expressions) != 1 or expressions[0].type != 'parenthesized_expression':
            continue
        expression = expressions[0]
        if not errors:
            # With no grammar error, (Type) can be a parameter list and (value)
            # an initializer. Resolve only names explicitly bound in this scope;
            # included/unknown names need semantic context, not a guessed function.
            known = _prior_bindings(declaration, source)
            roles = []
            for parameter in parameters.named_children:
                if parameter.type == 'comment':
                    continue
                type_node = parameter.child_by_field_name('type')
                if type_node is not None and type_node.type in {'primitive_type', 'sized_type_specifier', 'decltype'}:
                    roles.append({'type'})
                else:
                    roles.append(known.get(text(type_node, source), set()))
            if roles and all(role == {'type'} for role in roles):
                continue
            if not roles or not all(role == {'value'} for role in roles):
                unknown[declaration.id] = dict(name=text(name, source),
                    reason='declarator requires type/value context', **position(declaration, source))
                continue
        found[declaration.id] = dict(declaration=declaration, reference=reference,
                                      declarator=function, name=text(name, source), tree=tree,
                                      expression=expression, errors={n.id for n in errors})
    return found, unknown


def _declared_function(declarator, source):
    """The first declarator operator outward from the name determines its kind.

    ``T* f()`` is a function returning a pointer; ``T (*f)()`` is a pointer
    variable. Parentheses group these operators rather than changing that rule.
    Following declarator fields also covers references and function factories,
    without interpreting parameter types or treating a callback as a function.
    """
    operators, node = [], declarator
    while node is not None and node.type not in NAMES:
        if node.type != 'parenthesized_declarator':
            operators.append(node.type)
        node = _declarator_child(node)
    return text(node, source) if node is not None and operators and operators[-1] == 'function_declarator' else ''


def extract(root: Path, rel: str, data: bytes, module: str, is_test: bool) -> dict:
    suffix = Path(rel).suffix
    language = 'cpp' if suffix == '.C' else 'c' if suffix.lower() in ('.c', '.h') else 'cpp'
    source, tree = parse(data, language)
    facts = blank(module, source, language)
    initializers, binding_unknowns = _reference_initializers(tree.root_node, source) if language == 'cpp' else ({}, {})
    covered = {identifier for item in initializers.values() for identifier in item['errors']}
    original_errors = list(_syntax_errors(tree.root_node))
    errors = [n for n in original_errors if n.id not in covered]
    if errors or tree.root_node.has_error and not original_errors:
        loc = position(errors[0], source) if errors else dict(line=1, column=1)
        facts['parse_error'] = f'{language} syntax error at {rel}:{loc["line"]}:{loc["column"]}'
    if language == 'cpp':
        facts['parser']['syntax_recovery'] = 'reference/pointer direct-initialization from original ranges'
        facts['binding_unknowns'] = list(binding_unknowns.values())
        facts['syntax_recoveries'] = [dict(kind=('reference' if item['reference'].type == 'reference_declarator' else 'pointer') + '-direct-initialization',
                                          **position(item['declaration'], source))
                                      for item in initializers.values()]
    owners, params, local_bindings, classes, names = {}, {}, {}, set(), {}
    def syntax_walk(node):
        yield node
        recovery = initializers.get(node.id)
        for child in node.named_children:
            if recovery and child.id == recovery['reference'].id:
                yield from walk(recovery['expression'])
            elif recovery and child.start_byte >= recovery['declarator'].child_by_field_name('declarator').end_byte:
                continue  # The verified fragment owns the entire original initializer suffix.
            else:
                yield from syntax_walk(child)
    all_nodes = list(syntax_walk(tree.root_node))
    macros = {text(n.child_by_field_name('name'), source) for n in all_nodes
              if n.type in ('preproc_def', 'preproc_function_def')}

    def add_node(node, qual, kind, cls='', sig='', declaration_only=False):
        loc = position(node, source)
        # A declaration's own signature distinguishes overloads; source line
        # only disambiguates genuinely repeated definitions with that signature.
        base = qual
        if qual in names:
            qual += '@' + re.sub(r'\s+', '', sig)
            if qual in names:
                qual += f'@L{loc["line"]}'
        names[qual] = node
        facts['nodes'].append(dict(qual=qual, kind=kind, cls=cls, line=loc['line'],
                                   end=loc['end_line'], column=loc['column'], end_column=loc['end_column'],
                                   sig=sig, doc='', fp=fingerprint(node, source, base.split('.')[-1]),
                                   shape=[], size=len(list(walk(node))), raw={'declared_qual': base,
                                       'declaration_only': declaration_only,
                                       'requires_build_context': _conditional(node)}))
        owners[node.id] = qual
        return qual

    def declarations(node, scope=(), cls=''):
        if node.type == 'namespace_definition':
            name = text(node.child_by_field_name('name'), source)
            if name:
                scope += tuple(name.replace('::', '.').split('.'))
        elif node.type in CLASSES and node.child_by_field_name('body') is not None:
            name = text(node.child_by_field_name('name'), source)
            if name:
                qual = '.'.join((*scope, name))
                cls = add_node(node, qual, 'class')
                classes.add(qual)
                scope += (name,)
        elif node.type == 'function_definition':
            declarator = node.child_by_field_name('declarator')
            name = _name(declarator, source).replace('::', '.')
            if name:
                qual = '.'.join((*scope, name))
                parent = qual.rpartition('.')[0]
                fn_cls = cls or (parent if parent in classes else '')
                sig = text(declarator, source)
                qual = add_node(node, qual, 'method' if fn_cls else 'function', fn_cls, sig)
                arguments = [n for n in walk(declarator) if n.type in ('parameter_declaration', 'optional_parameter_declaration')]
                params[qual] = [name for n in arguments if (name := _name(n.child_by_field_name('declarator'), source))]
                body = node.child_by_field_name('body')
                local_bindings[qual] = {_name(n.child_by_field_name('declarator'), source)
                                        for n in walk(body) if n.type in ('init_declarator', 'declaration')} if body else set()
                scope += (name,)
        elif node.type in ('declaration', 'field_declaration'):
            for declarator in node.children_by_field_name('declarator') if node.id not in initializers and node.id not in binding_unknowns else ():
                name = _declared_function(declarator, source).replace('::', '.')
                if name:
                    add_node(declarator, '.'.join((*scope, name)), 'method' if cls else 'function',
                             cls, text(declarator, source), declaration_only=True)
        for child in node.named_children:
            declarations(child, scope, cls)

    declarations(tree.root_node)
    guarded_names = {n['raw']['declared_qual'].split('.')[-1] for n in facts['nodes']
                     if n['raw']['requires_build_context']}

    recovered_owners = {}
    def owner(node):
        if node.id in recovered_owners:
            return recovered_owners[node.id]
        while node is not None:
            if node.id in owners:
                return owners[node.id]
            node = node.parent
        return ''

    for item in initializers.values():
        scope = owner(item['declaration'])
        recovered_owners.update((node.id, scope) for node in walk(item['expression']))
        local_bindings.setdefault(scope, set()).add(item['name'])

    def fact(node, **values):
        loc = position(node, source)
        qual = owner(node)
        return dict(node=module + (':' + qual if qual else ''), file=rel, **loc, **values)

    for node in all_nodes:
        qual = owner(node)
        if node.type == 'preproc_include':
            value = node.child_by_field_name('path')
            spelling = text(value, source)
            quoted = spelling.startswith('"') and spelling.endswith('"')
            loc = position(node, source)
            facts['dependencies'].append(dict(module=spelling[1:-1] if spelling[:1] in ('"', '<') else spelling,
                name='', alias='', kind='include', line=loc['line'], column=loc['column'], scope=qual,
                relative=quoted, reason='' if quoted else 'system or computed include needs build context'))
        elif node.type in ('preproc_def', 'preproc_function_def'):
            name = text(node.child_by_field_name('name'), source)
            if name:
                facts['keys'].append(('constant', name, node.start_point.row + 1, qual))
        elif node.type in ('using_declaration', 'namespace_alias_definition'):
            facts['dependencies'].append(dict(module=text(node, source), name='', alias='', kind='using',
                line=node.start_point.row + 1, column=position(node, source)['column'], scope=qual,
                relative=False, reason='namespace/using declaration requires C++ name resolution'))
        elif node.type == 'call_expression':
            callee = node.child_by_field_name('function')
            spelling = text(callee, source)
            candidate = spelling.replace('::', '.')
            reason = ''
            if spelling in macros:
                reason = 'macro call requires preprocessing'
            elif spelling.split('::')[-1] in guarded_names:
                reason = 'conditional declaration requires preprocessing/build context'
            elif spelling in set(params.get(qual, ())) | local_bindings.get(qual, set()):
                reason = 'parameter or local callable requires type/runtime binding'
            elif callee is None or callee.type not in ('identifier', 'qualified_identifier'):
                reason = 'member, indirect or template call requires type/build context'
            facts['syntax_calls'].append(fact(node, text=spelling, resolved=None, candidate=candidate,
                scope=qual, parameters=params.get(qual, []), reason=reason))
        elif node.type in ('assignment_expression', 'update_expression', 'init_declarator'):
            left = node.child_by_field_name('left') or node.child_by_field_name('argument') or node.child_by_field_name('declarator')
            right = node.child_by_field_name('right') or node.child_by_field_name('value')
            target = text(left, source)
            field = left.child_by_field_name('field') if left is not None else None
            field_name = text(field, source) if field is not None else _name(left, source)
            value, literal = _literal(right, source)
            operator = text(node.child_by_field_name('operator'), source)
            facts['assignments'].append(fact(node, target=target, field=field_name or target,
                value=value, literal=literal, operation='update' if node.type == 'update_expression' or operator not in ('', '=') else 'write'))
            if field_name:
                facts['keys'].append(('field', field_name, node.start_point.row + 1, qual))
        elif node.type == 'field_expression':
            field = text(node.child_by_field_name('field'), source)
            parent = node.parent
            simple_write = (parent is not None and parent.type == 'assignment_expression'
                            and parent.child_by_field_name('left') == node
                            and text(parent.child_by_field_name('operator'), source) == '=')
            if not simple_write:
                facts['symbol_reads'].append(fact(node, text=text(node, source), kind='read', resolved=None))
            if field:
                facts['keys'].append(('field', field, node.start_point.row + 1, qual))
        elif node.type == 'identifier':
            parent = node.parent
            if parent is not None and parent.type not in ('function_declarator', 'parameter_declaration',
                                                         'init_declarator', 'preproc_def', 'preproc_function_def'):
                facts['symbol_reads'].append(fact(node, text=text(node, source), kind='read', resolved=None))
        elif node.type == 'string_literal':
            value, literal = _literal(node, source)
            if literal:
                facts['keys'].append(('constant', value, node.start_point.row + 1, qual))
    for item in initializers.values():
        # The initializer is an expression, not a nested function declaration.
        # Its value needs type/evaluation context; expose the write without a
        # guessed value while the real initializer calls/reads above retain scope.
        write = fact(item['declarator'], target=item['name'], field=item['name'],
                     value=None, literal=False, operation='write')
        end = position(item['expression'], source)
        write.update(end_line=end['end_line'], end_column=end['end_column'])
        facts['assignments'].append(write)
    return facts
