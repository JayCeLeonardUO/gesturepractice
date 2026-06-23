"""Pure-Python logic for the 'recently used folders' list (an MRU).

Like :mod:`gesturepractice.session` this module imports NOTHING from Qt or
krita so the list behaviour can be unit-tested standalone. The docker persists
the list through Krita's settings store as a single newline-separated string;
the (de)serialisation and ordering rules live here.
"""

import os


# How many recent folders we remember and offer as quick-load buttons.
RECENTS_CAP = 8

# Krita settings coordinates (group, key) the docker reads/writes the MRU under.
SETTINGS_GROUP = "gesturePractice"
SETTINGS_KEY = "recentFolders"


def parse_recents(raw):
    """Parse the stored newline-separated string into a list of folder paths.

    Tolerates anything that isn't a non-empty string -- a missing setting, or
    in tests a Krita mock -- by returning an empty list.
    """
    if not isinstance(raw, str):
        return []
    return [line for line in raw.splitlines() if line]


def serialize_recents(recents):
    """Render the MRU list back to a newline-separated string for storage."""
    return "\n".join(recents)


def add_recent(recents, path, cap=RECENTS_CAP):
    """Return a new MRU list with ``path`` promoted to the front.

    The path is normalised, any existing duplicate (compared normalised) is
    dropped, and the result is capped at ``cap`` entries, most-recent first.
    The input list is never mutated.
    """
    norm = os.path.normpath(path)
    out = [norm]
    for p in recents:
        if os.path.normpath(p) != norm:
            out.append(p)
    return out[:cap]


def existing_recents(recents):
    """Filter the MRU list down to folders that still exist on disk."""
    return [p for p in recents if os.path.isdir(p)]
