"""Real child traces, independent state, and public-prefix restoration."""

import copy
import sys

import pytest

from flowguard.behave.project import UnsupportedWorld, construct, replay, restore
from flowguard.behave.skeleton import derive
from .test_skeleton import example

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")


def test_complete_graph_retains_hidden_slots_aliases_cycles_and_order(example):
    spec = derive(example)
    calls = [{"name": "add_entry", "args": ["B", "second"]},
             {"name": "add_entry", "args": ["A", "first"]},
             {"name": "bump", "args": ["A"]}]
    observed = replay(spec, calls)
    graph = observed["final"]["graph"]
    nodes = graph["nodes"]
    attributes = next(dict(node["attributes"]) for node in nodes if node["type"] == "example:Engine")
    assert attributes["_hidden"] == attributes["_alias"]
    sequence = nodes[attributes["_cycle"]["ref"]]
    assert sequence["items"] == [attributes["_cycle"]]
    assert nodes[attributes["_items"]["ref"]]["items"] == [["B", "second"], ["A", "first"]]
    assert next(dict(node["attributes"]) for node in nodes if node["type"] == "example:Vault")["_Vault__secret"] == 2
    assert observed["steps"][-1]["before"] != observed["steps"][-1]["after"]
    assert observed == replay(spec, calls)


def test_restore_replays_public_prefix_and_continues(example):
    spec = derive(example)
    prefix = [{"name": "add_entry", "args": ["E1", "one"]}, {"name": "bump", "args": ["E1"]}]
    tail = [{"name": "bump", "args": ["E1"]}]
    checkpoint = replay(spec, prefix)["final"]
    assert restore(spec, prefix, checkpoint, tail=tail)["final"] == replay(spec, prefix + tail)["final"]
    incomplete = copy.deepcopy(checkpoint)
    incomplete["graph"]["nodes"] = []
    with pytest.raises(UnsupportedWorld, match="complete checkpoint"):
        restore(spec, prefix, incomplete)


def test_native_save_load_and_resave_keep_complete_state_and_relative_files(example):
    spec = derive(example)
    recipe = {"$file": "counter.json"}
    calls = [{"name": "add_entry", "args": ["E1", "one"]},
             {"name": "bump", "args": ["E1"]},
             {"name": "save", "args": [recipe]},
             {"name": "load", "args": [recipe], "replace": True},
             {"name": "bump", "args": ["E1"]},
             {"name": "save", "args": [recipe]}]
    result = replay(spec, calls)
    assert all(item["outcome"] == "success" for item in result["steps"])
    assert result["steps"][2]["after"]["graph"] == result["steps"][3]["after"]["graph"]
    assert result["steps"][2]["after"]["files"] != result["final"]["files"]
    assert [item[0] for item in result["final"]["files"]] == ["counter.json", "home", "temp"]
    assert result == replay(spec, calls)


def test_refusal_is_observed_without_discarding_hidden_changes(example):
    result = replay(derive(example), [{"name": "refuse"}, {"name": "refuse_changed"}])
    plain, changed = result["steps"]
    assert plain["outcome"] == changed["outcome"] == "refusal"
    assert plain["before"] == plain["after"]
    assert changed["before"] != changed["after"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission mode control")
def test_refused_permission_change_is_not_equal_state(example):
    result = replay(derive(example), [{"name": "refuse_permissions"}], {"files": {"locked": "eA=="}})
    step = result["steps"][0]
    assert step["outcome"] == "refusal"
    assert step["before"]["graph"] == step["after"]["graph"]
    assert step["before"]["files"] != step["after"]["files"]


def test_container_subtype_is_explicitly_unsupported(example):
    with pytest.raises(UnsupportedWorld, match="container subtype"):
        replay(derive(example), [{"name": "use_subtype"}])


def test_live_construction_is_not_allowed_in_the_coordinator(example):
    with pytest.raises(UnsupportedWorld, match="fresh native worker"):
        construct(derive(example))


def test_shipped_defaults_seeding_and_scalar_results_are_recorded(example):
    spec = derive(example)
    result = replay(spec, [{"name": "bump", "args": ["E1"]},
                           {"name": "bump", "args": [{"$result": 0}]}],
                    {"world": "small", "settings": {"limit": 8}})
    assert result["defaults"] == {"limit": 3}
    assert len(result["seeding"]) == 1
    assert result["steps"][1]["value"]["root"] == 2
    assert any(dict(node.get("attributes", [])) == {"limit": 8} for node in result["initial"]["graph"]["nodes"])


def test_opaque_runtime_state_does_not_become_an_empty_graph(example):
    path = example / "example.py"
    path.write_text(path.read_text() + '\n    def opaque(self): self._opaque = __import__("random").Random()\n')
    with pytest.raises(UnsupportedWorld, match="opaque state|nondeterministic resource"):
        replay(derive(example), [{"name": "opaque"}])


def test_arena_paths_in_diagnostics_are_reproducible(example):
    path = example / "example.py"
    source = path.read_text().replace('        self._options =', '        print("root=" + str(Path.cwd()))\n        self._options =')
    path.write_text(source + '\n    def missing(self, path):\n        print(path)\n        return Path(path).read_bytes()\n')
    spec = derive(example)
    calls = [{"name": "missing", "args": [{"$file": "missing"}]}]
    observed = replay(spec, calls)
    assert observed == replay(spec, calls)
    assert observed["construction_stdout"] == "root=<world>\n"
    assert observed["steps"][0]["stdout"] == "<world>/missing\n"
    assert "<world>/missing" in observed["steps"][0]["exception"]["message"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX descriptor-relative scope control")
def test_descriptor_relative_writes_are_unsupported_but_mkstemp_save_works(example):
    sentinel = example / "sentinel"
    sentinel.write_bytes(b"sentinel")
    path = example / "example.py"
    path.write_text(path.read_text() + '''
    def ordinary_save(self):
        import os, tempfile
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as stream:
            stream.write("inside")
        os.replace(path, "saved.txt")
    def descriptor_write(self, directory, name):
        import os
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            fd = os.open(name, os.O_WRONLY, dir_fd=directory_fd)
            try: os.write(fd, b"bad")
            finally: os.close(fd)
        finally: os.close(directory_fd)
    def descriptor_remove(self, directory, name):
        import os
        directory_fd = os.open(directory, os.O_RDONLY)
        try: os.remove(name, dir_fd=directory_fd)
        finally: os.close(directory_fd)
    def descriptor_chmod(self, directory, name):
        import os
        fd = os.open(str(Path(directory) / name), os.O_RDONLY)
        try: os.fchmod(fd, 0o400)
        finally: os.close(fd)
''')
    spec = derive(example)
    saved = replay(spec, [{"name": "ordinary_save"}])
    assert saved["steps"][0]["outcome"] == "success"
    assert any(item[0] == "saved.txt" and item[-1] == "aW5zaWRl" for item in saved["final"]["files"])
    mode = sentinel.stat().st_mode
    for name in ("descriptor_write", "descriptor_remove", "descriptor_chmod"):
        with pytest.raises(UnsupportedWorld, match="descriptor"):
            replay(spec, [{"name": name, "args": [str(example), "sentinel"]}])
        assert sentinel.read_bytes() == b"sentinel"
        assert sentinel.stat().st_mode == mode
