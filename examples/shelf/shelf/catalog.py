"""Catalog of books and their free copies."""


class Catalog:
    def __init__(self):
        self.copies = {}

    def add(self, book, count=1):
        self.copies[book] = self.copies.get(book, 0) + count

    def free(self, book):
        return self.copies.get(book, 0)

    def take(self, book):
        if self.copies.get(book, 0) <= 0:
            raise ValueError("no free copy")
        self.copies[book] -= 1

    def put_back(self, book):
        self.copies[book] = self.copies.get(book, 0) + 1
