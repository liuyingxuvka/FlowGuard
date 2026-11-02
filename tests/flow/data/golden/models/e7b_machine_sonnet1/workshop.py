"""Model of request 10: every repair is done in the workshop at main.

A tool that goes to repair anywhere is taken to main (its branch becomes main), so
`repaired` (allowed only at main) can never get stuck. A repaired tool is in the shop at main.
"""
from machine import Machine, need

TOOLS = ["T1", "T2"]
BRANCHES = ["main", "lib"]
m = Machine("workshop", settings=dict())
m.field("where", ["shop", "loan", "repair", "inspection", "transit"], "shop", over=TOOLS)
m.field("branch", BRANCHES, "main", over=TOOLS)


@m.action(t=TOOLS)
def rent(s, t):
    need(s["where", t] == "shop", "not in the shop")
    s["where", t] = "loan"


@m.action(t=TOOLS)
def return_due_maintenance(s, t):          # regular maintenance: to repair, to main
    need(s["where", t] == "loan", "not on loan")
    s["where", t], s["branch", t] = "repair", "main"


@m.action(t=TOOLS)
def return_due_inspection(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "inspection"


@m.action(t=TOOLS)
def return_damaged(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t], s["branch", t] = "repair", "main"


@m.action(t=TOOLS, r=["pass", "fail"])
def inspected(s, t, r):
    need(s["where", t] == "inspection", "not waiting for inspection")
    if r == "pass":
        s["where", t] = "shop"
    else:
        s["where", t], s["branch", t] = "repair", "main"


@m.action(t=TOOLS, b=BRANCHES)
def transfer(s, t, b):
    need(s["where", t] == "shop", "not available")
    need(s["branch", t] != b, "already there")
    s["where", t], s["branch", t] = "transit", b


@m.action(t=TOOLS)
def receive(s, t):
    need(s["where", t] == "transit", "not in transit")
    s["where", t] = "shop"


@m.action(t=TOOLS)
def repaired(s, t):
    need(s["where", t] == "repair", "not in repair")
    need(s["branch", t] == "main", "repairs are done at main")
    s["where", t] = "shop"


m.option("workshop: repaired", lambda s, t: s["where", t] == "repair" and s["branch", t] == "main",
         action="repaired", t=TOOLS)
m.always("a tool in repair is at main",
         lambda s: all(s["branch", t] == "main" for t in TOOLS if s["where", t] == "repair"))
m.after("a repaired tool is in the shop at main", "repaired",
        lambda b, a, t: a["where", t] == "shop" and a["branch", t] == "main")
m.only_when("repair only at main", "repaired", lambda s, t: s["branch", t] == "main")
m.progress("a tool in repair gets back to the shop", over=TOOLS,
           when=lambda s, t: s["where", t] == "repair", goal=lambda s, t: s["where", t] == "shop")
m.reach("repair of a tool that was away", lambda s: s["where", "T1"] == "repair")
MACHINE = m
