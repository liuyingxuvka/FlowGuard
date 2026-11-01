"""Model of the single workshop: every repair happens at the main branch."""
from machine import Machine, need

TOOLS = ["T1", "T2"]
m = Machine("workshop", settings=dict(move_to_main=1))
S = m.settings
m.field("where", ["shop", "loan", "repair", "lost"], "shop", over=TOOLS)
m.field("branch", ["main", "library"], "main", over=TOOLS)
m.terminal("where", ["lost"])


def to_repair(s, t):
    s["where", t] = "repair"
    if S["move_to_main"]:               # the tool is carried to the workshop
        s["branch", t] = "main"


@m.action(t=TOOLS)
def rent(s, t):
    need(s["where", t] == "shop", "not in the shop")
    s["where", t] = "loan"


@m.action(t=TOOLS)
def return_tool(s, t):                  # normal return
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "shop"


@m.action(t=TOOLS)
def return_due_or_damaged(s, t):        # maintenance due, damage
    need(s["where", t] == "loan", "not on loan")
    to_repair(s, t)


@m.action(t=TOOLS)
def mark_lost(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "lost"


@m.action(t=TOOLS)
def transfer(s, t):                     # only a tool in the shop moves between branches
    need(s["where", t] == "shop", "not in the shop")
    s["branch", t] = "library" if s["branch", t] == "main" else "main"


@m.action(t=TOOLS)
def repaired(s, t):
    need(s["where", t] == "repair", "not in repair")
    need(s["branch", t] == "main", "the workshop is at main")
    s["where", t] = "shop"


m.option("repaired", lambda s, t: s["where", t] == "repair", action="repaired", t=TOOLS)
m.always("a tool in repair is at main", lambda s: all(
    s["where", t] != "repair" or s["branch", t] == "main" for t in TOOLS))
m.only_when("repaired only at main", "repaired", lambda s, t: s["branch", t] == "main")
m.after("a repaired tool is in the shop at main", "repaired",
        lambda b, a, t: a["where", t] == "shop" and a["branch", t] == "main")
m.progress("a tool in repair is back in the shop", over=TOOLS,
           when=lambda s, t: s["where", t] == "repair", goal=lambda s, t: s["where", t] == "shop")
MACHINE = m
