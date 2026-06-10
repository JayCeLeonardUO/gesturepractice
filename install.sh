#!/usr/bin/env bash
# Install the Gesture Practice plugin into Krita's pykrita directory.
#
# Idempotent: re-running overwrites the previously installed copy.
# Auto-detects a Flatpak Krita install and uses its sandboxed resource path;
# otherwise falls back to the native ~/.local/share location. Override either
# with:  PYKRITA_DIR=/some/path ./install.sh
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE="gesturepractice"

FLATPAK_PYKRITA="$HOME/.var/app/org.kde.krita/data/krita/pykrita"
NATIVE_PYKRITA="$HOME/.local/share/krita/pykrita"

if [[ -n "${PYKRITA_DIR:-}" ]]; then
    DEST="$PYKRITA_DIR"
elif flatpak info org.kde.krita >/dev/null 2>&1; then
    DEST="$FLATPAK_PYKRITA"
    echo "Detected Flatpak Krita -> $DEST"
else
    DEST="$NATIVE_PYKRITA"
    echo "Using native Krita path -> $DEST"
fi

mkdir -p "$DEST"

# Remove any prior install so renamed/deleted files don't linger.
rm -rf "${DEST:?}/${PACKAGE}" "${DEST}/${PACKAGE}.desktop"

cp -r "$SRC_DIR/$PACKAGE" "$DEST/$PACKAGE"
cp "$SRC_DIR/$PACKAGE.desktop" "$DEST/$PACKAGE.desktop"

# Don't ship dev/test artifacts into the live plugin dir.
rm -rf "$DEST/$PACKAGE/__pycache__"

echo "Installed:"
echo "  $DEST/$PACKAGE.desktop"
echo "  $DEST/$PACKAGE/"
echo
echo "Next: launch Krita -> Settings > Configure Krita > Python Plugin Manager,"
echo "enable \"Gesture Practice\", then restart Krita."
