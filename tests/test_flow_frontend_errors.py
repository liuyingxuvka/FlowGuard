"""The flow frontend reports failures before dispatch as one explicit error."""
import pytest

from _fg_helpers import flowguard_map_contracts421_project as basic_project


@pytest.mark.parametrize("verb", ["check", "show", "release"])
def test_status_preamble_failure_has_one_line_and_exit_two(verb, tmp_path, monkeypatch, capsys):
    from flowguard.__main__ import main
    from flowguard.map import status
    def broken(*args, **kwargs):
        raise NotADirectoryError(".flowguard/cache is a file")
    monkeypatch.setattr(status, "show_status_first", broken)
    assert main([verb, "--root", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    lines = (captured.out + captured.err).splitlines()
    assert len(lines) == 1 and "NotADirectoryError" in lines[0]
    assert "Traceback" not in lines[0]


def test_ctrl_c_is_one_line_without_traceback(tmp_path, monkeypatch, capsys):
    from flowguard.__main__ import main
    from flowguard.map import status
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(status, "show_status_first", interrupted)
    assert main(["check", "--root", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert (captured.out + captured.err).splitlines() == ["interrupted"]


@pytest.mark.parametrize("verb", ["check", "show", "release"])
def test_real_cache_file_in_status_preamble_is_one_error(verb, tmp_path, monkeypatch, capsys):
    from flowguard.__main__ import main
    basic_project(tmp_path)
    (tmp_path / ".flowguard/cache").write_text("not a directory\n")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "cache-file-regression")
    assert main([verb, "--root", str(tmp_path)]) == 2
    output = capsys.readouterr()
    assert "Traceback" not in output.out + output.err
    assert "internal error:" in output.out + output.err
    assert "(flowguard/" in output.out + output.err


def test_stdlib_exception_reports_the_calling_flowguard_location(tmp_path, monkeypatch, capsys):
    import json
    from flowguard.__main__ import main
    from flowguard.map import status
    monkeypatch.setattr(status, "show_status_first", lambda *a, **kw: json.loads("{"))
    assert main(["release", "--json", "--root", str(tmp_path)]) == 2
    output = capsys.readouterr()
    assert "(flowguard/__main__.py:" in output.err
    assert "json/decoder.py" not in output.err
    assert json.loads(output.out)["codes"][0]["subject"] == "flow"
