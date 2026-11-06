"""Incremental code-owned structure; queries never execute project functions."""

from .paths import project_code

__all__ = ["build", "project_code"]

def build(root, store_path=None, **options):
    from .api import build as build_map
    return build_map(root, store_path, **options)
