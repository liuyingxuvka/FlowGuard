"""e7_mach_sonnet1_R10/model.py in the new API, the two tools declared interchangeable."""
from flowguard.flow import Model, need
# to_main_on_repair: 0 = literal request, 1 = a tool entering repair is moved to main
m = Model("workshop")
S = m.settings
m.setting("to_main_on_repair", 0)
TOOLS = m.objects("tool", "T1", "T2")
m.field("cond", ["shop", "loan", "repair", "transit", "inspection", "lost"], "shop", over=TOOLS)
m.field("branch", ["main", "east"], "main", over=TOOLS)


def to_repair(s, t):
    s["cond", t] = "repair"
    if S["to_main_on_repair"]:
        s["branch", t] = "main"


@m.action(t=TOOLS)
def rent(s, t):
    need(s["cond", t] == "shop", "not available")
    s["cond", t] = "loan"


@m.action(t=TOOLS)
def return_ok(s, t):
    need(s["cond", t] == "loan", "not on loan")
    s["cond", t] = "shop"


@m.action(t=TOOLS)
def return_inspect(s, t):
    need(s["cond", t] == "loan", "not on loan")
    s["cond", t] = "inspection"


@m.action(t=TOOLS)
def return_maintenance(s, t):
    need(s["cond", t] == "loan", "not on loan")
    to_repair(s, t)


@m.action(t=TOOLS)
def return_damaged(s, t):
    need(s["cond", t] == "loan", "not on loan")
    to_repair(s, t)


@m.action(t=TOOLS)
def mark_lost(s, t):
    need(s["cond", t] == "loan", "not on loan")
    s["cond", t] = "lost"


@m.action(t=TOOLS)
def inspect_pass(s, t):
    need(s["cond", t] == "inspection", "no")
    s["cond", t] = "shop"


@m.action(t=TOOLS)
def inspect_fail(s, t):
    need(s["cond", t] == "inspection", "no")
    to_repair(s, t)


@m.action(t=TOOLS, b=["main", "east"])
def transfer(s, t, b):
    need(s["cond", t] == "shop", "only available")
    need(s["branch", t] != b, "same")
    s["branch", t] = b
    s["cond", t] = "transit"


@m.action(t=TOOLS)
def receive(s, t):
    need(s["cond", t] == "transit", "no")
    s["cond", t] = "shop"


@m.action(t=TOOLS)
def repaired(s, t):
    need(s["cond", t] == "repair", "not in repair")
    need(s["branch", t] == "main", "workshop is at main")
    s["cond", t] = "shop"


@m.action(t=TOOLS)
def restart(s, t):   # keeps the model alive: a lost tool is replaced
    need(s["cond", t] == "lost", "no")
    s["cond", t] = "shop"


m.option("workshop: repaired", lambda s, t: s["cond", t] == "repair" and s["branch", t] == "main",
         action="repaired", t=TOOLS)
m.always("workshop sees every tool in repair",
         lambda s: all(s["branch", t] == "main" for t in TOOLS if s["cond", t] == "repair"))
m.progress("a tool in repair can come back", over=TOOLS,
           when=lambda s, t: s["cond", t] == "repair", goal=lambda s, t: s["cond", t] != "repair")
m.after("repaired lands at main shop", "repaired",
        lambda b, a, t: a["cond", t] == "shop" and a["branch", t] == "main")
MODEL = m
