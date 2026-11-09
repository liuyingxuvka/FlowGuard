"""Small file-fact vocabulary shared by grammar readers, stored by the existing Map."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import importlib
from importlib.metadata import version

GRAMMARS = {
    'javascript': ('tree_sitter_javascript', 'tree-sitter-javascript', 'language'),
    'typescript': ('tree_sitter_typescript', 'tree-sitter-typescript', 'language_typescript'),
    'tsx': ('tree_sitter_typescript', 'tree-sitter-typescript', 'language_tsx'),
    'c': ('tree_sitter_c', 'tree-sitter-c', 'language'),
    'cpp': ('tree_sitter_cpp', 'tree-sitter-cpp', 'language'),
    'csharp': ('tree_sitter_c_sharp', 'tree-sitter-c-sharp', 'language'),
}


@lru_cache(maxsize=None)
def parser(language):
    from flowguard.map.common import MapError
    binding = version('tree-sitter')
    if not binding.startswith('0.25.'):
        raise MapError(f'tree-sitter {binding} is outside the packaged compatible range; install FlowGuard dependencies (0.25.2 <= binding < 0.26)')
    from tree_sitter import Language, Parser
    module, distribution, entry = GRAMMARS[language]
    grammar = importlib.import_module(module)
    return Parser(Language(getattr(grammar, entry)()))


def parse(data, language):
    # Normalize through the same source text convention; offsets below refer to
    # decoded source characters, never pretending UTF-8 bytes are columns.
    from flowguard.map.common import normalize_newlines
    source = normalize_newlines(data).decode('utf-8-sig').encode('utf-8')
    tree = parser(language).parse(source)
    return source, tree


def walk(node):
    yield node
    for child in node.named_children:
        yield from walk(child)


def text(node, source):
    return source[node.start_byte:node.end_byte].decode('utf-8') if node is not None else ''


def position(node, source):
    prefix = source[:node.start_byte].rsplit(b'\n', 1)[-1]
    return dict(line=node.start_point.row + 1, column=len(prefix.decode('utf-8')) + 1,
                end_line=node.end_point.row + 1,
                end_column=len(source[:node.end_byte].rsplit(b'\n', 1)[-1].decode('utf-8')) + 1)


def fingerprint(node, source, name=''):
    parts = []
    stack = [node]
    while stack:
        item = stack.pop()
        if item.type in ('comment', 'line_comment', 'block_comment'):
            continue
        if item.children:
            stack.extend(reversed(item.children))
        else:
            value = text(item, source)
            parts.append((item.type, '<self>' if value == name and name else value))
    return hashlib.sha256(repr(parts).encode('utf-8')).hexdigest()[:20]


def blank(module, data, language, parser=None):
    """Empty facts of one file; `parser` describes a reader that is not a tree-sitter grammar."""
    from flowguard.map.common import normalize_newlines
    if parser is None:
        parser = dict(engine='tree-sitter', version=version('tree-sitter'), grammar=GRAMMARS[language][1],
                      grammar_version=version(GRAMMARS[language][1]))
    return dict(module=module, language=language, parser=parser,
                loc=len(data.splitlines()), source_lines=len(data.splitlines()), parse_error='',
                imports=[], import_lines={}, import_reads={}, literal_dynamic_imports={},
                unknown_dynamic_imports=[], lazy={}, bound=[], nodes=[], syspath=[], keys=[],
                facts={}, optional=[], star=False, getattr=False, submodules=False,
                dependencies=[], syntax_calls=[], assignments=[], symbol_reads=[],
                handlers=[], literal_sets=[], writes=[], literals=[], locations={}, module_fp=hashlib.sha256(normalize_newlines(data).removeprefix(b'\xef\xbb\xbf')).hexdigest()[:20])
