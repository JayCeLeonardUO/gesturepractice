"""Unit tests for the pure-Python recent-folders (MRU) logic."""

import os
import sys

# Import recent.py directly (not via the package) so we never touch the
# package __init__, which imports krita. This mirrors test_session.py.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gesturepractice"))

from recent import (  # noqa: E402
    RECENTS_CAP,
    parse_recents,
    serialize_recents,
    add_recent,
    existing_recents,
)


def test_parse_skips_blank_lines():
    assert parse_recents("/a\n\n/b\n") == ["/a", "/b"]


def test_parse_non_string_is_empty():
    # A missing setting / Krita mock must not blow up.
    assert parse_recents(None) == []
    assert parse_recents(object()) == []


def test_serialize_roundtrips():
    folders = ["/a", "/b/c"]
    assert parse_recents(serialize_recents(folders)) == folders


def test_add_promotes_to_front():
    assert add_recent(["/a", "/b"], "/b") == ["/b", "/a"]


def test_add_dedupes_normalised():
    # A trailing slash / redundant segment is the same folder.
    assert add_recent(["/a"], "/a/") == ["/a"]
    assert add_recent(["/a"], "/x/../a") == ["/a"]


def test_add_does_not_mutate_input():
    original = ["/a", "/b"]
    add_recent(original, "/c")
    assert original == ["/a", "/b"]


def test_add_caps_length():
    folders = ["/f{}".format(i) for i in range(RECENTS_CAP)]
    result = add_recent(folders, "/new")
    assert len(result) == RECENTS_CAP
    assert result[0] == "/new"
    assert "/f{}".format(RECENTS_CAP - 1) not in result  # oldest dropped


def test_existing_filters_missing(tmp_path):
    real = str(tmp_path)
    missing = os.path.join(real, "does-not-exist")
    assert existing_recents([real, missing]) == [real]
