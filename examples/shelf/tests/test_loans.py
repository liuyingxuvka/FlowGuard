from shelf.loans import LoanService


def _svc():
    s = LoanService()
    s.members.join("ann")
    s.catalog.add("dune", 1)
    return s


def test_borrow_and_return():
    s = _svc()
    assert s.borrow("ann", "dune") == "lent"
    assert s.borrow("ann", "dune") == "unavailable"
    assert s.give_back("ann", "dune") == "returned"
    assert s.catalog.free("dune") == 1


def test_limit():
    s = _svc()
    s.catalog.add("a", 3)
    assert s.borrow("ann", "a") == "lent"
    assert s.borrow("ann", "a") == "lent"
    assert s.borrow("ann", "a") == "refused"
