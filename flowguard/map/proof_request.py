"""Serialize fresh model-view and port inputs for one subprocess call."""

from __future__ import annotations
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def _view_request(view, port_request=None):
    if view is None and port_request is None:
        yield []
        return
    with tempfile.TemporaryDirectory(prefix="flowguard-model-view-") as directory:
        path = Path(directory) / "view.json"
        payload = {
            "view": view.to_payload() if view is not None else None,
            "port_request": port_request,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        yield [str(path)]


def _port_request(tree, model_id, *, shared=None):
    """The parent shares already parsed ports and the tree's location metadata."""
    from .port import Port, port_to_payload

    if shared is None:
        shared = {
            "ports": {
                mid: port_to_payload(node.contract.get("port", Port()))
                for mid, node in tree.nodes.items()
            },
            "nodes": {
                mid: {
                    "path": node.path,
                    "kind": node.kind,
                    "parent": node.parent,
                    "parent_kind": node.parent_kind,
                }
                for mid, node in tree.nodes.items()
            },
        }
    node = tree.nodes[model_id]
    return {
        **shared,
        "children": [child.id for child in tree.children(model_id, "model")],
        "path": node.path,
        "parent_kind": node.parent_kind,
    }
