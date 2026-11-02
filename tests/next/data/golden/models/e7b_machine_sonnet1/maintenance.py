"""Model of a tool's life with regular maintenance (request 9) and the existing inspection."""
from machine import Machine, need

TOOLS = ["T1", "T2"]
m = Machine("tool maintenance", settings=dict(maintain_every=4, inspect_every=5))
S = m.settings
m.field("where", ["shop", "loan", "repair", "inspection", "lost"], "shop", over=TOOLS)
m.field("since_repair", range(0, S["maintain_every"] + 1), 0, over=TOOLS)   # rentals since last repair
m.field("since_insp", range(0, S["inspect_every"] + 1), 0, over=TOOLS)
m.field("charged", [False, True], False, over=TOOLS)   # last return charged the member for repair


@m.action(t=TOOLS)
def rent(s, t):
    need(s["where", t] == "shop", "not in the shop")
    s["where", t] = "loan"
    s["since_repair", t] = min(s["since_repair", t] + 1, S["maintain_every"])
    s["since_insp", t] = min(s["since_insp", t] + 1, S["inspect_every"])


@m.action(t=TOOLS)
def return_tool(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["charged", t] = False
    due_m = S["maintain_every"] > 0 and s["since_repair", t] >= S["maintain_every"]
    due_i = S["inspect_every"] > 0 and s["since_insp", t] >= S["inspect_every"]
    s["where", t] = "repair" if due_m else "inspection" if due_i else "shop"


@m.action(t=TOOLS)
def return_damaged(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "repair"
    s["charged", t] = True


@m.action(t=TOOLS)
def mark_lost(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "lost"


@m.action(t=TOOLS, r=["pass", "fail"])
def inspected(s, t, r):
    need(s["where", t] == "inspection", "not waiting for inspection")
    s["since_insp", t] = 0
    s["where", t] = "shop" if r == "pass" else "repair"


@m.action(t=TOOLS)
def repaired(s, t):
    need(s["where", t] == "repair", "not in repair")
    s["where", t] = "shop"
    s["since_repair", t] = 0
    s["since_insp", t] = 0
    s["charged", t] = False


m.option("rent", lambda s, t: s["where", t] == "shop", action="rent", t=TOOLS)
m.option("repaired", lambda s, t: s["where", t] == "repair", action="repaired", t=TOOLS)
m.terminal("where", ["lost"])

m.only_when("no rental of a tool due maintenance", "rent",
            lambda s, t: S["maintain_every"] == 0 or s["since_repair", t] < S["maintain_every"])
m.after("every repair restarts the count", "repaired",
        lambda b, a, t: a["since_repair", t] == 0)
m.after("a normal return at the Nth rental goes to repair, uncharged", "return_tool",
        lambda b, a, t: not (b["since_repair", t] >= S["maintain_every"] > 0)
        or (a["where", t] == "repair" and not a["charged", t]))
m.after("damaged return is charged", "return_damaged", lambda b, a, t: a["charged", t])
m.progress("a tool in repair gets back to the shop", over=TOOLS,
           when=lambda s, t: s["where", t] == "repair", goal=lambda s, t: s["where", t] == "shop")
m.progress("a tool waiting for inspection leaves it", over=TOOLS,
           when=lambda s, t: s["where", t] == "inspection", goal=lambda s, t: s["where", t] == "shop")
m.reach("maintenance happens", lambda s: s["where", "T1"] == "repair" and not s["charged", "T1"])
MACHINE = m
