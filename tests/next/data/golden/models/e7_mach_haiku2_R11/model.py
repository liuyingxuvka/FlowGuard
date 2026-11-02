"""Design model for REQUEST.md (request 11): a member has a held tool brought to another branch.

Run:  python tools/machine.py design/model.py

What is modelled: one tool T, three members (M1 is the member whose session is on the
item screen; M2 and M3 are other members), two branches, and the session branch of M1 (B2).
The hold clock is `age` (days since the hold started, clamped at hold_days). The
condition is "shop" (on the shelf at its branch) or "transit" (on the way, not yet
received). Repair, inspection, fees and the no-show charge are left out: they change
neither where the tool is nor who holds it. The nonexistent-branch refusal is left
out too: it is a plain check on the argument and changes no interaction.

Two machines are explored:
  - "design": the rules DESIGN.md chooses.
  - "naive": the code as it is today, with `bring` added and nothing else changed.
    Each rule it breaks is a decision the design has to make on purpose.
"""
from machine import Machine, need

MEMBERS = ["M1", "M2", "M3"]
BRANCHES = ["main", "B2"]
SESSION = "B2"                                   # the branch of M1's session
# Queues of up to two members: one member holds or has the tool, so two can wait at once
# only with three members.
QUEUES = [()] + [(a,) for a in MEMBERS] + [(a, b) for a in MEMBERS for b in MEMBERS if a != b]


def build(naive, hold_days=2):
    name = "request 11, current code extended naively" if naive else "request 11, design"
    # held_list: 1 = the reservations screen's held list offers `open` (the item screen of a
    # tool held elsewhere is reachable); 0 = only search, which lists this branch's tools.
    m = Machine(name, settings=dict(hold_days=hold_days, held_list=1))
    S = m.settings

    m.field("loan", [None] + MEMBERS, None)            # who has the tool on loan
    m.field("hold", [None] + MEMBERS, None)            # whom the tool is held for
    m.field("queue", QUEUES, ())                       # reservations, first in line first
    m.field("cond", ["shop", "transit"], "shop")       # on the shelf, or on the way
    m.field("branch", BRANCHES, "main")                # where it is (or is going)
    m.field("age", range(0, S["hold_days"]), 0)        # days since the hold started (expiry resets it)
    m.field("screen", ["away", "item"], "away")        # M1's item screen

    def hand_next(s):
        """The tool is on the shelf: hold it for the first in line (if anyone waits)."""
        if s["queue"]:
            s["hold"], s["queue"], s["age"] = s["queue"][0], s["queue"][1:], 0

    def can_rent(s, who):
        if s["loan"] is not None:
            return False
        if s["hold"] is not None and s["hold"] != who:
            return False
        if naive:   # today: a tool held for you is rentable whatever its condition
            return s["hold"] == who or s["cond"] == "shop"
        return s["cond"] == "shop"

    def can_reserve(s, who):
        return (s["cond"] == "shop" and (s["loan"] is not None or s["hold"] is not None)
                and s["loan"] != who and s["hold"] != who and who not in s["queue"])

    def can_bring(s, who, b):
        held_elsewhere = s["hold"] == who and s["branch"] != b
        return held_elsewhere if naive else held_elsewhere and s["cond"] == "shop"

    # ------------------------------------------------------------ members
    @m.action(who=MEMBERS)
    def rent(s, who):
        need(can_rent(s, who), "not rentable now")
        s["loan"], s["hold"], s["age"] = who, None, 0
        if who == "M1":
            s["screen"] = "away"

    @m.action(who=MEMBERS)
    def return_tool(s, who):
        need(s["loan"] == who, "not on loan to them")
        s["loan"] = None
        hand_next(s)

    @m.action(who=MEMBERS)
    def reserve(s, who):
        need(can_reserve(s, who), "not reservable now")
        s["queue"] = s["queue"] + (who,)
        if who == "M1":
            s["screen"] = "away"

    @m.action(who=MEMBERS)
    def cancel(s, who):
        if who in s["queue"]:
            s["queue"] = tuple(x for x in s["queue"] if x != who)
            return
        need(s["hold"] == who, "no reservation of theirs")
        s["hold"], s["age"] = None, 0
        if naive:                    # today's code puts the tool back on the shelf
            s["cond"] = "shop"
        if s["cond"] == "shop":      # in transit: the next in line waits for arrival
            hand_next(s)

    @m.action(who=MEMBERS, b=BRANCHES)
    def bring(s, who, b):
        need(can_bring(s, who, b), "not held for them elsewhere, or not on the shelf")
        s["branch"], s["cond"] = b, "transit"

    # ------------------------------------------------------------ staff
    @m.action()
    def receive(s):
        need(s["cond"] == "transit", "not on the way")
        s["cond"] = "shop"
        if naive or s["hold"] is None:
            hand_next(s)             # naive: this overwrites the hold of the member
        else:
            s["age"] = 0             # held for its member: the window starts on arrival

    @m.action(b=BRANCHES)
    def transfer(s, b):
        need(s["cond"] == "shop" and s["loan"] is None and s["hold"] is None,
             "only an available tool can be sent")
        need(b != s["branch"], "already at that branch")
        s["branch"], s["cond"] = b, "transit"

    @m.action()
    def advance(s):
        if s["hold"] is None:
            return
        if not naive and s["cond"] != "shop":
            return                   # design: the clock does not run while on the way
        s["age"] += 1
        if s["age"] >= S["hold_days"]:
            s["hold"], s["age"] = None, 0
            if naive:
                s["cond"] = "shop"   # today's code: expiry puts it on the shelf
            if s["cond"] == "shop":
                hand_next(s)

    # ------------------------------------------------------------ the item screen of M1
    @m.action()
    def open_item(s):
        need(s["screen"] == "away", "already on the item screen")
        listed = s["branch"] == SESSION or (S["held_list"] == 1 and s["hold"] == "M1")
        need(listed, "not listed on any of M1's screens")
        s["screen"] = "item"

    @m.action()
    def leave_item(s):
        need(s["screen"] == "item", "not on the item screen")
        s["screen"] = "away"

    m.option("rent", lambda s, who: s["screen"] == "item" and can_rent(s, who),
             action="rent", who=["M1"])
    m.option("reserve", lambda s, who: s["screen"] == "item" and can_reserve(s, who),
             action="reserve", who=["M1"])
    m.option("bring", lambda s, who, b: s["screen"] == "item" and can_bring(s, who, b),
             action="bring", who=["M1"], b=[SESSION])

    # ------------------------------------------------------------ the promises
    m.always("a tool on the way is not on loan",
             lambda s: not (s["cond"] == "transit" and s["loan"] is not None))
    m.always("a tool on loan is not held",
             lambda s: s["loan"] is None or s["hold"] is None)
    m.always("the member holding a tool is not also waiting for it",
             lambda s: s["hold"] not in s["queue"])
    m.always("a queue waits only for a tool that is out, held or on the way",
             lambda s: (not s["queue"] or s["loan"] is not None or s["hold"] is not None
                        or s["cond"] == "transit"))
    m.after("a tool on the way is made available only by its arrival", "*",
            lambda b, a, action, args: not (b["cond"] == "transit" and a["cond"] == "shop")
            or action == "receive")
    m.after("bring holds the tool for the same member, sent to the branch asked, on the way",
            "bring",
            lambda b, a, who, br: (a["hold"] == who and a["branch"] == br
                                   and a["cond"] == "transit" and a["queue"] == b["queue"]))
    m.after("a brought tool stays held for its member when it arrives", "receive",
            lambda b, a: b["hold"] is None or a["hold"] == b["hold"])
    m.progress("a tool on the way always arrives",
               when=lambda s: s["cond"] == "transit", goal=lambda s: s["cond"] == "shop")
    m.progress("a hold always ends",
               when=lambda s: s["hold"] is not None, goal=lambda s: s["hold"] is None)
    m.reach("a tool brought for M1 is on the way to M1's branch",
            lambda s: s["cond"] == "transit" and s["hold"] == "M1" and s["branch"] == SESSION)
    m.reach("M1 can pick up at their branch a tool brought there",
            lambda s: s["hold"] == "M1" and s["cond"] == "shop" and s["branch"] == SESSION)
    return m


MACHINES = [build(naive=False), build(naive=True)]
