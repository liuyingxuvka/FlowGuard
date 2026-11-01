"""A tool is retired after its third repair (the declared end of its life)."""
from flowguard._next import Model, need

m = Model("tool life")
TOOLS = m.objects("tool", "T1", "T2")
m.field("cond", ["shop", "loan", "repair", "retired"], "shop", over=TOOLS, source="R4")
m.field("repairs", range(0, 4), 0, over=TOOLS, source="R12")
m.terminal("cond", ["retired"], source="R12")


@m.action(t=TOOLS, source="R4")
def rent(s, t):
    need(s["cond", t] == "shop", "not on the shelf")
    s["cond", t] = "loan"


@m.action(t=TOOLS, source="R4")
def give_back(s, t):
    need(s["cond", t] == "loan", "not on loan")
    s["cond", t] = "repair"


@m.action(t=TOOLS, source="R9")
def repaired(s, t):
    need(s["cond", t] == "repair", "not in repair")
    need(s["repairs", t] < 3, "worn out: retire it")
    s["cond", t], s["repairs", t] = "shop", s["repairs", t] + 1


@m.action(t=TOOLS, source="R12")
def retire(s, t):
    need(s["cond", t] == "repair", "not in repair")
    need(s["repairs", t] == 3, "not worn out yet")
    s["cond", t] = "retired"


MODEL = m
