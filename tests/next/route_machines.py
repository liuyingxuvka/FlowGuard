"""Prototype (`machine` API) model files loaded for the route check, the way the
prototype's branch check loads them: golden_machine records the declarations (the test
supplies the name `machine`), and the model file is compiled with the route check's
if-forcing transform."""
from __future__ import annotations

import ast
import os
import sys
import types
from pathlib import Path

import golden_machine
from flowguard._next.model import validate
from flowguard._next.routes import ForceIfs


def load_forced_machines(path, drop_rules=False):
    """(models, ifs): every Machine of the file as a Model, and the wrapped ifs."""
    path = Path(path).resolve()
    force = ForceIfs(path)
    tree = ast.fix_missing_locations(force(ast.parse(path.read_text(encoding="utf-8"), str(path))))
    code = compile(tree, str(path), "exec")
    module = types.ModuleType("model_under_test")
    module.__file__ = str(path)
    sys.modules["machine"] = golden_machine
    folder = str(path.parent)
    old_cwd = os.getcwd()
    sys.path.insert(0, folder)
    os.chdir(folder)
    try:
        exec(code, module.__dict__)
    finally:
        os.chdir(old_cwd)
        sys.path.remove(folder)
        sys.modules.pop("machine", None)
    machines = list(module.MACHINES) if hasattr(module, "MACHINES") else [module.MACHINE]
    out = []
    for n, mach in enumerate(machines):
        model = mach.to_model(drop_rules=drop_rules)
        model.id = path.stem if len(machines) == 1 else f"{path.stem}_{n + 1}"
        model.path = path
        model.root = path.parent
        validate(model)
        out.append(model)
    return out, force.ifs
