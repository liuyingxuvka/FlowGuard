"""Each cached part retains its own observed application inputs."""
from flowguard.flow import Model, need

m = Model("part manifests", covers=["flowguard/flow/project.py", "flowguard/flow/jobs.py", "flowguard/flow/worker.py:Worker.run"])
m.field("phase", ("start", "stored", "edited", "checked"), "start")
m.field("core_inputs", (False, True), False)
m.field("routes_inputs", (False, True), False)
m.field("core_hit", (False, True), False)
m.field("routes_hit", (False, True), False)
m.field("recipe", ("ordinary", "incremental", "full"), "ordinary")
m.field("status_seen", (False,True), False)
m.field("diagnostic_seen", (False,True), False)
m.field("ledger", (False,True), True)
m.field("history_anchor", (True,), True)
m.field("decision_reference", (True,), True)
m.field("restored", (False,True), False)

@m.action(recipe=("ordinary", "incremental", "full"))
def store_core(s, recipe):
    need(s["phase"] == "start" and not s["core_inputs"])
    s["core_inputs"] = True
    s["recipe"] = recipe

@m.action()
def store_routes(s):
    need(s["phase"] == "start" and s["core_inputs"])
    s["routes_inputs"] = True
    s["phase"] = "stored"
    s["core_hit"] = s["routes_hit"] = True

@m.action()
def forget_record(s):
    need(s["phase"] == "stored")
    s["ledger"] = False

@m.action()
def explicit_restore(s):
    need(s["phase"] == "stored" and not s["ledger"])
    s["ledger"] = True
    s["restored"] = True

@m.action()
def status_current(s):
    need(s["phase"] == "stored")
    s["status_seen"] = True

@m.action()
def unchanged_full_diagnostic(s):
    need(s["phase"] == "stored")
    s["diagnostic_seen"] = True

@m.action()
def edit_core_input(s):
    need(s["phase"] == "stored")
    s["phase"] = "edited"
    s["core_hit"] = False

@m.action()
def check_again(s):
    need(s["phase"] == "edited")
    s["phase"] = "checked"
    s["ledger"] = True

@m.action()
def next_run(s):
    need(s["phase"] == "checked")
    s["phase"] = "start"
    s["core_inputs"] = s["routes_inputs"] = False
    s["core_hit"] = s["routes_hit"] = False
    s["recipe"] = "ordinary"
    s["ledger"] = True
    s["status_seen"] = s["diagnostic_seen"] = False
    s["restored"] = False

m.always("another part never erases core dependencies", lambda s: s["phase"] == "start" or s["core_inputs"])
m.always("editing only core leaves routes cached", lambda s: s["phase"] not in ("edited", "checked") or (not s["core_hit"] and s["routes_hit"]))
m.reach("unchanged second check hits both", lambda s: s["phase"] == "stored" and s["core_hit"] and s["routes_hit"])
m.after("status preserves the current actual recipe", "status_current", lambda before,after:
        after["recipe"] == before["recipe"] and after["core_hit"] == before["core_hit"])
m.after("unchanged full diagnostics preserve current input identity", "unchanged_full_diagnostic", lambda before,after:
        after["core_inputs"] == before["core_inputs"] and after["core_hit"] == before["core_hit"])
m.reach("status reuses incremental evidence", lambda s:s["status_seen"] and s["recipe"]=="incremental")
m.reach("full diagnostics can preserve an incremental record", lambda s:s["diagnostic_seen"] and s["recipe"]=="incremental")
m.after("unchanged cached status does not recreate an absent record", "status_current", lambda before,after:
        after["ledger"] == before["ledger"])
m.reach("current inputs can remain unrecorded without rerunning", lambda s:
        s["phase"]=="stored" and not s["ledger"] and s["status_seen"] and s["core_hit"] and s["routes_hit"])
m.after("explicit restoration preserves actual historical anchors", "explicit_restore", lambda before,after:
        after["history_anchor"] == before["history_anchor"] and after["decision_reference"] == before["decision_reference"])
m.reach("explicit restoration keeps historical decision references", lambda s:
        s["ledger"] and s["restored"] and s["status_seen"] and s["history_anchor"] and s["decision_reference"])
MODEL = m
