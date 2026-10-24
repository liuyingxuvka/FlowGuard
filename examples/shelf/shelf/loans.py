"""Lending: borrow and return books."""

from shelf.catalog import Catalog
from shelf.members import Members


class LoanService:
    def __init__(self, catalog=None, members=None):
        self.catalog = catalog or Catalog()
        self.members = members or Members()
        self.loans = []          # (member, book)

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
        self.catalog.put_back(book)
        return "returned"
