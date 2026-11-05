"""The flow-model engine behind `python -m flowguard check` and `show`.

Simple model files start with `from flowguard.flow import Model, need`.
Composition uses the existing `flowguard.flow.compose` owner.
"""
from .model import Model, need

__all__ = ["Model", "need"]
