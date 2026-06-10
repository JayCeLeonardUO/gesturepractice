"""Gesture Practice — a Krita docker for timed reference-drawing sessions."""

from krita import Krita, DockWidgetFactory, DockWidgetFactoryBase

from .gesture_docker import GestureDocker, DOCKER_ID

# Krita 6.0 (PyQt6) scopes the enum as DockPosition.DockRight; Krita 5.3
# (PyQt5) exposes it flat as DockRight. Resolve whichever exists.
_pos = getattr(DockWidgetFactoryBase, "DockPosition", DockWidgetFactoryBase)
_DOCK_RIGHT = _pos.DockRight

Krita.instance().addDockWidgetFactory(
    DockWidgetFactory(DOCKER_ID, _DOCK_RIGHT, GestureDocker)
)
