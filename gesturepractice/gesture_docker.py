"""Qt + Krita docker for Gesture Practice.

This file holds ALL Qt/krita work. Every non-UI decision is delegated to the
pure-Python :class:`~gesturepractice.session.Session`.

Qt version shim
---------------
Krita 5.3 ships PyQt5; Krita 6.0 ships PyQt6. We try PyQt6 first, fall back to
PyQt5, and normalise the one ergonomic difference we touch: in PyQt6 enums are
scoped (``Qt.AlignmentFlag.AlignCenter``, ``Qt.AspectRatioMode.KeepAspectRatio``,
``QTimer`` is unchanged) whereas in PyQt5 they are flat (``Qt.AlignCenter``,
``Qt.KeepAspectRatio``). We resolve the few flags we need into module-level
constants so the widget code is binding-agnostic.
"""

try:  # Krita 6.0
    from PyQt6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSpinBox,
        QCheckBox,
        QFileDialog,
    )
    from PyQt6.QtCore import QTimer, Qt
    from PyQt6.QtGui import QPixmap

    _ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
    _KEEP_ASPECT = Qt.AspectRatioMode.KeepAspectRatio
    _SMOOTH = Qt.TransformationMode.SmoothTransformation
except ImportError:  # Krita 5.3
    from PyQt5.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSpinBox,
        QCheckBox,
        QFileDialog,
    )
    from PyQt5.QtCore import QTimer, Qt
    from PyQt5.QtGui import QPixmap

    _ALIGN_CENTER = Qt.AlignCenter
    _KEEP_ASPECT = Qt.KeepAspectRatio
    _SMOOTH = Qt.SmoothTransformation

import os

from krita import DockWidget, Krita, InfoObject

from .session import Session, ManifestError

DOCKER_ID = "gesturePractice"
DOCKER_TITLE = "Gesture Practice"


class GestureDocker(DockWidget):
    """Krita docker that runs a timed reference-drawing session."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(DOCKER_TITLE)

        self._session = None
        self._folder_path = None
        self._output_dir = None  # where auto-saved JPGs go
        self._view = None  # the Krita view we opened for the current pose

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        self._build_ui()
        self._refresh_controls()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self):
        root = QWidget(self)
        layout = QVBoxLayout(root)

        self._image_label = QLabel("No folder loaded.")
        self._image_label.setAlignment(_ALIGN_CENTER)
        self._image_label.setMinimumSize(200, 200)
        self._image_label.setScaledContents(False)
        layout.addWidget(self._image_label, stretch=1)

        self._status_label = QLabel("")
        self._status_label.setAlignment(_ALIGN_CENTER)
        layout.addWidget(self._status_label)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Seconds / pose:"))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(5, 3600)
        self._interval_spin.setValue(60)
        interval_row.addWidget(self._interval_spin)
        layout.addLayout(interval_row)

        self._load_btn = QPushButton("Load folder…")
        self._load_btn.clicked.connect(self._on_load)
        layout.addWidget(self._load_btn)

        self._autosave_check = QCheckBox("Auto-save each pose as JPG")
        self._autosave_check.toggled.connect(self._on_autosave_toggled)
        layout.addWidget(self._autosave_check)

        self._output_btn = QPushButton("Auto-save folder…")
        self._output_btn.clicked.connect(self._on_choose_output)
        layout.addWidget(self._output_btn)

        button_row = QHBoxLayout()
        self._start_btn = QPushButton("Start")
        self._pause_btn = QPushButton("Pause")
        self._next_btn = QPushButton("Next")
        self._stop_btn = QPushButton("Stop")
        self._start_btn.clicked.connect(self._on_start)
        self._pause_btn.clicked.connect(self._on_pause)
        self._next_btn.clicked.connect(self._on_next)
        self._stop_btn.clicked.connect(self._on_stop)
        for btn in (self._start_btn, self._pause_btn, self._next_btn, self._stop_btn):
            button_row.addWidget(btn)
        layout.addLayout(button_row)

        self.setWidget(root)

    # -- Krita hook ---------------------------------------------------------

    def canvasChanged(self, canvas):
        # Required by the DockWidget interface; nothing to do here.
        pass

    # -- button handlers ----------------------------------------------------

    def _on_load(self):
        path = QFileDialog.getExistingDirectory(
            self.widget(), "Choose a folder of reference images", ""
        )
        if path:
            self.load_directory(path)

    def _on_choose_output(self):
        path = QFileDialog.getExistingDirectory(
            self.widget(), "Choose a folder to auto-save drawings into", ""
        )
        if path:
            self._output_dir = path
            self._status_label.setText("Auto-save folder: {}".format(path))

    def _on_autosave_toggled(self, checked):
        # Turning auto-save on without a destination: prompt for one now.
        if checked and not self._output_dir:
            self._on_choose_output()
            if not self._output_dir:
                self._autosave_check.setChecked(False)

    def _on_start(self):
        if self._session is None:
            self._status_label.setText("Load a folder first.")
            return
        self._show_current()
        self._timer.start(self._interval_spin.value() * 1000)
        self._refresh_controls()

    def _on_pause(self):
        if self._timer.isActive():
            self._timer.stop()
        elif self._session is not None:
            self._timer.start(self._interval_spin.value() * 1000)
        self._refresh_controls()

    def _on_next(self):
        self.advance()

    def _on_stop(self):
        self._timer.stop()
        self._close_view()
        self._session = None
        self._image_label.setText("Session stopped.")
        self._status_label.setText("")
        self._refresh_controls()

    def _on_tick(self):
        self.advance()

    # -- session-driven logic ----------------------------------------------

    def load_directory(self, path, seed=None):
        """Scan a folder for images and build a Session. UI-safe (no throw)."""
        try:
            self._session = Session.from_directory(path, seed=seed)
        except ManifestError as exc:
            self._session = None
            self._status_label.setText(str(exc))
            self._image_label.setText("Failed to load folder.")
            self._refresh_controls()
            return False
        self._folder_path = path
        self._image_label.setText("Loaded {} poses. Press Start.".format(
            self._session.total))
        self._refresh_controls()
        return True

    def advance(self):
        """Advance the Session one pose and refresh canvas + reference."""
        if self._session is None:
            return
        self._session.next()
        self._show_current()

    def _show_current(self):
        """Open a fresh blank document for drawing and display the reference."""
        if self._session is None:
            return
        entry = self._session.current()
        self._new_document(self._doc_name_for(entry["path"]))
        self._set_reference_pixmap(entry["path"])
        self._status_label.setText(
            "Pose {}/{}".format(self._session.index + 1, self._session.total)
        )

    def _set_reference_pixmap(self, path):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._image_label.setText("Missing image:\n{}".format(path))
            return
        scaled = pixmap.scaled(
            self._image_label.size(), _KEEP_ASPECT, _SMOOTH
        )
        self._image_label.setPixmap(scaled)

    # -- Krita document lifecycle ------------------------------------------

    @staticmethod
    def _doc_name_for(ref_path):
        """Derive a drawing name from the reference image's file name.

        ``/refs/standing_01.jpg`` -> ``standing_01``. The save dialog defaults
        to the document name, so the saved study auto-suggests this name.
        """
        base = os.path.basename(ref_path)
        stem = os.path.splitext(base)[0]
        return stem or "Gesture pose"

    def _new_document(self, name="Gesture pose"):
        """Close the previous pose's view and create a fresh blank canvas.

        ``name`` becomes the document name, which Krita's Save dialog uses as
        the default file name.
        """
        self._close_view()
        app = Krita.instance()
        doc = app.createDocument(
            1080, 1080, name, "RGBA", "U8", "", 300.0
        )
        # createDocument's name arg isn't always honoured for the save default;
        # setName() reliably drives the Save dialog's suggested file name.
        doc.setName(name)
        # Batch mode suppresses Krita's dialogs for this document: both the
        # JPEG export-options popup and the "save changes before closing?"
        # prompt we'd otherwise hit every time we swap to the next pose.
        doc.setBatchmode(True)
        app.activeWindow().addView(doc)
        self._view = doc

    def _close_view(self):
        if self._view is not None:
            self._autosave_view()
            try:
                self._view.close()
            except Exception:
                pass
            self._view = None

    def _autosave_view(self):
        """Export the current drawing to the output folder as a JPG.

        Named after the document (i.e. the reference image). A numeric suffix
        is added if a file of that name already exists so nothing is clobbered.
        Only a JPG is written — never the .kra working file. No-op unless
        auto-save is enabled and an output folder is set.
        """
        if not self._autosave_check.isChecked() or not self._output_dir:
            return
        doc = self._view
        if doc is None:
            return
        stem = doc.name() or "pose"
        target = self._unique_path(self._output_dir, stem, ".jpg")
        try:
            doc.setBatchmode(True)  # suppress the JPEG export options dialog
            doc.exportImage(target, InfoObject())  # extension drives JPG format
        except Exception as exc:
            self._status_label.setText("Auto-save failed: {}".format(exc))

    @staticmethod
    def _unique_path(folder, stem, ext):
        """Return a path in ``folder`` that does not yet exist on disk."""
        candidate = os.path.join(folder, stem + ext)
        n = 1
        while os.path.exists(candidate):
            candidate = os.path.join(folder, "{}_{}{}".format(stem, n, ext))
            n += 1
        return candidate

    # -- control state ------------------------------------------------------

    def _refresh_controls(self):
        has_session = self._session is not None
        running = self._timer.isActive()
        self._start_btn.setEnabled(has_session and not running)
        self._pause_btn.setEnabled(has_session)
        self._next_btn.setEnabled(has_session)
        self._stop_btn.setEnabled(has_session)
        self._pause_btn.setText("Pause" if running else "Resume")
