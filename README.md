# Gesture Practice — Krita docker

A docker for timed reference-drawing sessions. Point it at a JSON manifest of
images, optionally filter by tags, and it cycles through poses on a timer —
opening a fresh blank document for each pose so you can draw.

## Architecture

The logic is split so everything except the Qt/Krita UI is unit-testable
without Krita (which can't run headlessly — `import krita` only works *inside*
a running Krita process):

- `gesturepractice/session.py` — pure Python `Session`. No `krita`/Qt imports.
  Loads + validates the manifest, filters by tags (image must contain ALL
  required tags), shuffles (optional seed for determinism), advances with
  wraparound, exposes `current()` / `index` / `total`.
- `gesturepractice/gesture_docker.py` — the `DockWidget`. Qt + Krita only:
  `QTimer`, the scaled reference `QLabel`, Start/Pause/Next/Stop, and
  `createDocument`/`addView`/`close` on advance. All non-UI decisions delegate
  to `Session`. Imports via a PyQt6→PyQt5 shim (Krita 6.0 vs 5.3).
- `gesturepractice/__init__.py` — registers the docker (`DockRight`).
- `gesturepractice.desktop` — the Krita plugin service entry.

## Manifest format

```json
{ "version": 1,
  "images": [ { "path": "/abs/x.jpg", "tags": ["figure","standing"] } ] }
```

Paths should be absolute. A sample manifest + placeholder images live in
`test/fixtures/`.

## Install

```bash
./install.sh
```

Auto-detects Flatpak Krita and installs to
`~/.var/app/org.kde.krita/data/krita/pykrita/`; otherwise uses the native
`~/.local/share/krita/pykrita/`. Override with `PYKRITA_DIR=/path ./install.sh`.
Re-running is safe (it replaces the prior copy).

## Tests

```bash
python -m pytest test/ -q          # session logic + Krita-free docker import
python -m py_compile gesturepractice/*.py
ruff check .
```

## Manual smoke test

`import krita` exists only inside Krita, so the GUI path is verified by hand:

1. Run `./install.sh`.
2. Launch Krita. **Settings → Configure Krita → Python Plugin Manager**, tick
   **Gesture Practice**, click OK.
3. **Restart Krita** (required for newly enabled plugins to load).
4. **Settings → Dockers → Gesture Practice** to show the docker (docks right).
5. Click **Load manifest…** and choose
   `…/gesturepractice/test/fixtures/sample_manifest.json`.
   - Confirm it reports "Loaded 3 poses. Press Start."
6. Click **Start**:
   - the reference image appears in the docker (scaled, aspect kept), and
   - a fresh blank 1080×1080 document opens to draw on.
7. Click **Next**: advances to the next pose — reference changes and a new blank
   document opens (the previous pose's view closes).
8. Wait for the timer (default 60s; lower "Seconds / pose" to e.g. 5 to test
   fast): it **auto-advances** like Next.
9. Click **Pause**: the timer stops (button reads "Resume"); **Resume** restarts
   it. Reaching the last pose and advancing **wraps** back to the first.
10. Click **Stop**: the timer stops, the session clears, the docker shows
    "Session stopped." — no errors in the Python console.

If a reference shows "Missing image", the path in the manifest is wrong or
unreadable; Flatpak Krita here has `filesystems=host` so any absolute path in
your home dir is fine.
