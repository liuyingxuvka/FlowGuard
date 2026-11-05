"""A native drift picture uses current checked facts without another production call."""
from flowguard.flow import Model, need

m = Model("native drift picture", covers=["flowguard/flow/diagram.py", "flowguard/flow/native_picture.py"])
m.field("phase", ("ready", "drawn", "rerun"), "ready")
m.field("receipt", ("unchecked", "current", "missing", "stale"), "unchecked")
m.field("executes_production", (False,), False)

@m.action(receipt=("current", "missing", "stale"))
def show(s, receipt):
    need(s["phase"] == "ready")
    s["receipt"] = receipt
    s["phase"] = "drawn" if receipt == "current" else "rerun"

@m.action()
def next_request(s):
    need(s["phase"] != "ready")
    s["phase"] = "ready"
    s["receipt"] = "unchecked"

m.always("drawing requires current checked native evidence",
         lambda s: s["phase"] != "drawn" or s["receipt"] == "current")
m.always("drawing never executes the production program", lambda s: not s["executes_production"])
m.reach("current evidence is drawable", lambda s: s["phase"] == "drawn")
m.reach("stale evidence asks for a new check", lambda s: s["phase"] == "rerun" and s["receipt"] == "stale")
MODEL = m
