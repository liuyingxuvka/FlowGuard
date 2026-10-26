"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_target_add_keeps_untracked_model(tmp_path):
    from _fg_helpers import target__fg403_add_case as _fg403_add_case
    _fg403_add_case(tmp_path, "untracked")


def test_target_add_after_uncommitted_promote_copies(tmp_path):
    from _fg_helpers import target__fg403_add_case as _fg403_add_case
    _fg403_add_case(tmp_path, "promoted")


def test_target_add_moves_in_place_edit_of_committed_model(tmp_path):
    from _fg_helpers import target__fg403_add_case as _fg403_add_case
    _fg403_add_case(tmp_path, "dirty")
