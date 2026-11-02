"""The prototype's `machine` API, supplied by the golden test itself.

Nothing named `machine` ships in the package: the test registers this module as
sys.modules["machine"], so the E7 model files (`from machine import Machine, need`) load
unchanged. It records the prototype's declarations and converts them to a new-engine
Model with literal settings and plain lists; `need` is the engine's.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from flowguard.flow.model import Model, need, validate  # noqa: F401  (need is re-exported)

__all__ = ["Machine", "need", "load_machines"]


class Machine:
    def __init__(self, name, settings=None, variations=None, valid=None):
        self.name = name
        self.settings = dict(settings or {})
        self.variations = dict(variations or {})
        self.valid = valid
        self.fields = []        # (name, domain, init, over)
        self.actions = []       # (name, params, domains, fn)
        self.options = []       # (name, params, domains, offered, action): variants.py edits it
        self.rules = []
        self.terminals = {}

    def field(self, name, domain, init, over=None):
        self.fields.append((name, tuple(domain), init, None if over is None else list(over)))

    def action(self, **params):
        def register(fn):
            self.actions.append((fn.__name__, tuple(params), tuple(tuple(v) for v in params.values()), fn))
            return fn
        return register

    def option(self, name, offered, action=None, **params):
        self.options.append((name, tuple(params), tuple(tuple(v) for v in params.values()), offered,
                             action or name))

    def terminal(self, name, values):
        self.terminals[name] = tuple(values)

    def always(self, name, pred):
        self.rules.append(("always", name, pred))

    def only_when(self, name, action, pred):
        self.rules.append(("only_when", name, action, pred))

    def after(self, name, action, pred):
        self.rules.append(("after", name, action, pred))

    def progress(self, name, when, goal, over=None):
        self.rules.append(("progress", name, when, goal, over))

    def reach(self, name, pred, over=None):
        self.rules.append(("reach", name, pred, over))

    def to_model(self, drop_rules=False) -> Model:
        m = Model(self.name, valid=self.valid)
        m._settings = self.settings           # the prototype's live dict its actions read (the test's
                                              # adapter only: model code never replaces m.settings)
        for k, v in list(self.settings.items()):
            m.setting(k, v, vary=self.variations.get(k))
        for name, domain, init, over in self.fields:
            m.field(name, domain, init, over=over)
        for name, params, domains, fn in self.actions:
            m.action(**dict(zip(params, domains)))(fn)
        for name, params, domains, offered, action in self.options:
            m.option(name, offered, action=action, **dict(zip(params, domains)))
        for fam, values in self.terminals.items():
            m.terminal(fam, values)
        if not drop_rules:
            for r in self.rules:
                kind = r[0]
                if kind == "always":
                    m.always(r[1], r[2])
                elif kind in ("only_when", "after"):
                    getattr(m, kind)(r[1], r[2], r[3])
                elif kind == "progress":
                    m.progress(r[1], r[2], r[3], over=r[4])
                else:
                    m.reach(r[1], r[2], over=r[3])
        return m


def load_machines(path, drop_rules=False) -> list[Model]:
    """Load a prototype model file the way machine.py does (from its own folder) and
    convert every Machine it defines."""
    path = Path(path).resolve()
    sys.modules["machine"] = sys.modules[__name__]
    folder = str(path.parent)
    old_cwd = os.getcwd()
    sys.path.insert(0, folder)
    os.chdir(folder)
    try:
        spec = importlib.util.spec_from_file_location("model_under_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        os.chdir(old_cwd)
        sys.path.remove(folder)
        sys.modules.pop("machine", None)
        sys.modules.pop("model_under_test", None)
    machines = list(module.MACHINES) if hasattr(module, "MACHINES") else [module.MACHINE]
    out = []
    for n, mach in enumerate(machines):
        model = mach.to_model(drop_rules=drop_rules)
        model.id = path.stem if len(machines) == 1 else f"{path.stem}_{n + 1}"
        model.path = path
        model.root = path.parent
        validate(model)
        out.append(model)
    return out
