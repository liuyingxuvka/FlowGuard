from shelf.cli import main
from shelf import members

def test_main_tells_refused_borrow(monkeypatch,capsys):
    monkeypatch.setattr(members,"LIMIT",0)
    assert main()==0
    assert capsys.readouterr().out.strip()=="refused"
