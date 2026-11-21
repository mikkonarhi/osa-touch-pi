#!/bin/bash
# Launch the touch GUI from the repo without installing.
#   bash tools/run_gui.sh --mock                 # simulator
#   bash tools/run_gui.sh --address 1 --fullscreen
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
# On the Pi's Wayland desktop run Qt natively: only then does pinch zoom get real multi-touch
# (through X11/XWayland every touch arrives as a mouse click). Needs the Qt Wayland plugin
# (sudo apt install qt6-wayland); without it Qt falls back to X11 (xcb) by itself.
if [ -n "$WAYLAND_DISPLAY" ] && [ -z "$QT_QPA_PLATFORM" ]; then
    export QT_QPA_PLATFORM="wayland;xcb"
fi
exec python3 -m ando_osa.gui "$@"
