from pathlib import Path
import json
import runpy

from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.tree import build_tree
from flowguard.map.discover import discover_inventory
from flowguard.map.views import relations, render_show, render_mermaid
from flowguard.map.review import render_review
from flowguard.map.port import escalation_set


def fixture(root):
    base=Path(__file__).resolve().parents[1]/'.flowguard'
    path=base/'target/models/_relation_fixture.py'
    if not path.exists(): path=base/'models/_relation_fixture.py'
    data=runpy.run_path(str(path))['fixture'](root)
    inv=build_inventory(root,DEFAULT_IGNORE,write_cache=False)
    tree=build_tree(root,data,inv)
    raw=discover_inventory(root,inv,data=data,write_cache=False)
    return data,inv,tree,relations(root,data,inv,tree,raw)


def test_three_relation_kinds_are_shown_distinctly(tmp_path):
    data, inv, tree, graph = fixture(tmp_path)
    show = render_show(tmp_path, data, inv, component=None, detail=False)
    mermaid = render_mermaid(tmp_path, data, inv)
    assert "stage children:" in show and "branch children:" in show
    assert "consumes: P.value -> value" in show
    assert "consumes: lending." not in show
    assert ("desk", "lending", "stage") in graph.composition
    assert "m_desk ==> m_lending" in mermaid and "m_desk --> m_lending" not in mermaid
    assert 'm_cmd ==>|"x"| m_a' in mermaid
    assert mermaid.count('m_P --o|"value"| m_K1') == 1
    assert mermaid.splitlines()[1].startswith("  %% edges:")
    # A component-limited diagram still displays consumers across that boundary.
    data["components"][1]["files"]  # real component data remains untouched by rendering
    assert 'm_P --o|"value"| m_K1' in render_mermaid(tmp_path, data, inv, component="extra")


def test_hubs_are_listed_at_the_thresholds(tmp_path):
    data, inv, tree, graph = fixture(tmp_path)
    assert len(graph.callers["Q8"]) == 8 and len(graph.callers["R"]) == 7
    assert graph.hub["P"] and graph.hub["Q8"] and not graph.hub["R"]
    text = render_review(tmp_path, data, inv)
    assert "P (extra): consumed by 2" in text and "Q8 (extra)" in text
    assert "\n  R (extra)" not in text
    from flowguard.map.discover import select_model_functions

    raw = discover_inventory(tmp_path, inv, data=data, write_cache=False)
    assert graph.selects["Q8"] == len(
        select_model_functions(data, inv, tree, raw, {"extra.py#q8"})[0]
    )


def test_ripple_is_the_escalation_set(tmp_path):
    data, inv, tree, graph = fixture(tmp_path)
    ports = {mid: node.contract["port"] for mid, node in tree.nodes.items()}
    assert (
        graph.ripple["T"]
        == escalation_set("T", tree, ports)
        == [("V", "parent"), ("KT", "HANDOFF")]
    )
    assert "ripple 2: V (parent), KT (HANDOFF)" in render_review(tmp_path, data, inv)
    from flowguard.map.port import port_selection, model_port

    old = ports["T"]
    new = model_port(
        (tmp_path / tree.nodes["T"].path).read_text().replace("('ready',)", "('ready','later')")
    )
    chosen, line, _ = port_selection("T", old, new, tree, {**ports, "T": new})
    assert chosen == graph.ripple["T"]
    assert "V (parent)" in line and "KT (HANDOFF)" in line


def test_relations_store_nothing(tmp_path):
    data, inv, tree, graph = fixture(tmp_path)

    def files():
        return {
            str(path.relative_to(tmp_path)): path.read_bytes()
            for path in tmp_path.rglob("*")
            if path.is_file() and ".flowguard/cache/" not in str(path.relative_to(tmp_path))
        }

    before = files()
    render_show(tmp_path, data, inv, component=None, detail=False)
    render_mermaid(tmp_path, data, inv)
    render_review(tmp_path, data, inv)
    assert files() == before


def test_hubs_and_relations_line_always_shown(tmp_path):
    data, inv, tree, graph = fixture(tmp_path)
    review = render_review(tmp_path, data, inv)
    from flowguard.map.views import hub_lines

    assert "\n".join(hub_lines(tree, graph)) in review
    shown = render_show(tmp_path, data, inv, component=None, detail=False)
    assert "\nrelations:" in shown and "truncated" not in shown
