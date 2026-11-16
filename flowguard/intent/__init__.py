"""One executable decision, its literal regressions, and its real code homes."""
from .api import D, IntentError, Refused, row, rule, states, flow, Node, Read, Relation

__all__ = ["D", "IntentError", "Refused", "row", "rule", "states", "flow", "Node", "Read", "Relation"]


def __getattr__(name):
    """A name 5.0 removed raises IntentError with what to do instead (`api.REMOVED`)."""
    from . import api
    if name in api.REMOVED:
        raise api.IntentError(api.removed(name))
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
