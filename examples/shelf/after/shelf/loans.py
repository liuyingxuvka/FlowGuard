"""Lending: borrow and return books."""

from shelf.catalog import Catalog
from shelf.members import Members


class LoanService:
    def __init__(self, catalog=None, members=None):
        self.catalog = catalog or Catalog()
        self.members = members or Members()
        self.loans = []          # (member, book)
        self.holds = []          # (member, book) waiting in order

    def count(self, member):
        return sum(1 for m, _ in self.loans if m == member)

    def borrow(self, member, book):
        if not self.members.may_borrow(member, self.count(member)):
            return "refused"
        if self.catalog.free(book) <= 0:
            return "unavailable"
        self.catalog.take(book)
        self.loans.append((member, book))
        return "lent"

    def give_back(self, member, book):
        if (member, book) not in self.loans:
            return "not_lent"
        self.loans.remove((member, book))
        waiting = [h for h in self.holds if h[1] == book]
        if waiting:
            self.holds.remove(waiting[0])
            self.loans.append(waiting[0])
            return "returned"
        self.catalog.put_back(book)
        return "returned"

    def hold(self, member, book):
        if self.catalog.free(book) > 0 or (member, book) in self.holds:
            return "no_hold"
        self.holds.append((member, book))
        return "held"
