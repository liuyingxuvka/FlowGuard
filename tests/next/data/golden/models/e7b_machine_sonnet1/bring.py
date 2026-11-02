"""Model of request 11: a held tool is brought to another branch for its member.

A held tool is on the shelf (where=shop, held=member). `bring` sends it in transit to
the new branch, still held. The hold clock does not run in transit (the member cannot
collect it); it restarts on arrival. Others may queue for it; if the member cancels in
transit the tool simply continues and goes to the next in the queue on arrival.
`rent` is refused while in transit.
"""
from machine import Machine, need

TOOLS = ["T1"]
MEMBERS = ["A", "B"]
BRANCHES = ["main", "lib"]
m = Machine("bring", settings=dict(hold_days=2))
S = m.settings
m.field("where", ["shop", "loan", "transit"], "shop", over=TOOLS)
m.field("branch", BRANCHES, "main", over=TOOLS)
m.field("held", [None] + MEMBERS, None, over=TOOLS)
m.field("queue", [None] + MEMBERS, None, over=TOOLS)      # one waiting member is enough
m.field("age", range(0, S["hold_days"]), 0, over=TOOLS)   # days the hold has run


def hold_next(s, t):
    if s["queue", t] is not None:
        s["held", t], s["queue", t], s["age", t] = s["queue", t], None, 0


@m.action(t=TOOLS, p=MEMBERS)
def rent(s, t, p):
    need(s["where", t] == "shop", "not in the shop")
    need(s["held", t] in (None, p), "held for another")
    s["where", t], s["held", t], s["age", t] = "loan", None, 0


@m.action(t=TOOLS)
def return_tool(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "shop"
    hold_next(s, t)


@m.action(t=TOOLS, p=MEMBERS)
def reserve(s, t, p):
    need(s["where", t] == "loan" or s["held", t] not in (None, p), "nothing to wait for")
    need(s["queue", t] is None and s["held", t] != p, "already waiting or held")
    s["queue", t] = p


@m.action(t=TOOLS, p=MEMBERS, b=BRANCHES)
def bring(s, t, p, b):
    need(s["held", t] == p, "not held for this member")
    need(s["where", t] == "shop", "not on the shelf (in transit)")
    need(s["branch", t] != b, "already there")
    s["where", t], s["branch", t], s["age", t] = "transit", b, 0


@m.action(t=TOOLS)
def receive(s, t):
    need(s["where", t] == "transit", "not in transit")
    s["where", t], s["age", t] = "shop", 0
    if s["held", t] is None:
        hold_next(s, t)


@m.action(t=TOOLS, p=MEMBERS)
def cancel(s, t, p):
    need(s["held", t] == p, "not held for this member")
    s["held", t], s["age", t] = None, 0
    if s["where", t] == "shop":
        hold_next(s, t)


@m.action()
def advance(s):                            # a night: shelf holds age; no-show ends them
    for t in TOOLS:
        if s["held", t] is not None and s["where", t] == "shop":
            s["age", t] += 1
            if s["age", t] >= S["hold_days"]:
                s["held", t], s["age", t] = None, 0
                hold_next(s, t)


m.option("bring", lambda s, t, p, b: s["held", t] == p and s["where", t] == "shop"
         and s["branch", t] != b, action="bring", t=TOOLS, p=MEMBERS, b=BRANCHES)
m.only_when("never rent in transit", "rent", lambda s, t, p: s["where", t] != "transit")
m.after("bring keeps the hold", "bring",
        lambda b, a, t, p, br: a["held", t] == p and a["where", t] == "transit")
m.after("arrival never changes who the tool is held for", "receive",
        lambda b, a, t: b["held", t] is None or a["held", t] == b["held", t])
m.progress("a held tool is always collected or released", over=TOOLS,
           when=lambda s, t: s["held", t] is not None, goal=lambda s, t: s["held", t] is None)
m.progress("a tool in transit arrives", over=TOOLS,
           when=lambda s, t: s["where", t] == "transit", goal=lambda s, t: s["where", t] != "transit")
m.reach("held tool in transit", lambda s: s["where", "T1"] == "transit" and s["held", "T1"] is not None)
MACHINE = m
