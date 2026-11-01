# The same toy, one route per function: rental_planted.py with P1..P7 removed (the
# fallback, the duplicates, the special case, the same-result branch, the defensive
# branch and the dead guard). The R10 dead end the fallback was hiding is visible again.
from flowguard._next import Model, need

TOOLS = ["T1"]
m = Model("rental R10, one route per function")
m.field("cond", ["shop", "loan", "repair"], "shop", over=TOOLS)
m.field("branch", ["main", "library"], "main", over=TOOLS)
m.field("main_busy", [False, True], False)


@m.action(t=TOOLS)
def rent(s, t):
    need(s["cond", t] == "shop", "not on the shelf")
    s["cond", t] = "loan"


@m.action(t=TOOLS)
def return_ok(s, t):
    need(s["cond", t] == "loan", "not out")
    s["cond", t] = "shop"


@m.action(t=TOOLS)
def return_damaged(s, t):
    need(s["cond", t] == "loan", "not out")
    s["cond", t] = "repair"


@m.action(t=TOOLS)
def repaired(s, t):
    need(s["cond", t] == "repair", "not in repair")
    need(s["branch", t] == "main", "R10: repairs only at main")
    need(not s["main_busy"], "main is busy")
    s["cond", t] = "shop"


@m.action(t=TOOLS)
def transfer(s, t):
    need(s["cond", t] == "shop", "only shelf tools move")
    s["branch", t] = "library" if s["branch", t] == "main" else "main"


@m.action()
def workshop(s):
    s["main_busy"] = not s["main_busy"]


m.only_when("repairs only at main", "repaired", lambda s, t: s["branch", t] == "main")
m.progress("back on a shelf", when=lambda s, t: True, goal=lambda s, t: s["cond", t] == "shop", over=TOOLS)
MODEL = m
