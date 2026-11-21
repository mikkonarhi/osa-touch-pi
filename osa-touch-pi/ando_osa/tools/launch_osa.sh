#!/bin/bash
# Desktop / menu launcher for the OSA touch GUI (used by the "ANDO OSA" menu entry).
# Settings (OSA address, window options) come from ~/.config/ando_osa/launch.conf, written by
# install.sh. Start-up output and errors go to logs/launcher.log (the GUI also logs to logs/gui.log).
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
OSA_ADDRESS=1
GUI_ARGS="--fullscreen"
CONF=${XDG_CONFIG_HOME:-$HOME/.config}/ando_osa/launch.conf
# shellcheck source=/dev/null
[ -f "$CONF" ] && . "$CONF"
echo "=== launcher $(date '+%Y-%m-%d %H:%M:%S') address=$OSA_ADDRESS args=$GUI_ARGS $*" >> logs/launcher.log
# shellcheck disable=SC2086  # GUI_ARGS is a list of options
exec bash tools/run_gui.sh --address "$OSA_ADDRESS" $GUI_ARGS "$@" >> logs/launcher.log 2>&1
