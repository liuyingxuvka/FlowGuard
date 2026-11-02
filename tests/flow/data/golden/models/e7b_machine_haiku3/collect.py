"""Collect at your own counter: one tool that a member holds, and where it is.

The slice modelled: one tool, two members (M1, M2), two branches (main, A). A tool
is on the shelf ("shop"), in transit between branches, or on loan. A hold is for one
member; one member may wait in line behind it. The hold has a pick-up window that
counts days (it does not run while the tool is in transit).

Actions: bring (a holder asks for the tool at another branch), transfer (staff send an
available tool), receive (a tool in transit arrives), rent / pick up, return, reserve,
cancel, advance (a day passes).
"""
from machine import Machine, need

MEMBERS = ["M1", "M2"]
BRANCHES = ["main", "A"]

m = Machine("collect at your own counter", settings=dict(hold_days=2))
S = m.settings
H = S["hold_days"]

m.field("at", BRANCHES, "main")                       # the branch the tool is at (or going to)
m.field("cond", ["shop", "transit", "loan"], "shop")
m.field("hold", ["none"] + MEMBERS, "none")           # the member the tool is held for
m.field("wait", ["none"] + MEMBERS, "none")           # the next in line
m.field("clock", range(0, H), 0)                      # days after today the pick-up can still happen


def shelve(s):
    """The tool is on the shelf: the next in line gets the hold, with a fresh window."""
    s["cond"] = "shop"
    if s["wait"] != "none":
        s["hold"], s["wait"], s["clock"] = s["wait"], "none", H - 1


def bring_refusal(s, who, to):
    if s["hold"] != who:
        return "tool is not held for this member"
    if s["at"] == to:
        return "tool is already at that branch"
    return None


def reserve_refusal(s, who):
    if s["cond"] == "transit":
        return "a tool in transit cannot be reserved"
    if not (s["cond"] == "loan" or s["hold"] != "none"):
        return "the tool is available"
    if s["hold"] == who or s["wait"] != "none":
        return "no place for this member"
    return None


@m.action(who=MEMBERS, to=BRANCHES)
def bring(s, who, to):
    need(bring_refusal(s, who, to) is None, bring_refusal(s, who, to) or "")
    s["at"], s["cond"] = to, "transit"


@m.action(to=BRANCHES)
def transfer(s, to):
    need(s["cond"] == "shop" and s["hold"] == "none", "only an available tool can be sent")
    need(s["at"] != to, "already at that branch")
    s["at"], s["cond"] = to, "transit"


@m.action()
def receive(s):
    need(s["cond"] == "transit", "not in transit")
    if s["hold"] != "none":
        s["cond"], s["clock"] = "shop", H - 1          # the window starts on arrival
    else:
        shelve(s)


@m.action(who=MEMBERS)
def pick_up(s, who):                                   # rent a tool held for you
    need(s["hold"] == who and s["cond"] == "shop", "not held for you on the shelf")
    s["cond"], s["hold"], s["clock"] = "loan", "none", 0


@m.action(who=MEMBERS)
def rent_free(s, who):                                 # rent an available tool
    need(s["hold"] == "none" and s["cond"] == "shop", "not available")
    s["cond"] = "loan"


@m.action()
def return_tool(s):
    need(s["cond"] == "loan", "not on loan")
    shelve(s)


@m.action(who=MEMBERS)
def reserve(s, who):
    need(reserve_refusal(s, who) is None, reserve_refusal(s, who) or "")
    s["wait"] = who


@m.action(who=MEMBERS)
def cancel(s, who):
    need(s["hold"] == who or s["wait"] == who, "no reservation")
    if s["wait"] == who:
        s["wait"] = "none"
    else:
        s["hold"], s["clock"] = "none", 0
        if s["cond"] == "shop":                        # in transit: shelved on arrival
            shelve(s)


@m.action()
def advance(s):
    if s["hold"] != "none" and s["cond"] == "shop":    # the window does not run in transit
        if s["clock"] == 0:                            # the last pick-up day has passed
            s["hold"] = "none"
            shelve(s)
        else:
            s["clock"] = 0


# screen options: the item screen of a member at branch `to`
m.option("bring", lambda s, who, to: bring_refusal(s, who, to) is None,
         action="bring", who=MEMBERS, to=BRANCHES)
m.option("rent", lambda s, who: s["hold"] == who and s["cond"] == "shop",
         action="pick_up", who=MEMBERS)
m.option("reserve", lambda s, who: reserve_refusal(s, who) is None,
         action="reserve", who=MEMBERS)

m.always("a held tool is never on loan",
         lambda s: not (s["hold"] != "none" and s["cond"] == "loan"))
m.always("a waiting member is not the holder",
         lambda s: s["wait"] == "none" or s["wait"] != s["hold"])
m.always("the window runs only for a held tool on the shelf",
         lambda s: s["hold"] != "none" or s["clock"] == 0)

m.after("a tool in transit stays in transit until it is received", "*",
        lambda b, a, act, args: act == "receive" or b["cond"] != "transit" or a["cond"] == "transit")
m.after("the pick-up window does not run in transit", "*",
        lambda b, a, act, args: act != "advance" or b["cond"] != "transit"
        or (a["hold"] == b["hold"] and a["clock"] == b["clock"]))
m.after("bring keeps the hold for the same member", "bring",
        lambda b, a, who, to: a["hold"] == who)
m.after("a held tool that arrives gets a fresh window", "receive",
        lambda b, a: b["hold"] == "none" or a["clock"] == H - 1)

m.progress("a tool in transit is received", when=lambda s: s["cond"] == "transit",
           goal=lambda s: s["cond"] != "transit")
m.progress("a held tool is picked up or released", when=lambda s: s["hold"] != "none",
           goal=lambda s: s["hold"] == "none")

m.reach("a tool held for a member is brought, arrives and is picked up at the new branch",
        lambda s: s["cond"] == "loan" and s["at"] == "A")
m.reach("a held tool can be in transit (and so can be brought again)",
        lambda s: s["cond"] == "transit" and s["hold"] != "none")

MACHINE = m
