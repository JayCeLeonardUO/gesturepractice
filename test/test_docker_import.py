"""Import & drive the Qt-bound docker WITHOUT Krita installed.

We inject fake ``krita`` and ``PyQt5``/``PyQt6`` modules into sys.modules
(MagicMock-based) before importing the docker, then confirm the class
constructs and that advancing drives the underlying real Session. We do NOT
assert on real Qt behaviour.
"""

import importlib
import os
import sys
import types
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

QT_SUBMODULES = ("QtWidgets", "QtCore", "QtGui")


def _make_fake_krita():
    mod = types.ModuleType("krita")

    # DockWidget must be a REAL class so GestureDocker can subclass it; any
    # unknown method call (setWidget, setWindowTitle, ...) returns a mock.
    class DockWidget:
        def __init__(self, *a, **k):
            pass

        def __getattr__(self, name):
            return MagicMock()

    mod.DockWidget = DockWidget
    mod.Krita = MagicMock(name="Krita")
    mod.InfoObject = MagicMock(name="InfoObject")
    mod.DockWidgetFactory = MagicMock(name="DockWidgetFactory")
    mod.DockWidgetFactoryBase = MagicMock(name="DockWidgetFactoryBase")
    return mod


def _make_fake_qt(prefix):
    pkg = types.ModuleType(prefix)
    mods = {prefix: pkg}
    for sub in QT_SUBMODULES:
        m = types.ModuleType(prefix + "." + sub)
        # Every Qt symbol the docker pulls in becomes a MagicMock factory.
        m.__getattr__ = lambda name: MagicMock(name=name)  # noqa: B023
        setattr(pkg, sub, m)
        mods[prefix + "." + sub] = m
    return mods


def _install_fakes(qt_prefix):
    """Install fakes for one Qt binding, removing the other so the shim picks it."""
    other = "PyQt5" if qt_prefix == "PyQt6" else "PyQt6"
    for name in list(sys.modules):
        if name == other or name.startswith(other + "."):
            del sys.modules[name]
    sys.modules["krita"] = _make_fake_krita()
    sys.modules.update(_make_fake_qt(qt_prefix))
    # Force a fresh import of the docker against these fakes.
    sys.modules.pop("gesturepractice.gesture_docker", None)
    return importlib.import_module("gesturepractice.gesture_docker")


def _make_image_dir(tmp_path):
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        (tmp_path / name).write_bytes(b"")
    return str(tmp_path)


@pytest.mark.parametrize("qt_prefix", ["PyQt6", "PyQt5"])
def test_docker_imports_and_constructs(qt_prefix):
    mod = _install_fakes(qt_prefix)
    docker = mod.GestureDocker()
    assert docker is not None
    assert docker._session is None  # nothing loaded yet


@pytest.mark.parametrize("qt_prefix", ["PyQt6", "PyQt5"])
def test_advance_drives_session(qt_prefix, tmp_path):
    mod = _install_fakes(qt_prefix)
    docker = mod.GestureDocker()

    ok = docker.load_directory(_make_image_dir(tmp_path), seed=0)
    assert ok is True
    assert docker._session is not None
    assert docker._session.total == 3

    start_index = docker._session.index
    docker.advance()
    assert docker._session.index == (start_index + 1) % 3

    # advance through wraparound
    docker.advance()
    docker.advance()
    assert docker._session.index == start_index


@pytest.mark.parametrize("qt_prefix", ["PyQt6", "PyQt5"])
def test_load_records_recent_folder(qt_prefix, tmp_path):
    mod = _install_fakes(qt_prefix)
    docker = mod.GestureDocker()
    assert docker._recents == []  # nothing remembered yet (Krita mock => empty)

    folder = _make_image_dir(tmp_path)
    docker.load_directory(folder, seed=0)
    assert os.path.normpath(folder) in docker._recents


@pytest.mark.parametrize("qt_prefix", ["PyQt6", "PyQt5"])
def test_load_empty_dir_is_safe(qt_prefix, tmp_path):
    mod = _install_fakes(qt_prefix)
    docker = mod.GestureDocker()
    empty = tmp_path / "empty"
    empty.mkdir()
    ok = docker.load_directory(str(empty))  # no images inside
    assert ok is False
    assert docker._session is None  # stays unloaded, no exception escapes
