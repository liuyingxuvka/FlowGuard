"""C/C++ source facts, without preprocessing, type inference or project execution."""
from __future__ import annotations

import re
import math
from pathlib import Path

from .common import blank, fingerprint, parse, position, text, walk

CLASSES = {'class_specifier', 'struct_specifier', 'union_specifier'}
NAMES = {'identifier', 'field_identifier', 'type_identifier', 'qualified_identifier',
         'namespace_identifier', 'destructor_name', 'operator_name'}


def _name(node, source):
    while node is not None:
        if node.type in NAMES:
            return text(node, source)
        child = node.child_by_field_name('declarator') or node.child_by_field_name('name')
        if child is None and node.type == 'parenthesized_declarator' and len(node.named_children) == 1:
            child = node.named_children[0]
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


def extract(root: Path, rel: str, data: bytes, module: str, is_test: bool) -> dict:
    suffix = Path(rel).suffix
    language = 'cpp' if suffix == '.C' else 'c' if suffix.lower() in ('.c', '.h') else 'cpp'
    source, tree = parse(data, language)
    facts = blank(module, source, language)
    if tree.root_node.has_error:
        errors = [n for n in walk(tree.root_node) if n.is_error or n.is_missing]
        loc = position(errors[0], source) if errors else dict(line=1, column=1)
        facts['parse_error'] = f'{language} syntax error at {rel}:{loc["line"]}:{loc["column"]}'
    owners, params, local_bindings, classes, names = {}, {}, {}, set(), {}
    all_nodes = list(walk(tree.root_node))
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
            for declarator in node.children_by_field_name('declarator'):
                if declarator.type != 'function_declarator':
                    continue
                target = declarator.child_by_field_name('declarator')
                if target is None or target.type not in NAMES:
                    continue  # A parenthesized function pointer is a variable.
                name = _name(target, source).replace('::', '.')
                if name:
                    add_node(declarator, '.'.join((*scope, name)), 'method' if cls else 'function',
                             cls, text(declarator, source), declaration_only=True)
        for child in node.named_children:
            declarations(child, scope, cls)

    declarations(tree.root_node)
    guarded_names = {n['raw']['declared_qual'].split('.')[-1] for n in facts['nodes']
                     if n['raw']['requires_build_context']}

    def owner(node):
        while node is not None:
            if node.id in owners:
                return owners[node.id]
            node = node.parent
        return ''

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
    return facts
