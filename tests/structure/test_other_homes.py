"""Other homes are static pointers through the shared postings index."""

DUP = {
    "lib/__init__.py": "",
    "lib/standing.py": """
        def may_borrow(member, today):
            return (today - member.expires_on).days <= 3 and not member.suspended
    """,
    "lib/doors.py": """
        from datetime import timedelta

        def door_opens(m, now):
            if m.suspended:
                return False
            if now > m.expires_on + timedelta(days=3):
                return False
            return True
    """,
    "lib/rooms.py": """
        def cancel_window_open(booking, today):
            return (today - booking.created_on).days <= 3

        def price(booking):
            if booking.hours > 8:
                return booking.hours * 9
            return booking.hours * 10
    """,
    "lib/env.py": """
        import os

        def debug_on():
            return os.environ.get("APP_DEBUG", "") in ("1", "true", "yes")

        def verbose():
            flag = os.getenv("APP_VERBOSE")
            if flag not in ("1", "true", "yes"):
                return False
            return True
    """,
    "lib/misc.py": """
        def total(items):
            return sum(i.price for i in items)

        def label(item):
            if item.kind == "book":
                return "B"
            return "?"
    """,
}


def test_a_duplicate_decision_written_differently_is_an_other_home(repo):
    repo.write(DUP)
    m = repo.build()
    found = m.other_homes("lib.standing:may_borrow", weak=True)
    strong = [h for h in found if h["strength"] == "strong"]
    assert strong and strong[0]["id"] == "lib.doors:door_opens", found
    assert "tests suspended" in strong[0]["reason"] and "3 days" in strong[0]["reason"]
    assert "lib.rooms:cancel_window_open" not in [h["id"] for h in strong]   # 3 days only: another decision
    assert "lib.misc:total" not in [h["id"] for h in found]
    worded = m.other_homes("lib.standing:may_borrow", words="3 grace days after expiry, unless suspended")
    assert worded[0]["id"] == "lib.doors:door_opens"
    sets = m.other_homes("lib.env:debug_on")
    assert sets and sets[0]["id"] == "lib.env:verbose" and "the same literal set" in sets[0]["reason"]
