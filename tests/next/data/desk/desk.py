"""Lending desk: holds, loans, renewals and returns of two interchangeable books.
Left out: members and fees (no rule reads who holds a book or what it costs)."""
from flowguard._next import Model, need

m = Model("desk", covers=["app/desk.py:Desk"], config="app.config:Config",
          note="one member per book at a time; members are not modelled")
S = m.settings
m.setting("hold_days", source="R2")
m.setting("max_renewals", source="R3")
BOOKS = m.objects("book", "B1", "B2")
m.field("where", ["shelf", "held", "loan"], "shelf", over=BOOKS, source="R1")
m.field("nights", range(0, S["hold_days"] + 1), 0, over=BOOKS, source="R2",
        note="nights a held book has waited, 0..hold_days")
m.field("renewed", range(0, S["max_renewals"] + 1), 0, over=BOOKS, source="R3")


@m.action(b=BOOKS, source="R1")
def hold(s, b):
    need(s["where", b] == "shelf", "not on the shelf")
    s["where", b], s["nights", b] = "held", 0


@m.action(b=BOOKS, source="R1")
def lend(s, b):
    need(s["where", b] == "held", "not held")
    s["where", b], s["renewed", b] = "loan", 0


@m.action(source="R2")
def night(s):
    for b in BOOKS:
        if s["where", b] == "held":
            s["nights", b] += 1
            if s["nights", b] >= S["hold_days"]:
                s["where", b], s["nights", b] = "shelf", 0


@m.action(b=BOOKS, source="R3")
def renew(s, b):
    need(s["where", b] == "loan", "not on loan")
    need(s["renewed", b] < S["max_renewals"], "renewed too often")
    s["renewed", b] += 1


@m.action(b=BOOKS, source="R3")
def give_back(s, b):
    need(s["where", b] == "loan", "not on loan")
    s["where", b], s["renewed", b] = "shelf", 0


m.option("lend", lambda s, b: s["where", b] == "held", action="lend", b=BOOKS, source="R1")
m.always("a held book has waited less than hold_days",
         lambda s: all(s["nights", b] < S["hold_days"] for b in BOOKS if s["where", b] == "held"), source="R2")
m.progress("a held book gets lent or goes back", over=BOOKS, source="R2",
           when=lambda s, b: s["where", b] == "held", goal=lambda s, b: s["where", b] != "held")
m.reach("a renewed book", lambda s: any(s["renewed", b] > 0 for b in BOOKS), source="R3")
MODEL = m
