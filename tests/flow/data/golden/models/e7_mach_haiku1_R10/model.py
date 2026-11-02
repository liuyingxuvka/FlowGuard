"""Proposal for Request 10: one workshop at main.

Same as as_written.py, with one change to repair routing: a tool that needs repair
at a branch other than main is sent to main (in transit, with a flag that its
arrival is a repair, not a return to the shop). A tool in repair is then always
at main, so `repaired` can always be done. Receive puts it in repair at main.
"""
from machine import Machine, need

TOOLS = ["T1", "T2"]
BRANCHES = ["main", "library"]
CONDS = ["shop", "loaned", "inspection", "repair", "transit", "lost"]

m = Machine("workshop, proposal")
S = m.settings
m.field("branch", BRANCHES, "main", over=TOOLS)
m.field("cond", CONDS, "shop", over=TOOLS)
m.field("arrive_repair", range(0, 2), 0, over=TOOLS)   # transit ends in repair, not in the shop


def route_to_repair(s, t):
    if s["branch", t] == "main":
        s["cond", t] = "repair"
    else:                                     # the workshop is at main: send it there
        s["branch", t], s["cond", t], s["arrive_repair", t] = "main", "transit", 1


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
    s["cond", t] = "repair" if s["arrive_repair", t] else "shop"
    s["arrive_repair", t] = 0


@m.action(t=TOOLS)
def repaired(s, t):
    need(s["branch", t] == "main", "tool is not at main")
    need(s["cond", t] == "repair", "tool is not in repair")
    s["cond", t] = "shop"


m.always("a tool in repair is at main",
         lambda s: all(s["cond", t] != "repair" or s["branch", t] == "main" for t in TOOLS))
m.always("only a tool in transit has the repair flag",
         lambda s: all(s["arrive_repair", t] == 0 or s["cond", t] == "transit" for t in TOOLS))
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
