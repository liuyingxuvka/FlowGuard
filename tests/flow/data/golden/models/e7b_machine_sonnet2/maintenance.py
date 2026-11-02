"""Model of regular maintenance: the tool's life with the rental count since its last repair."""
from machine import Machine, need

TOOLS = ["T1", "T2"]
m = Machine("maintenance", settings=dict(maintain_every=4))
S = m.settings
TOP = max(S["maintain_every"], 1)
m.field("where", ["shop", "loan", "repair", "lost"], "shop", over=TOOLS)
m.field("count", range(0, TOP + 1), 0, over=TOOLS)      # rentals since the last repair
m.field("charged", [False, True], False, over=TOOLS)    # last return charged a repair fee
m.field("renewed", [False, True], False, over=TOOLS)
m.terminal("where", ["lost"])


@m.action(t=TOOLS)
def rent(s, t):
    need(s["where", t] == "shop", "not in the shop")
    s["where", t] = "loan"
    s["count", t] = min(s["count", t] + 1, TOP)
    s["charged", t] = False


@m.action(t=TOOLS)
def renew(s, t):                       # not a rental: count unchanged
    need(s["where", t] == "loan", "not on loan")
    s["renewed", t] = True


@m.action(t=TOOLS)
def return_tool(s, t):
    need(s["where", t] == "loan", "not on loan")
    due = S["maintain_every"] > 0 and s["count", t] >= S["maintain_every"]
    s["where", t] = "repair" if due else "shop"


@m.action(t=TOOLS)
def return_damaged(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "repair"
    s["charged", t] = True


@m.action(t=TOOLS)
def mark_lost(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "lost"


@m.action(t=TOOLS)
def repaired(s, t):
    need(s["where", t] == "repair", "not in repair")
    s["where", t], s["count", t], s["charged", t] = "shop", 0, False


m.option("rent", lambda s, t: s["where", t] == "shop", action="rent", t=TOOLS)
m.option("return", lambda s, t: s["where", t] == "loan", action="return_tool", t=TOOLS)
m.option("repaired", lambda s, t: s["where", t] == "repair", action="repaired", t=TOOLS)

m.always("a tool due for maintenance is never rentable",
         lambda s: all(not (S["maintain_every"] and s["count", t] >= S["maintain_every"]
                            and s["where", t] == "shop") for t in TOOLS))
m.after("a normal return at the Nth rental goes to repair", "return_tool",
        lambda b, a, t: (S["maintain_every"] == 0 or b["count", t] < S["maintain_every"]
                         or a["where", t] == "repair"))
m.after("a normal return is never charged", "return_tool", lambda b, a, t: not a["charged", t])
m.after("a repair restarts the count", "repaired", lambda b, a, t: a["count", t] == 0)
m.after("a renewal keeps the count", "renew", lambda b, a, t: a["count", t] == b["count", t])
m.after("a damaged return stays damaged", "return_damaged",
        lambda b, a, t: a["where", t] == "repair" and a["charged", t])
m.progress("a tool in repair is back in the shop", over=TOOLS,
           when=lambda s, t: s["where", t] == "repair", goal=lambda s, t: s["where", t] == "shop")
MACHINE = m
