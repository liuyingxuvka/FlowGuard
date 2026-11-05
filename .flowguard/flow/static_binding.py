"""MODEL is an object binding; rebinding a local name never changes that object."""
from flowguard.flow import Model, need

m = Model("static model binding", covers=["flowguard/map/flow_sources.py"])
m.field("phase", ("start", "built", "exported", "rebound", "shown"), "start")
m.field("local", ("none", "first", "other"), "none")
m.field("exported", ("none", "first"), "none")
m.field("first_rule", (False, True), False)
m.field("other_rule", (False, True), False)
m.field("objects_declared", (False, True), False)
m.field("coverage", ("none", "first", "unknown"), "none")
m.field("uncertain", (False, True), False)

@m.action()
def construct(s):
    need(s["phase"] == "start")
    s["local"] = "first"
    s["coverage"] = "first"
    s["phase"] = "built"

@m.action()
def declare_objects(s):
    need(s["phase"] in ("built", "exported") and not s["objects_declared"])
    s["objects_declared"] = True

@m.action()
def dynamic_argument(s):
    need(s["phase"] in ("exported", "rebound") and not s["uncertain"])
    s["uncertain"] = True
    s["coverage"] = "unknown"

@m.action()
def first_rule(s):
    need(s["phase"] in ("built", "exported") and not s["first_rule"])
    s["first_rule"] = True

@m.action()
def export(s):
    need(s["phase"] == "built")
    s["exported"] = s["local"]
    s["phase"] = "exported"

@m.action()
def rebind(s):
    need(s["phase"] == "exported")
    s["local"] = "other"
    s["phase"] = "rebound"

@m.action()
def other_rule(s):
    need(s["phase"] == "rebound" and not s["other_rule"])
    s["other_rule"] = True

@m.action()
def query(s):
    need(s["phase"] in ("exported", "rebound"))
    s["phase"] = "shown"

@m.action()
def next_query(s):
    need(s["phase"] == "shown")
    s["phase"] = "start"
    s["local"] = s["exported"] = "none"
    s["first_rule"] = s["other_rule"] = False
    s["objects_declared"] = s["uncertain"] = False
    s["coverage"] = "none"

m.always("export survives local rebinding", lambda s: s["phase"] not in ("exported", "rebound", "shown") or s["exported"] == "first")
m.reach("both instances have separate rules", lambda s: s["phase"] == "rebound" and s["first_rule"] and s["other_rule"])
m.always("dynamic argument never leaves clean old coverage", lambda s: not s["uncertain"] or s["coverage"] == "unknown")
m.always("ordinary declarations preserve known coverage", lambda s: s["phase"] == "start" or s["uncertain"] or s["coverage"] == "first")
MODEL = m
