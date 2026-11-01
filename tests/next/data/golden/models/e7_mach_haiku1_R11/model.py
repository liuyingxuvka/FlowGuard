"""Request 11 (collect at your own counter), as a small model: one held tool, two members.

M1 is the member whose screens are modelled (session branch `sb`, screens home /
item / reservations). M2 is any other member: they act without screens. Staff
actions (transfer, receive, return, advance) have no screens.

Run:  python tools/machine.py design/model.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from machine import Machine, need  # noqa: E402

MEMBERS = ["M1", "M2"]
BR = ["main", "north", "east"]

# Settings. The shipped values are the design proposed in DESIGN.md. The other values
# are the alternatives the design weighs (run them with --set); naive_back_in_shop=True
# is what counter/core.py's _back_in_shop does today.
m = Machine("collect at your own counter",
            settings=dict(hold_days=2,                  # days the holder has to pick up
                          pause_hold_in_transit=True,   # the hold clock does not run in transit
                          reserved_items_open=True,     # reservations list lets M1 open held items
                          naive_back_in_shop=False))    # True: today's _back_in_shop behaviour
S = m.settings

m.field("at", BR, "main")                       # the branch the tool is at (or travelling to)
m.field("cond", ["shop", "transit", "loan"], "shop")
m.field("holder", [None] + MEMBERS, None)       # who the tool is held for
m.field("waiting", [None] + MEMBERS, None)      # the queue (one place is enough for two members)
m.field("renter", [None] + MEMBERS, None)       # who has it on loan
m.field("left", range(0, S["hold_days"] + 1), 0)  # days the holder has left to pick up
m.field("sb", BR, "main")                       # M1's session branch
m.field("screen", ["home", "item", "reservations"], "home")   # M1's screen
m.field("far", [False, True], False)            # M1 opened the item from a branch the tool is not at


def on_screen(s, who, screen):
    return who != "M1" or s["screen"] == screen


def start_hold(s, who):
    s["holder"], s["left"] = who, S["hold_days"]


def hold_next(s):
    """The tool is on the shelf and nobody holds it: the first waiting member gets it."""
    if s["holder"] is None and s["cond"] == "shop" and s["waiting"] is not None:
        start_hold(s, s["waiting"])
        s["waiting"] = None


def back_in_shop(s):
    if S["naive_back_in_shop"]:              # what counter/core.py does today
        s["cond"] = "shop"
        if s["waiting"] is not None:         # ...even when someone already holds it
            start_hold(s, s["waiting"])
            s["waiting"] = None
    else:
        s["cond"] = "shop"
        hold_next(s)


# ---------------------------------------------------------------- M1's navigation
@m.action()
def go_reservations(s):
    need(s["screen"] == "home", "not on home")
    s["screen"] = "reservations"


@m.action()
def back_home(s):
    need(s["screen"] != "home", "already home")
    s["screen"] = "home"


@m.action(b=BR)
def new_session(s, b):
    s["sb"], s["screen"], s["far"] = b, "home", False


@m.action()
def open_item(s):
    # from home: the search finds the tool only at M1's branch;
    # from reservations: a held tool is listed (setting reserved_items_open)
    at_home = s["screen"] == "home" and s["at"] == s["sb"]
    listed = (s["screen"] == "reservations" and S["reserved_items_open"]
              and s["holder"] == "M1")
    need(at_home or listed, "the tool is not on this screen")
    s["far"] = s["at"] != s["sb"]
    s["screen"] = "item"


# ---------------------------------------------------------------- members
@m.action(who=MEMBERS)
def reserve(s, who):
    need(on_screen(s, who, "item"), "not on the item screen")
    need(s["cond"] == "loan" or (s["cond"] == "shop" and s["holder"] is not None),
         "only a tool on loan or held for another member can be reserved")
    need(s["holder"] != who and s["renter"] != who and s["waiting"] is None,
         "already holding, waiting or renting it")
    s["waiting"] = who


@m.action(who=MEMBERS)
def cancel(s, who):
    need(on_screen(s, who, "reservations"), "not on the reservations screen")
    need(s["holder"] == who or s["waiting"] == who, "no reservation for this member")
    if s["holder"] == who:
        s["holder"], s["left"] = None, 0
        if S["naive_back_in_shop"]:
            back_in_shop(s)
        else:
            hold_next(s)         # on the shelf: the next waiting member; in transit: at receive
    else:
        s["waiting"] = None


@m.action(who=MEMBERS)
def rent(s, who):
    # an available tool (no hold) is rentable by anyone; a held one only by its holder
    need(on_screen(s, who, "item"), "not on the item screen")
    need(s["holder"] in (None, who), "held for another member")
    # counter/core.py's why_not_rent does not look at the condition of a held tool
    need(s["cond"] == "shop" or (S["naive_back_in_shop"] and s["holder"] == who), "not on the shelf")
    need(who != "M1" or s["at"] == s["sb"], "the tool is at another branch")
    s["renter"], s["cond"], s["holder"], s["left"] = who, "loan", None, 0


@m.action(who=MEMBERS, b=BR)
def bring(s, who, b):
    need(on_screen(s, who, "item"), "not on the item screen")
    need(s["holder"] == who, "not held for this member")
    need(s["cond"] == "shop", "the tool is already travelling or on loan")
    need(b != s["at"], "the tool is already at that branch")
    s["cond"], s["at"] = "transit", b


# ---------------------------------------------------------------- staff and the clock
@m.action(b=BR)
def transfer(s, b):
    need(s["cond"] == "shop" and s["holder"] is None, "only an available tool can be sent")
    need(b != s["at"], "already at that branch")
    s["cond"], s["at"] = "transit", b


@m.action()
def receive(s):
    need(s["cond"] == "transit", "not in transit")
    if not S["naive_back_in_shop"] and S["pause_hold_in_transit"] and s["holder"] is not None:
        s["left"] = S["hold_days"]           # the holder's days start at the new branch
    back_in_shop(s)


@m.action(who=MEMBERS)
def return_tool(s, who):
    need(s["renter"] == who, "not on loan to this member")
    s["renter"] = None
    back_in_shop(s)


@m.action()
def advance(s):
    if s["holder"] is not None and (s["cond"] == "shop" or not S["pause_hold_in_transit"]):
        s["left"] -= 1
        if s["left"] == 0:                   # the last day to pick up has passed
            s["holder"] = None
            if S["naive_back_in_shop"]:
                back_in_shop(s)
            else:
                hold_next(s)


# ---------------------------------------------------------------- screen options (M1)
m.option("reservations", lambda s: s["screen"] == "home", action="go_reservations")
m.option("home", lambda s: s["screen"] != "home", action="back_home")
m.option("open", lambda s: (s["screen"] == "home" and s["at"] == s["sb"])
         or (s["screen"] == "reservations" and S["reserved_items_open"] and s["holder"] == "M1"),
         action="open_item")
m.option("rent", lambda s, who: who == "M1" and s["screen"] == "item" and s["holder"] in (None, "M1")
         and s["cond"] == "shop" and s["at"] == s["sb"], action="rent", who=MEMBERS)
m.option("reserve", lambda s, who: who == "M1" and s["screen"] == "item"
         and (s["cond"] == "loan" or (s["cond"] == "shop" and s["holder"] is not None))
         and s["holder"] != "M1" and s["renter"] != "M1" and s["waiting"] is None,
         action="reserve", who=MEMBERS)
m.option("bring", lambda s, who, b: who == "M1" and s["screen"] == "item"
         and s["holder"] == "M1" and s["cond"] == "shop" and b == s["sb"] and s["at"] != b,
         action="bring", who=MEMBERS, b=BR)
m.option("cancel", lambda s, who: who == "M1" and s["screen"] == "reservations"
         and (s["holder"] == "M1" or s["waiting"] == "M1"), action="cancel", who=MEMBERS)

# ---------------------------------------------------------------- promises
m.always("a tool on loan is not held", lambda s: s["renter"] is None or s["holder"] is None)
m.always("on loan exactly when someone has it", lambda s: (s["cond"] == "loan") == (s["renter"] is not None))
m.always("a clock runs only for a hold", lambda s: s["holder"] is not None or s["left"] == 0)

m.after("a tool in transit stays in transit until received", "*",
        lambda b, a, name, args: b["cond"] != "transit" or name == "receive" or a["cond"] == "transit")
m.after("a held tool stays held for the same member, except when they cancel, rent or run out",
        "*", lambda b, a, name, args: (b["holder"] is None or name in ("cancel", "rent", "advance")
                                       or a["holder"] == b["holder"]))
m.only_when("bring only by the member it is held for, and only to another branch", "bring",
            lambda s, who, b: s["holder"] == who and b != s["at"])
m.only_when("staff send only tools that nobody holds", "transfer", lambda s, b: s["holder"] is None)
m.only_when("a held tool is rented only by its holder", "rent",
            lambda s, who: s["holder"] in (None, who))
m.only_when("M1 rents only where the tool is", "rent",
            lambda s, who: who != "M1" or s["at"] == s["sb"])

m.progress("a tool in transit arrives", when=lambda s: s["cond"] == "transit",
           goal=lambda s: s["cond"] != "transit")
m.progress("a hold ends or is picked up", when=lambda s: s["holder"] is not None,
           goal=lambda s: s["holder"] is None)
m.reach("M1 opens from their own branch a tool held for them at another branch",
        lambda s: s["screen"] == "item" and s["far"] and s["holder"] == "M1" and s["at"] != s["sb"])
m.after("a held tool gets the usual pick-up days when it arrives", "receive",
        lambda b, a: b["holder"] is None or a["left"] == S["hold_days"])
m.reach("M1 collects a tool brought to another branch",
        lambda s: s["renter"] == "M1" and s["at"] != "main")
m.reach("M1 gets a tool brought to their branch and held for them",
        lambda s: s["holder"] == "M1" and s["cond"] == "shop" and s["at"] == s["sb"] and s["sb"] != "main")

MACHINE = m
