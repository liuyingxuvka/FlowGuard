"""Next flow-model engine (slice S1a; not in the wheel until it passes its gate).

Model files import only these two names: `from flowguard._next import Model, need`.
"""
from .model import Model, need

__all__ = ["Model", "need"]
