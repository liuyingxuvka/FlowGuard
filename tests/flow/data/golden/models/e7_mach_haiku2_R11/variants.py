"""Variants of design/model.py used to check the open questions in DESIGN.md.

Run:  python tools/machine.py design/variants.py
  - "screen as worded": the item screen offers `bring` whenever the tool is held for
    the member at another branch than the session's, even while it is on the way (the
    literal wording of REQUEST.md). The design refuses bring on the way, so this must
    show a CONTRADICTION.
"""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "model", os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.py"))
model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(model)


def worded_screen():
    m = model.build(naive=False)
    # Replace the bring option: offered wherever the wording says, not only on the shelf.
    m.options = [o for o in m.options if o[0] != "bring"]
    m.option("bring",
             lambda s, who, b: (s["screen"] == "item" and s["hold"] == who
                                and s["branch"] != b),
             action="bring", who=["M1"], b=[model.SESSION])
    m.name = "request 11, design, screen offers bring as worded"
    return m


def window(days):
    m = model.build(naive=False, hold_days=days)
    m.name = f"request 11, design, hold_days={days}"
    return m


MACHINES = [worded_screen(), window(1), window(3)]
