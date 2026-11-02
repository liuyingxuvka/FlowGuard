from app.config import Config


class Desk:
    """The lending desk: holds, loans, returns."""

    def __init__(self):
        self.books = {}

    def hold(self, book):
        if self.books.get(book, "shelf") != "shelf":
            raise ValueError("not on the shelf")
        self.books[book] = "held"

    def lend(self, book):
        if self.books.get(book) != "held":
            raise ValueError("not held")
        self.books[book] = "loan"

    def give_back(self, book):
        if self.books.get(book) != "loan":
            raise ValueError("not on loan")
        self.books[book] = "shelf"
