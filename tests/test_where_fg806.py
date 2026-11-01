"""`where` prints a bounded relevant part, says what it left out, and reuses parse work by content."""

import json
import os
import re
import subprocess

from flowguard.__main__ import main


def write(root, path, text):
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def git(root, *arguments):
    return subprocess.check_output(["git", "-C", str(root), *arguments], stderr=subprocess.PIPE).decode().strip()


def committed(root):
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")
    return git(root, "rev-parse", "HEAD")


def where(capsys, root, *arguments):
    assert main(["where", *arguments, "--root", str(root)]) == 0
    answer = capsys.readouterr()
    assert not answer.err, answer.err
    return answer.out


def test_text_file_default_shows_the_relevant_part_counts_the_rest_and_all_prints_everything(tmp_path, capsys):
    rules = [f"Rule {index}: the `missing_name_{index}` value MUST stay unique{index}." for index in range(30)]
    write(tmp_path, "doc.md", "\n\n".join(rules) + "\n")
    write(tmp_path, "core.py", "def present(): return 1\n")
    committed(tmp_path)

    default = where(capsys, tmp_path, "--text", "doc.md")
    shown = re.findall(r"^doc\.md:\d+-\d+ · source:", default, re.M)
    assert 0 < len(shown) < 30, default
    assert f"{30 - len(shown)} passages" in default
    assert "provenance:" not in default
    everything = where(capsys, tmp_path, "--text", "doc.md", "--all")
    assert all(rule in everything for rule in rules)
    assert len(re.findall(r"^doc\.md:\d+-\d+ · source:", everything, re.M)) == 30
    assert len(everything) > 2 * len(default)


def test_where_prints_no_fixed_disclaimer_lines_and_no_project_list_per_function(tmp_path, capsys):
    from flowguard.map import derived

    write(tmp_path, "app.py", '''import argparse
STATE = 0
def helper(): return STATE
def advance():
    global STATE
    STATE += 1
    return helper()
def reset():
    global STATE
    STATE = 0
def parser():
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command")
    commands.add_parser("orphan")
    commands.add_parser("other")
    return root
if __name__ == "__main__": advance()
''')
    fixed = ("complete resolved static graph", "rule-test provenance is unavailable", "no map at",
             derived.COHESION_UNKNOWN, "no rule-test provenance index", "tests: not recorded",
             "declared model anchors: none recorded", "behavior: not recorded")
    for arguments in (["helper"], ["app.py"], ["helper", "--flow"], ["--arch"], ["--keyflows"]):
        output = where(capsys, tmp_path, *arguments)
        for text in fixed:
            assert text not in output, (arguments, text)
        assert output.count("unknown entry bindings") <= 1, (arguments, output)
    write(tmp_path, ".flowguard/map.json", "{not json")
    assert main(["where", "helper", "--root", str(tmp_path)]) == 2  # A map that cannot be read stops the query.
    answer = capsys.readouterr()
    assert "is not valid JSON" in answer.err and not answer.out, answer


def test_repeated_query_reuses_parse_facts_by_content_digest_with_identical_bytes(tmp_path, capsys, monkeypatch):
    from flowguard.map import discover, inventory

    (tmp_path / ".flowguard").mkdir()
    write(tmp_path, "app.py", "from other import beta, zeta\ndef alpha(): return beta()\n")
    write(tmp_path, "other.py", "def beta(): return 1\ndef zeta(): return 2\n")
    parsed = []
    for module, name in ((inventory, "parse_python"), (discover, "file_facts")):
        def counted(*args, _real=getattr(module, name), _name=name, **kwargs):
            parsed.append(args[1] if _name == "parse_python" else args[3])
            return _real(*args, **kwargs)
        monkeypatch.setattr(module, name, counted)

    first = where(capsys, tmp_path, "alpha", "--flow")
    assert parsed
    parsed.clear()
    second = where(capsys, tmp_path, "alpha", "--flow")
    assert not parsed, "an unchanged file was parsed again: " + ", ".join(parsed)
    assert second == first
    source = tmp_path / "app.py"
    stat = source.stat()
    source.write_text(source.read_text().replace("return beta()", "return zeta()"))
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert source.stat().st_size == stat.st_size
    edited = where(capsys, tmp_path, "alpha", "--flow")
    assert set(parsed) == {"app.py"}
    assert "other.py#zeta" in edited and "other.py#beta" not in edited
    assert not any(path.is_file() and ".flowguard/cache" not in path.as_posix()
                   for path in (tmp_path / ".flowguard").rglob("*"))


def test_an_edit_that_keeps_size_and_modification_time_is_still_seen(tmp_path, capsys):
    from flowguard.map import inventory

    write(tmp_path, "app.py", "from other import gamma\ndef run(): return gamma()\n")
    write(tmp_path, "other.py", "def gamma(): return 1\n")
    write(tmp_path, "third.py", "def gamma(): return 2\n")
    old = 1_600_000_000_000_000_000
    for name in ("app.py", "other.py", "third.py"):
        os.utime(tmp_path / name, ns=(old, old))
    inventory.build_inventory(tmp_path, [], with_bodies=False)
    source = tmp_path / "app.py"
    source.write_text(source.read_text().replace("from other import", "from third import"))
    os.utime(source, ns=(old, old))

    output = where(capsys, tmp_path, "--arch")
    line = next(row for row in output.splitlines() if row.startswith("app.py ·"))
    assert "imports third.py" in line, line


def test_compact_text_view_does_no_blame_and_a_file_view_blames_at_most_that_file(tmp_path, capsys, monkeypatch):
    from flowguard.map import textrules

    for name in ("a", "b", "c"):
        write(tmp_path, name + ".md", f"You MUST keep the `{name}_missing` value for every {name} reader.\n")
    revision = committed(tmp_path)
    blamed, real = [], textrules._blame
    def counted(root, path, *args, **kwargs):
        blamed.append(path)
        return real(root, path, *args, **kwargs)
    monkeypatch.setattr(textrules, "_blame", counted)

    where(capsys, tmp_path, "--text")
    assert not blamed, "the compact text view shows no origins but blamed " + ", ".join(blamed)
    file_view = json.loads(where(capsys, tmp_path, "--text", "a.md", "--json"))
    assert set(blamed) <= {"a.md"}
    blamed.clear()
    identifier = file_view["texts"][0]["id"]
    original = where(capsys, tmp_path, "--text", "source:" + identifier)
    assert blamed == ["a.md"]
    assert "git " + revision[:12] + " 1-1" in original and "provenance:" not in original


def test_name_query_reports_string_literals_and_reads_only_files_containing_them(tmp_path, capsys, monkeypatch):
    from flowguard.map import derived

    for index in range(5):
        word = "needle" if index == 0 else f"word{index}"
        write(tmp_path, f"mod{index}.py", f"def get{index}():\n    return '{word}'\n")
    calls, real = [], derived.literal_sites
    def counted(text):
        calls.append(text)
        return real(text)
    monkeypatch.setattr(derived, "literal_sites", counted)

    output = where(capsys, tmp_path, "needle")
    assert any(line.startswith("mod0.py:2 ") and "get0" in line and "needle" in line for line in output.splitlines()), output
    assert "not resolved" not in output
    assert len(calls) == 1
    assert not any(line.startswith("mod1.py:2") for line in where(capsys, tmp_path, "value").splitlines())


def test_source_views_are_bounded_with_counts_and_all_prints_every_row(tmp_path, capsys):
    chain = "\n".join(f"def f{index}(): return f{index + 1}()" for index in range(24)) + "\ndef f24(): return 1\n"
    write(tmp_path, "zz_chain.py", chain)
    for index in range(12):
        write(tmp_path, f"small{index:02}.py", f"def s{index}(): return {index}\n")
    write(tmp_path, "middle.py", "def m1(): return 1\ndef m2(): return 2\n")

    flow = where(capsys, tmp_path, "f0", "--flow")
    rows = re.findall(r"^zz_chain\.py#f\d+:", flow, re.M)
    assert 0 < len(rows) < 25 and rows[0] == "zz_chain.py#f0:"
    assert f"{25 - len(rows)} functions" in flow
    assert len(re.findall(r"^zz_chain\.py#f\d+:", where(capsys, tmp_path, "f0", "--flow", "--all"), re.M)) == 25
    bounded = json.loads(where(capsys, tmp_path, "f0", "--flow", "--json"))
    assert len(bounded["functions"]) == len(rows) and bounded["omitted"]["functions"] == 25 - len(rows)
    assert len(json.loads(where(capsys, tmp_path, "f0", "--flow", "--all", "--json"))["functions"]) == 25
    arch = [line for line in where(capsys, tmp_path, "--arch").splitlines() if " functions" in line and " · " in line]
    assert arch[0].startswith("zz_chain.py · 25 functions") and arch[1].startswith("middle.py · 2 functions")
