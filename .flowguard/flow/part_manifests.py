"""Each cached part retains its own observed application inputs."""
from flowguard.flow import Model, need

m = Model("part manifests", covers=["flowguard/flow/project.py", "flowguard/flow/jobs.py"])
m.field("phase", ("start", "stored", "edited", "checked"), "start")
m.field("core_inputs", (False, True), False)
m.field("routes_inputs", (False, True), False)
m.field("core_hit", (False, True), False)
m.field("routes_hit", (False, True), False)

@m.action()
def store_core(s):
    need(s["phase"] == "start" and not s["core_inputs"])
    s["core_inputs"] = True

@m.action()
def store_routes(s):
    need(s["phase"] == "start" and s["core_inputs"])
    s["routes_inputs"] = True
    s["phase"] = "stored"
    s["core_hit"] = s["routes_hit"] = True

@m.action()
def edit_core_input(s):
    need(s["phase"] == "stored")
    s["phase"] = "edited"
    s["core_hit"] = False

@m.action()
def check_again(s):
    need(s["phase"] == "edited")
    s["phase"] = "checked"

@m.action()
def next_run(s):
    need(s["phase"] == "checked")
    s["phase"] = "start"
    s["core_inputs"] = s["routes_inputs"] = False
    s["core_hit"] = s["routes_hit"] = False

m.always("another part never erases core dependencies", lambda s: s["phase"] == "start" or s["core_inputs"])
m.always("editing only core leaves routes cached", lambda s: s["phase"] not in ("edited", "checked") or (not s["core_hit"] and s["routes_hit"]))
m.reach("unchanged second check hits both", lambda s: s["phase"] == "stored" and s["core_hit"] and s["routes_hit"])
MODEL = m
