"""Pure-Python session logic for the Gesture Practice plugin.

This module deliberately imports NOTHING from ``krita`` or any Qt binding so
that it can be unit-tested without Krita. All non-UI decisions (manifest
parsing, tag filtering, shuffling, advancing) live here; the docker is a thin
Qt/krita shell on top.
"""

import json
import os
import random


# Image extensions Krita/QPixmap can load as reference. Lower-case, with dot.
IMAGE_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff",
)


class ManifestError(ValueError):
    """Raised when a manifest is missing, malformed, or yields no images."""


class Session:
    """A timed reference-drawing session over a filtered list of images.

    Construct via :meth:`from_manifest` (or :meth:`from_dict`). After
    construction the session holds a shuffled, tag-filtered list of image
    entries and tracks a current index that wraps around on ``next()``.
    """

    def __init__(self, images, required_tags=None, seed=None):
        """Build a session from already-loaded ``images``.

        ``images`` is a list of dicts each with at least ``path`` (str) and
        ``tags`` (list of str). ``required_tags`` keeps only images containing
        ALL of them (empty/None => keep all). ``seed`` makes the shuffle
        deterministic.
        """
        required = set(required_tags or [])
        filtered = [img for img in images if required.issubset(set(img.get("tags", [])))]
        if not filtered:
            raise ManifestError(
                "No images match the required tags: {}".format(sorted(required))
            )
        # Copy so shuffling never mutates the caller's list.
        self._images = list(filtered)
        random.Random(seed).shuffle(self._images)
        self._index = 0

    # -- constructors -------------------------------------------------------

    @classmethod
    def from_dict(cls, data, required_tags=None, seed=None):
        """Validate a parsed manifest ``dict`` and build a session."""
        if not isinstance(data, dict):
            raise ManifestError("Manifest must be a JSON object.")
        if data.get("version") != 1:
            raise ManifestError(
                "Unsupported or missing manifest version (expected 1)."
            )
        images = data.get("images")
        if not isinstance(images, list) or not images:
            raise ManifestError("Manifest 'images' must be a non-empty list.")
        for i, img in enumerate(images):
            if not isinstance(img, dict):
                raise ManifestError("Image entry {} is not an object.".format(i))
            if not isinstance(img.get("path"), str) or not img["path"]:
                raise ManifestError("Image entry {} is missing a 'path'.".format(i))
            tags = img.get("tags", [])
            if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
                raise ManifestError(
                    "Image entry {} has malformed 'tags'.".format(i)
                )
        return cls(images, required_tags=required_tags, seed=seed)

    @classmethod
    def from_manifest(cls, path, required_tags=None, seed=None):
        """Load a manifest from ``path`` on disk and build a session."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as exc:
            raise ManifestError("Cannot read manifest: {}".format(exc)) from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ManifestError("Manifest is not valid JSON: {}".format(exc)) from exc
        return cls.from_dict(data, required_tags=required_tags, seed=seed)

    @classmethod
    def from_directory(cls, path, recursive=True, seed=None):
        """Build a session from every image file found under ``path``.

        Scans ``path`` for files with a known image extension (see
        :data:`IMAGE_EXTENSIONS`). When ``recursive`` is true, subdirectories
        are walked too. Images carry no tags, so tag filtering does not apply.
        Raises :class:`ManifestError` if the path is not a directory or
        contains no images.
        """
        if not os.path.isdir(path):
            raise ManifestError("Not a directory: {}".format(path))

        paths = []
        if recursive:
            for root, _dirs, files in os.walk(path):
                for name in files:
                    if name.lower().endswith(IMAGE_EXTENSIONS):
                        paths.append(os.path.join(root, name))
        else:
            for name in os.listdir(path):
                full = os.path.join(path, name)
                if os.path.isfile(full) and name.lower().endswith(IMAGE_EXTENSIONS):
                    paths.append(full)

        if not paths:
            raise ManifestError("No images found in: {}".format(path))

        paths.sort()
        images = [{"path": p, "tags": []} for p in paths]
        return cls(images, seed=seed)

    # -- navigation ---------------------------------------------------------

    def current(self):
        """Return the current image entry dict."""
        return self._images[self._index]

    def next(self):
        """Advance to the next image, wrapping from last back to first.

        Returns the new current entry.
        """
        self._index = (self._index + 1) % len(self._images)
        return self.current()

    def reset(self):
        """Jump back to the first image of the (already shuffled) order."""
        self._index = 0
        return self.current()

    # -- introspection ------------------------------------------------------

    @property
    def index(self):
        """Zero-based position of the current image."""
        return self._index

    @property
    def total(self):
        """Number of images in the session after filtering."""
        return len(self._images)

    @property
    def paths(self):
        """All image paths in current (shuffled) order."""
        return [img["path"] for img in self._images]
