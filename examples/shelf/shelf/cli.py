"""Command line demo."""

import sys

from shelf.loans import LoanService


def main(argv=None):
    svc = LoanService()
    svc.members.join("ann")
    svc.catalog.add("dune", 1)
    print(svc.borrow("ann", "dune"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
