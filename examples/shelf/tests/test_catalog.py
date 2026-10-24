from shelf.catalog import Catalog


def test_take_put_back():
    c = Catalog()
    c.add("x")
    c.take("x")
    assert c.free("x") == 0
    c.put_back("x")
    assert c.free("x") == 1
