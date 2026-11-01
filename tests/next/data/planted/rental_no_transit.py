"""Planted: a removed transition. The fixed design with the transit branch taken out again:
`receive` can never happen."""
from flowguard._next import Model, need

m = Model("rental R10 without transit")
TOOLS = m.objects("tool", "T1")
m.field("cond", ["shop", "loan", "repair", "transit"], "shop", over=TOOLS, source="R4")
m.field("branch", ["main", "library"], "main", over=TOOLS, source="R6")


@m.action(t=TOOLS, source="R4")
def rent(s, t):
    need(s["cond", t] == "shop", "not on the shelf")
    s["cond", t] = "loan"


@m.action(t=TOOLS, source="R4")
def return_ok(s, t):
    need(s["cond", t] == "loan", "not out")
    s["cond", t] = "shop"


@m.action(t=TOOLS, source="R8")
def return_damaged(s, t):
    need(s["cond", t] == "loan", "not out")
    s["cond", t] = "repair"


@m.action(t=TOOLS, source="R10")
def receive(s, t):
    need(s["cond", t] == "transit", "not on the way")
    s["branch", t], s["cond", t] = "main", "repair"


@m.action(t=TOOLS, source="R8")
def repaired(s, t):
    need(s["cond", t] == "repair", "not in repair")
    need(s["branch", t] == "main", "repairs only at main", source="R10")
    s["cond", t] = "shop"


@m.action(t=TOOLS, source="R6")
def transfer(s, t):
    need(s["cond", t] == "shop", "only shelf tools move")
    s["branch", t] = "library" if s["branch", t] == "main" else "main"


m.progress("back on a shelf", when=lambda s, t: True, goal=lambda s, t: s["cond", t] == "shop", over=TOOLS,
           source="R8")
MODEL = m
