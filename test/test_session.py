"""Unit tests for the pure-Python Session. No Krita required."""

import json
import os
import sys

import pytest

# Import session.py directly (not via the package) so we never touch the
# package __init__, which imports krita. This is exactly the Krita-free path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gesturepractice"))

from session import Session, ManifestError  # noqa: E402


def _manifest(images):
    return {"version": 1, "images": images}


def _sample_images():
    return [
        {"path": "/a.jpg", "tags": ["figure", "standing"]},
        {"path": "/b.jpg", "tags": ["figure", "seated"]},
        {"path": "/c.jpg", "tags": ["hands"]},
        {"path": "/d.jpg", "tags": ["figure", "standing", "dynamic"]},
    ]


def _write(tmp_path, data):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


# -- tag filtering ----------------------------------------------------------

def test_filter_requires_all_tags():
    s = Session(_sample_images(), required_tags=["figure", "standing"])
    assert sorted(s.paths) == ["/a.jpg", "/d.jpg"]


def test_empty_filter_returns_all():
    s = Session(_sample_images())
    assert s.total == 4


def test_filter_single_tag():
    s = Session(_sample_images(), required_tags=["hands"])
    assert s.paths == ["/c.jpg"]


# -- shuffle determinism ----------------------------------------------------

def test_seeded_shuffle_is_reproducible():
    a = Session(_sample_images(), seed=42).paths
    b = Session(_sample_images(), seed=42).paths
    assert a == b


def test_different_seeds_differ():
    a = Session(_sample_images(), seed=1).paths
    b = Session(_sample_images(), seed=999).paths
    assert a != b


def test_shuffle_preserves_all_items():
    s = Session(_sample_images(), seed=7)
    assert sorted(s.paths) == ["/a.jpg", "/b.jpg", "/c.jpg", "/d.jpg"]


def test_shuffle_does_not_mutate_input():
    imgs = _sample_images()
    original = [i["path"] for i in imgs]
    Session(imgs, seed=3)
    assert [i["path"] for i in imgs] == original


# -- navigation -------------------------------------------------------------

def test_next_advances_and_wraps():
    s = Session(_sample_images(), seed=0)
    order = s.paths
    assert s.index == 0
    assert s.current()["path"] == order[0]
    assert s.next()["path"] == order[1]
    assert s.index == 1
    s.next()
    s.next()
    assert s.index == 3
    # wrap from last back to first
    assert s.next()["path"] == order[0]
    assert s.index == 0


def test_total_and_index():
    s = Session(_sample_images(), required_tags=["figure"], seed=5)
    assert s.total == 3
    assert 0 <= s.index < s.total


def test_reset():
    s = Session(_sample_images(), seed=0)
    s.next()
    s.next()
    assert s.index == 2
    s.reset()
    assert s.index == 0


# -- malformed manifests ----------------------------------------------------

def test_missing_file_raises(tmp_path):
    with pytest.raises(ManifestError):
        Session.from_manifest(str(tmp_path / "nope.json"))


def test_bad_json_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ManifestError):
        Session.from_manifest(str(p))


def test_wrong_version_raises(tmp_path):
    path = _write(tmp_path, {"version": 2, "images": _sample_images()})
    with pytest.raises(ManifestError):
        Session.from_manifest(path)


def test_missing_images_key_raises(tmp_path):
    path = _write(tmp_path, {"version": 1})
    with pytest.raises(ManifestError):
        Session.from_manifest(path)


def test_empty_images_raises(tmp_path):
    path = _write(tmp_path, {"version": 1, "images": []})
    with pytest.raises(ManifestError):
        Session.from_manifest(path)


def test_entry_missing_path_raises(tmp_path):
    path = _write(tmp_path, {"version": 1, "images": [{"tags": ["x"]}]})
    with pytest.raises(ManifestError):
        Session.from_manifest(path)


def test_malformed_tags_raises(tmp_path):
    path = _write(tmp_path, {"version": 1,
                             "images": [{"path": "/a.jpg", "tags": "figure"}]})
    with pytest.raises(ManifestError):
        Session.from_manifest(path)


def test_empty_after_filter_raises():
    with pytest.raises(ManifestError):
        Session(_sample_images(), required_tags=["nonexistent"])


def test_not_an_object_raises(tmp_path):
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ManifestError):
        Session.from_manifest(str(p))


# -- end-to-end load --------------------------------------------------------

def test_from_manifest_roundtrip(tmp_path):
    path = _write(tmp_path, _manifest(_sample_images()))
    s = Session.from_manifest(path, required_tags=["figure"], seed=1)
    assert s.total == 3
    assert all("figure" in img["tags"] for img in s._images)
