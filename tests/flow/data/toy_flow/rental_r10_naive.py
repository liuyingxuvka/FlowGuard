# Toy model of the rental shop after request R10 ("repairs only at the main branch"),
# naive design: nothing else changes.
from flowguard.flow import Model, need

TOOLS = ["T1"]
m = Model("rental R10 naive")
m.field("cond", ["shop", "loan", "repair"], "shop", over=TOOLS)
m.field("branch", ["main", "library"], "main", over=TOOLS)

@m.action(t=TOOLS)
def rent(s, t):
    need(s["cond", t] == "shop", "not on the shelf"); s["cond", t] = "loan"

@m.action(t=TOOLS)
def return_ok(s, t):
    need(s["cond", t] == "loan", "not out"); s["cond", t] = "shop"

@m.action(t=TOOLS)
def return_damaged(s, t):
    need(s["cond", t] == "loan", "not out"); s["cond", t] = "repair"

@m.action(t=TOOLS)
def repaired(s, t):
    need(s["cond", t] == "repair", "not in repair")
    need(s["branch", t] == "main", "R10: repairs only at main")
    s["cond", t] = "shop"

@m.action(t=TOOLS)
def transfer(s, t):
    need(s["cond", t] == "shop", "only shelf tools move")
    s["branch", t] = "library" if s["branch", t] == "main" else "main"

m.progress("back on a shelf", when=lambda s, t: True, goal=lambda s, t: s["cond", t] == "shop", over=TOOLS)
MODEL = m
