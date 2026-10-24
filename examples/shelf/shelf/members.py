"""Members and their loan limits."""

LIMIT = 2


class Members:
    def __init__(self):
        self.known = set()

    def join(self, member):
        self.known.add(member)

    def may_borrow(self, member, current_loans):
        return member in self.known and current_loans < LIMIT
