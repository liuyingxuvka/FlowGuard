"""Request 10 taken literally: repaired is refused unless the tool is at main.
Repair routing is the existing one: a tool that needs repair stays at the branch
where it is. Expected to show the trap."""
from machine import Machine, need

TOOLS = ["T1", "T2"]
BRANCHES = ["main", "library"]
CONDS = ["shop", "loaned", "inspection", "repair", "transit", "lost"]

m = Machine("workshop, as written")
S = m.settings
m.field("branch", BRANCHES, "main", over=TOOLS)
m.field("cond", CONDS, "shop", over=TOOLS)


def route_to_repair(s, t):
    s["cond", t] = "repair"                   # existing behaviour: repair where it is


@m.action(t=TOOLS)
def rent(s, t):
    need(s["cond", t] == "shop", "not in the shop")
    s["cond", t] = "loaned"


@m.action(t=TOOLS, outcome=["ok", "inspect", "maintenance", "damaged"])
def return_tool(s, t, outcome):
    need(s["cond", t] == "loaned", "not on loan")
    if outcome == "ok":
        s["cond", t] = "shop"
    elif outcome == "inspect":
        s["cond", t] = "inspection"
    else:
        route_to_repair(s, t)


@m.action(t=TOOLS)
def mark_lost(s, t):
    need(s["cond", t] == "loaned", "not on loan")
    s["cond", t] = "lost"


@m.action(t=TOOLS, result=["pass", "maintenance", "fail"])
def inspect(s, t, result):
    need(s["cond", t] == "inspection", "not waiting for inspection")
    if result == "pass":
        s["cond", t] = "shop"
    else:
        route_to_repair(s, t)


@m.action(t=TOOLS, to=BRANCHES)
def transfer(s, t, to):
    need(s["cond", t] == "shop", "only a tool in the shop can be sent")
    need(s["branch", t] != to, "already at that branch")
    s["branch", t], s["cond", t] = to, "transit"


@m.action(t=TOOLS)
def receive(s, t):
    need(s["cond", t] == "transit", "not in transit")
    s["cond", t] = "shop"                     # existing behaviour


@m.action(t=TOOLS)
def repaired(s, t):
    need(s["branch", t] == "main", "tool is not at main")   # the new rule
    need(s["cond", t] == "repair", "tool is not in repair")
    s["cond", t] = "shop"


m.always("a tool in repair is at main (the workshop is the only repair)",
         lambda s: all(s["cond", t] != "repair" or s["branch", t] == "main" for t in TOOLS))
m.only_when("repaired only for a tool at main", "repaired",
            lambda s, t: s["branch", t] == "main")
m.after("repaired puts the tool in the shop at main", "repaired",
        lambda b, a, t: a["cond", t] == "shop" and a["branch", t] == "main")
m.progress("a tool in repair gets repaired", over=TOOLS,
           when=lambda s, t: s["cond", t] == "repair",
           goal=lambda s, t: s["cond", t] != "repair")
m.progress("a tool in transit is received", over=TOOLS,
           when=lambda s, t: s["cond", t] == "transit",
           goal=lambda s, t: s["cond", t] != "transit")
m.terminal("cond", ["lost"])
MACHINE = m
