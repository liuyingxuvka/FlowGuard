"""A held tool brought to another branch (request 11: collect at your own counter).

One tool, two members and two branches ("main", and "other": the rules only tell main apart).
The hold is the member the tool is held for; the queue is one waiting member (a longer queue
behaves the same behind the first one). Repair and inspection are left out: request 11 does
not change them.

The rules this model covers:
- A held tool can be brought to another branch by the member it is held for. It is in transit
  (not on the shelf, not on loan) and already belongs to the branch it goes to. The hold stays
  with the same member.
- A tool in transit cannot be brought again, rented, reserved, or handed to anyone.
- The hold clock does not run while the tool is in transit. When it arrives, the holder keeps
  the tool and gets a full hold from the day of arrival.
- A tool that arrives without a holder goes to the first waiting member, as before. A waiting
  member is never handed a tool held for someone else.
- The item screen offers `bring` for the holder, at a branch other than the tool's, when the
  tool is on the shelf (not in transit).
- A cancelled hold of a tool in transit does not put it on the shelf; it waits there until it
  arrives, and then goes to the next waiting member.
"""
from machine import Machine, need

M, N = "M", "N"          # the two members: M holds the tool first, N waits for it
MEMBERS = [M, N]
T = ["T"]                # one tool
BRANCHES = ["main", "other"]
NONE = "none"

m = Machine("held tool brought to another branch",
            settings=dict(hold_days=2))
S = m.settings           # read here, not copied: --set changes the value after the file loads

# Domains wide enough for every value --set may try. The clock counts days of the hold on the
# shelf; with the shipped settings the values above hold_days-1 are never reached (expected).
m.field("where", ["shop", "loan", "transit"], "shop", over=T)
m.field("branch", BRANCHES, "main", over=T)           # the branch the tool is at (or going to)
m.field("hold", [NONE] + MEMBERS, NONE, over=T)       # the member the tool is held for
m.field("waiting", [NONE] + MEMBERS, NONE, over=T)    # the member waiting for it (one place)
m.field("clock", range(0, 6), 0, over=T)              # days of the hold so far


def hand_over(s, t):
    """A tool on the shelf with no holder goes to the waiting member, who is then the holder."""
    if s["waiting", t] != NONE and s["hold", t] == NONE:
        s["hold", t], s["waiting", t], s["clock", t] = s["waiting", t], NONE, 0


@m.action(t=T, who=MEMBERS)
def reserve(s, t, who):
    need(s["where", t] != "transit", "in transit")
    need(s["where", t] == "loan" or s["hold", t] != NONE, "not on loan or held")
    need(s["hold", t] != who, "already held for this member")
    need(s["waiting", t] == NONE, "a place in the queue is taken")
    s["waiting", t] = who


@m.action(t=T, who=MEMBERS)
def rent(s, t, who):
    need(s["where", t] == "shop", "not on the shelf")
    need(s["hold", t] in (NONE, who), "held for another member")
    s["where", t] = "loan"
    s["hold", t], s["clock", t] = NONE, 0


@m.action(t=T)
def return_tool(s, t):
    need(s["where", t] == "loan", "not on loan")
    s["where", t] = "shop"
    hand_over(s, t)


@m.action(t=T, who=MEMBERS, to=BRANCHES)
def bring(s, t, who, to):
    need(s["hold", t] == who, "not held for this member")
    need(s["where", t] == "shop", "in transit")
    need(to != s["branch", t], "the tool is already at that branch")
    s["where", t] = "transit"
    s["branch", t] = to


@m.action(t=T)
def receive(s, t):
    need(s["where", t] == "transit", "not in transit")
    s["where", t] = "shop"
    if s["hold", t] == NONE:
        hand_over(s, t)
    else:
        s["clock", t] = 0                      # the holder gets a full hold from arrival


@m.action(t=T, who=MEMBERS)
def cancel(s, t, who):
    need(s["hold", t] == who, "not held for this member")
    s["hold", t], s["clock", t] = NONE, 0
    if s["where", t] == "shop":
        hand_over(s, t)


@m.action(t=T)
def day(s, t):
    """One day passes: the hold of a tool on the shelf runs; the hold ends at hold_days."""
    if s["hold", t] == NONE or s["where", t] != "shop":
        return
    s["clock", t] += 1
    if s["clock", t] >= S["hold_days"]:
        s["hold", t], s["clock", t] = NONE, 0
        hand_over(s, t)


m.option("bring", lambda s, t, who, to: (s["hold", t] == who and s["where", t] == "shop"
                                         and s["branch", t] != to),
         action="bring", t=T, who=MEMBERS, to=BRANCHES)
m.option("rent", lambda s, t, who: s["where", t] == "shop" and s["hold", t] in (NONE, who),
         action="rent", t=T, who=MEMBERS)

# The promises. The brought tool and its hold.
m.after("a brought tool is in transit, at the branch it goes to, held for the same member",
        "bring",
        lambda b, a, t, who, to: a["where", t] == "transit" and a["branch", t] == to
        and a["hold", t] == b["hold", t])
m.after("a tool that arrives for its holder is still held for that member", "receive",
        lambda b, a, t: a["hold", t] == b["hold", t] and a["where", t] == "shop"
        if b["hold", t] != NONE else True)
m.after("a tool that arrives for its holder keeps the waiting member waiting", "receive",
        lambda b, a, t: a["waiting", t] == b["waiting", t] if b["hold", t] != NONE else True)
m.after("a tool that arrives for its holder gets a full hold from arrival", "receive",
        lambda b, a, t: a["clock", t] == 0 if b["hold", t] != NONE else True)
m.after("the hold clock does not run while the tool is in transit", "day",
        lambda b, a, t: (a["hold", t] == b["hold", t] and a["clock", t] == b["clock", t])
        if b["where", t] == "transit" else True)
m.after("a cancelled hold of a tool in transit does not put it on the shelf", "cancel",
        lambda b, a, t, who: a["where", t] == "transit" if b["where", t] == "transit" else True)
m.after("a tool that comes back with a waiting member goes to that member", "return_tool",
        lambda b, a, t: a["hold", t] == b["waiting", t] if b["waiting", t] != NONE else True)
m.only_when("a tool in transit is not rented", "rent", lambda s, t, who: s["where", t] != "transit")
m.only_when("a tool in transit is not reserved", "reserve",
            lambda s, t, who: s["where", t] != "transit")
m.only_when("a tool is brought only for the member it is held for", "bring",
            lambda s, t, who, to: s["hold", t] == who)
m.always("a waiting member is never the holder of the same tool",
         lambda s: all(s["waiting", t] != s["hold", t] or s["waiting", t] == NONE for t in T))
m.always("a tool in transit is never on loan or on the shelf",
         lambda s: all(s["where", t] in ("shop", "loan", "transit") for t in T))

m.progress("a tool in transit always arrives", over=T,
           when=lambda s, t: s["where", t] == "transit",
           goal=lambda s, t: s["where", t] == "shop")
m.progress("a waiting member is eventually held the tool", over=MEMBERS,
           when=lambda s, who: s["waiting", T[0]] == who,
           goal=lambda s, who: s["hold", T[0]] == who)
m.reach("a member picks up at the other branch a tool brought for them",
        lambda s: any(s["hold", t] == M and s["where", t] == "shop" and s["branch", t] == "other"
                      for t in T))
m.reach("a brought tool is held for its member when it arrives",
        lambda s: any(s["hold", t] == N and s["where", t] == "shop" and s["waiting", t] == NONE
                      and s["branch", t] == "other" for t in T))

MACHINE = m
