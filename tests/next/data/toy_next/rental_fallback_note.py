# Toy rental shop after request R10 ("repairs only at the main branch"), written the
# over-defensive way. Planted on purpose (the branch check must find each one):
#   P1 FALLBACK ROUTE      repair_anywhere: "if main is busy, repair it where it is"
#   P2 DUPLICATE ROUTE     give_back: a second "return" action identical to return_ok
#   P3 DUPLICATE ROUTE     rent(channel=...): two parameter values that change nothing
#   P4 REDUNDANT ACTION    return_at_main: a special case that return_ok already does
#   P5 SAME-RESULT BRANCH  return_damaged: "if it cannot go to main, still put it in repair"
#   P6 NEVER TAKEN         transfer: a defensive branch for a tool on loan, after the guard
#   P7 DEAD GUARD          rent: a check for an unknown branch that can never fail
from flowguard._next import Model, need

TOOLS = ["T1"]
m = Model("rental R10, fallback that leaves a note")
m.field("cond", ["shop", "loan", "repair"], "shop", over=TOOLS)
m.field("branch", ["main", "library"], "main", over=TOOLS)
m.field("main_busy", [False, True], False)      # the main workshop has no free slot
m.field("note", ["", "repaired away"], "", over=TOOLS)   # the fallback leaves a note


@m.action(t=TOOLS, channel=["desk", "app"])      # P3
def rent(s, t, channel):
    need(s["cond", t] == "shop", "not on the shelf")
    need(s["branch", t] in ("main", "library"), "unknown branch")   # P7
    s["cond", t] = "loan"


@m.action(t=TOOLS)
def return_ok(s, t):
    need(s["cond", t] == "loan", "not out")
    s["cond", t] = "shop"


@m.action(t=TOOLS)
def give_back(s, t):                              # P2
    need(s["cond", t] == "loan", "not out")
    s["cond", t] = "shop"


@m.action(t=TOOLS)
def return_at_main(s, t):                         # P4
    need(s["cond", t] == "loan", "not out")
    need(s["branch", t] == "main", "not at main")
    s["cond", t] = "shop"


@m.action(t=TOOLS)
def return_damaged(s, t):
    need(s["cond", t] == "loan", "not out")
    if s["branch", t] == "main":
        s["cond", t] = "repair"
    else:                                         # P5
        s["cond", t] = "repair"


@m.action(t=TOOLS)
def repaired(s, t):
    need(s["cond", t] == "repair", "not in repair")
    need(s["branch", t] == "main", "R10: repairs only at main")
    need(not s["main_busy"], "main is busy")
    s["cond", t] = "shop"


@m.action(t=TOOLS)
def repair_anywhere(s, t):                        # P1
    need(s["cond", t] == "repair", "not in repair")
    need(s["main_busy"], "main is free: use repaired")
    s["cond", t] = "shop"
    s["note", t] = "repaired away"


@m.action(t=TOOLS)
def transfer(s, t):
    need(s["cond", t] == "shop", "only shelf tools move")
    if s["cond", t] == "loan":                    # P6
        s["cond", t] = "shop"
    s["branch", t] = "library" if s["branch", t] == "main" else "main"


@m.action()
def workshop(s):                                  # the main workshop fills up / frees up
    s["main_busy"] = not s["main_busy"]


m.only_when("repairs only at main", "repaired", lambda s, t: s["branch", t] == "main")
m.progress("back on a shelf", when=lambda s, t: True, goal=lambda s, t: s["cond", t] == "shop", over=TOOLS)
MODEL = m
