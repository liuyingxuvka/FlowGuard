"""Model of 'bring': a held tool is carried to another branch for the member it is held for."""
from machine import Machine, need

TOOLS = ["T1", "T2"]
MEMBERS = ["M1", "M2"]
BRANCHES = ["main", "library"]
m = Machine("bring", settings=dict(hold_days=2, guard_transit=1))
S = m.settings
m.field("where", ["shop", "loan", "transit"], "shop", over=TOOLS)
m.field("holder", [None] + MEMBERS, None, over=TOOLS)       # tool is held for this member
m.field("waiting", [None] + MEMBERS, None, over=TOOLS)      # one member queued behind
m.field("branch", BRANCHES, "main", over=TOOLS)
m.field("age", range(0, S["hold_days"]), 0, over=TOOLS)     # days the hold has run on the shelf


def free(s, t):
    """Tool is on the shelf again: hold it for whoever waits."""
    s["where", t] = "shop"
    s["holder", t], s["waiting", t], s["age", t] = s["waiting", t], None, 0


@m.action(t=TOOLS, mem=MEMBERS)
def rent(s, t, mem):
    need(s["where", t] == "shop", "not on the shelf")      # also refuses in transit
    need(s["holder", t] in (None, mem), "held for another")
    s["where", t], s["holder", t], s["age", t] = "loan", None, 0


@m.action(t=TOOLS)
def return_tool(s, t):
    need(s["where", t] == "loan", "not on loan")
    free(s, t)


@m.action(t=TOOLS, mem=MEMBERS)
def reserve(s, t, mem):
    need(s["where", t] == "loan" or s["holder", t] is not None, "not reservable")
    need(s["holder", t] != mem and s["waiting", t] is None, "already / queue full")
    s["waiting", t] = mem


@m.action(t=TOOLS)
def transfer(s, t):
    need(s["where", t] == "shop" and s["holder", t] is None, "not available")
    s["where", t] = "transit"
    s["branch", t] = "library" if s["branch", t] == "main" else "main"


@m.action(t=TOOLS, mem=MEMBERS, b=BRANCHES)
def bring(s, t, mem, b):
    need(s["where", t] == "shop" and s["holder", t] == mem, "not held for this member")
    need(b != s["branch", t], "already there")
    s["where", t], s["branch", t], s["age", t] = "transit", b, 0


@m.action(t=TOOLS)
def receive(s, t):
    need(s["where", t] == "transit", "not in transit")
    if s["holder", t] is not None:              # same member, the pick-up clock starts again
        s["where", t], s["age", t] = "shop", 0
    else:
        free(s, t)


@m.action(t=TOOLS, mem=MEMBERS)
def cancel(s, t, mem):
    need(s["holder", t] == mem, "not held for this member")
    s["holder", t], s["age", t] = None, 0
    if s["where", t] == "shop":
        free(s, t)                              # to the next waiting member
    # in transit: it stays in transit; the next member gets it on arrival


@m.action()
def advance(s):                                 # night; holds on the shelf run out
    for t in TOOLS:
        if s["holder", t] is not None and s["where", t] == "shop":
            s["age", t] += 1
            if s["age", t] >= S["hold_days"]:
                s["holder", t] = None
                free(s, t)


m.option("bring", lambda s, mem, t, b: s["holder", t] == mem and s["where", t] == "shop"
         and s["branch", t] != b, action="bring", mem=MEMBERS, t=TOOLS, b=BRANCHES)
m.only_when("rent only from the shelf", "rent", lambda s, t, mem: s["where", t] == "shop")
m.after("bring keeps the hold", "bring", lambda b, a, t, mem, br: a["holder", t] == mem)
m.always("no hold runs out in transit", lambda s: all(
    s["where", t] != "transit" or s["age", t] == 0 for t in TOOLS))
m.progress("a tool in transit reaches the shelf", over=TOOLS,
           when=lambda s, t: s["where", t] == "transit", goal=lambda s, t: s["where", t] != "transit")
m.progress("a held tool is collected or released", over=TOOLS,
           when=lambda s, t: s["holder", t] is not None, goal=lambda s, t: s["holder", t] is None)
MACHINE = m
