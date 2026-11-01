from machine import Machine, need
T = ["T1", "T2"]
import os   # MV="4,5" env var picks (maintain_every, inspect_every) for the runs in DESIGN.md
_mv = [int(x) for x in os.environ.get("MV", "2,3").split(",")]
m = Machine("maintenance", settings=dict(maintain_every=_mv[0], inspect_every=_mv[1]))
S = m.settings
M, I = S["maintain_every"], S["inspect_every"]
m.field("where", ["shop", "loan", "repair", "inspection", "lost"], "shop", over=T)
m.field("since_m", range(0, M + 1), 0, over=T)   # rentals since last repair
m.field("since_i", range(0, I + 1), 0, over=T)   # rentals since inspection/repair
m.field("charged", [0, 1], 0, over=T)            # last return charged the member
m.field("renewed", [0, 1], 0, over=T)

@m.action(t=T)
def rent(s, t):
    need(s["where", t] == "shop", "not available")
    s["where", t] = "loan"
    s["since_m", t] = min(s["since_m", t] + 1, M)
    s["since_i", t] = min(s["since_i", t] + 1, I)
    s["charged", t] = 0

@m.action(t=T)
def renew(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["renewed", t] = 1          # must not change counts

@m.action(t=T)
def return_tool(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["renewed", t] = 0
    if M > 0 and s["since_m", t] >= M:
        s["where", t] = "repair"           # maintenance wins over inspection
    elif I > 0 and s["since_i", t] >= I:
        s["where", t] = "inspection"
    else:
        s["where", t] = "shop"

@m.action(t=T)
def return_damaged(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "repair"; s["charged", t] = 1; s["renewed", t] = 0

@m.action(t=T)
def mark_lost(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "lost"; s["charged", t] = 1

@m.action(t=T)
def repaired(s, t):
    need(s["where", t] == "repair", "not in repair")
    s["where", t] = "shop"; s["since_m", t] = 0; s["since_i", t] = 0

@m.action(t=T)
def inspected_pass(s, t):
    need(s["where", t] == "inspection", "not waiting")
    s["where", t] = "shop"; s["since_i", t] = 0   # since_m untouched

@m.action(t=T)
def inspected_fail(s, t):
    need(s["where", t] == "inspection", "not waiting")
    s["where", t] = "repair"; s["since_i", t] = 0

m.option("rent", lambda s, t: s["where", t] == "shop", action="rent", t=T)
m.option("repaired", lambda s, t: s["where", t] == "repair", action="repaired", t=T)
m.always("never more than maintain_every rentals without maintenance",
         lambda s: all(s["since_m", t] <= M for t in T))
m.only_when("rent only if maintenance not due", "rent",
            lambda s, t: M == 0 or s["since_m", t] < M)
m.after("Mth normal return goes to repair uncharged", "return_tool",
        lambda b, a, t: not (M > 0 and b["since_m", t] >= M) or (a["where", t] == "repair" and a["charged", t] == 0))
m.after("renew changes no count", "renew",
        lambda b, a, t: b["since_m", t] == a["since_m", t])
m.after("repair resets count", "repaired", lambda b, a, t: a["since_m", t] == 0)
m.progress("tool in repair/inspection gets back", over=T,
           when=lambda s, t: s["where", t] in ("repair", "inspection"),
           goal=lambda s, t: s["where", t] == "shop")
m.reach("maintenance without charge", lambda s: any(s["where", t] == "repair" and s["since_m", t] >= M and s["charged", t] == 0 for t in T))
MACHINE = m
