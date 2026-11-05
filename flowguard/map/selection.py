"""Shared static call-graph reachability and model selection for map consumers."""
from __future__ import annotations
from collections import defaultdict

def reachable_functions(edges, start):
    """Operation-local transitive calls; no retained reachability index."""
    pending, found = [start], set()
    while pending:
        node = pending.pop()
        if node not in found:
            found.add(node)
            pending.extend(edges.get(node, ()))
    return found

def anchor_matches(anchor, function):
    """A primary function/class anchor includes its nested symbols."""
    path, _, symbol = anchor.partition(':')
    file, _, name = function.partition('#')
    return path == file and (name == symbol or name.startswith(symbol+'.'))
