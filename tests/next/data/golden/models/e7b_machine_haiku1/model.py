"""One tool's life in the counter, with regular maintenance (request 9) and one workshop (request 10).

The rules this model covers:
- rentals_since_maintenance counts the rentals of the tool since its last repair. A rental
  adds one; any repair (however it came about) sets it back to 0.
- After a normal return, a tool whose count has reached maintain_every goes to repair, not to
  the shop, and nobody is charged for that. A damaged return or a loss is as before.
- Inspections (the existing feature): after inspect_every rentals a normal return goes to
  inspection; a passed inspection puts the tool in the shop and clears the inspection count.
  The maintenance is checked first: a tool due for maintenance goes to repair, not inspection.
  As before, every repair also clears the inspection count.
- A renewal is not a rental; it changes no count, so it is not modelled.
- A lost tool is never repaired or inspected again, so its counts are reset (they no longer
  matter); the counter itself keeps them for its queries.
- Request 10: every repair is done at the main branch. `repaired` is refused anywhere else.
  A tool in repair at another branch is sent to main (transfer), and it arrives in repair,
  not in the shop. Any other tool is sent as before (only from the shelf). Only two branches
  are modelled: main, and "other" (any other branch; the rules only tell main apart).
"""
from machine import Machine, need

m = Machine("tool life with maintenance and one workshop",
            settings=dict(maintain_every=4, inspect_every=5))
S = m.settings   # read here, not copied: --set changes these values after the file is loaded
T = ["T"]        # one tool
BRANCHES = ["main", "other"]


def maint_due(s, t):
    return S["maintain_every"] > 0 and s["rentals", t] >= S["maintain_every"]


def insp_due(s, t):
    return S["inspect_every"] > 0 and s["checked", t] >= S["inspect_every"]


# Domains wide enough for every value --set may try (the counts are capped at the setting).
m.field("where", ["shop", "loan", "repair", "inspection", "lost", "transit"], "shop", over=T)
m.field("rentals", range(0, 9), 0, over=T)   # rentals since the last repair
m.field("checked", range(0, 11), 0, over=T)  # rentals since the last inspection
m.field("branch", BRANCHES, "main", over=T)  # the branch the tool is at (or travelling to)
m.field("arrival", ["shop", "repair"], "shop", over=T)  # what a tool in transit becomes on arrival


@m.action(t=T)
def rent(s, t):
    need(s["where", t] == "shop", "not on the shelf")
    s["where", t] = "loan"
    s["rentals", t] = min(s["rentals", t] + 1, S["maintain_every"])
    s["checked", t] = min(s["checked", t] + 1, S["inspect_every"])


@m.action(t=T)
def return_ok(s, t):
    need(s["where", t] == "loan", "not on loan")
    if maint_due(s, t):
        s["where", t] = "repair"
    elif insp_due(s, t):
        s["where", t] = "inspection"
    else:
        s["where", t] = "shop"


@m.action(t=T)
def return_damaged(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "repair"


@m.action(t=T)
def mark_lost(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "lost"
    s["rentals", t] = 0
    s["checked", t] = 0


@m.action(t=T)
def repaired(s, t):
    need(s["where", t] == "repair", "not in repair")
    need(s["branch", t] == "main", "not at main")
    s["where", t] = "shop"
    s["rentals", t] = 0
    s["checked", t] = 0


@m.action(t=T)
def inspect_pass(s, t):
    need(s["where", t] == "inspection", "not waiting for inspection")
    s["where", t] = "shop"
    s["checked", t] = 0


@m.action(t=T)
def inspect_fail(s, t):
    need(s["where", t] == "inspection", "not waiting for inspection")
    s["where", t] = "repair"
    s["checked", t] = 0


@m.action(t=T, to=BRANCHES)
def transfer(s, t, to):
    need(to != s["branch", t], "already at that branch")
    need(s["where", t] == "shop" or (s["where", t] == "repair" and to == "main"),
         "only an available tool can be sent, or a tool in repair to main")
    s["arrival", t] = "repair" if s["where", t] == "repair" else "shop"
    s["branch", t] = to
    s["where", t] = "transit"


@m.action(t=T)
def receive(s, t):
    need(s["where", t] == "transit", "not in transit")
    s["where", t] = s["arrival", t]
    s["arrival", t] = "shop"


m.terminal("where", ["lost"])

# A tool due for maintenance is never on the shelf, and never rented before it.
m.always("a tool due for maintenance is never on the shelf",
         lambda s: all(not (s["where", t] == "shop" and maint_due(s, t)) for t in T))
m.only_when("a tool is rented only when no maintenance is due", "rent",
            lambda s, t: not maint_due(s, t))
m.after("a normal return due for maintenance goes to repair", "return_ok",
        lambda b, a, t: a["where", t] == "repair" if maint_due(b, t) else True)
m.after("a normal return due for inspection (and not maintenance) goes to inspection",
        "return_ok",
        lambda b, a, t: (a["where", t] == "inspection"
                         if insp_due(b, t) and not maint_due(b, t) else True))
m.after("a rental counts once", "rent",
        lambda b, a, t: a["rentals", t] == min(b["rentals", t] + 1, S["maintain_every"]))
m.after("a repair starts the count again from 0", "repaired",
        lambda b, a, t: a["rentals", t] == 0)
m.after("a passed inspection does not clear the rental count", "inspect_pass",
        lambda b, a, t: a["rentals", t] == b["rentals", t])

# Request 10: one workshop, at main.
m.only_when("a repair is recorded only at main", "repaired",
            lambda s, t: s["branch", t] == "main")
m.only_when("a tool in repair is only sent to main", "transfer",
            lambda s, t, to: s["where", t] != "repair" or to == "main")
m.after("a sent tool is at its new branch, in transit", "transfer",
        lambda b, a, t, to: a["branch", t] == to and a["where", t] == "transit")
m.after("a tool sent for repair arrives in repair, not in the shop", "receive",
        lambda b, a, t: a["where", t] == b["arrival", t])
m.after("a repaired tool is back in the shop at main", "repaired",
        lambda b, a, t: a["where", t] == "shop" and a["branch", t] == "main")

m.progress("a tool that is not lost always gets back to the shelf", over=T,
           when=lambda s, t: s["where", t] != "lost",
           goal=lambda s, t: s["where", t] == "shop")
m.progress("a tool in repair is repaired at main", over=T,
           when=lambda s, t: s["where", t] == "repair",
           goal=lambda s, t: s["where", t] == "shop" and s["branch", t] == "main")
m.reach("a tool waits in repair for its maintenance",
        lambda s: any(s["where", t] == "repair" and maint_due(s, t) for t in T))
m.reach("a tool at another branch is sent to main for repair",
        lambda s: any(s["where", t] == "transit" and s["arrival", t] == "repair"
                      and s["branch", t] == "main" for t in T))

MACHINE = m
