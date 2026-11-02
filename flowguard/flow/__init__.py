"""The flow-model engine behind `python -m flowguard check` and `show`.

Model files import only these two names: `from flowguard.flow import Model, need`.
"""
from .model import Model, need

__all__ = ["Model", "need"]
