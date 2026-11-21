#!/bin/bash
# Read-only status report of the Pi side of the project. Safe to run any time, no sudo needed
# (a few lines are richer with sudo). Writes logs/pi_check.log next to this repo so it can be
# reviewed remotely.
#
#   bash tools/pi_check.sh
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
LOG=logs/pi_check.log
exec > >(tee "$LOG") 2>&1

sec() { echo; echo "=== $* ==="; }
sec "date / host";      date; hostname; uname -a
sec "model";            tr -d '\0' < /proc/device-tree/model 2>/dev/null; echo
sec "os";               grep -E '^(PRETTY_NAME|VERSION_CODENAME)=' /etc/os-release
sec "kernel headers";   ls -d /lib/modules/"$(uname -r)"/build 2>&1
sec "gpib debs";        dpkg -l | grep -iE 'gpib' || echo "(no gpib packages installed)"
sec "installed .ko";    find /lib/modules/"$(uname -r)" -name 'gpib*.ko*' 2>/dev/null || true
sec "modinfo";          modinfo gpib_bitbang 2>&1 | grep -E '^(filename|version|parm)' ; modinfo gpib_common 2>&1 | grep -E '^filename'
sec "lsmod";            lsmod | grep -iE 'gpib' || echo "(no gpib module loaded)"
sec "modprobe options"; cat /etc/modprobe.d/*gpib* 2>/dev/null || echo "(none)"; cat /etc/modules-load.d/*gpib* 2>/dev/null
sec "/dev/gpib*";       ls -l /dev/gpib* 2>&1 | head -4
sec "groups";           id
sec "gpib-config.service"; systemctl is-active gpib-config.service; systemctl status gpib-config.service --no-pager 2>&1 | tail -6
sec "config path";      ls -l /usr/etc/gpib.conf 2>&1
sec "/etc/gpib.conf";  grep -vE '^\s*(/\*.*\*/)?\s*$' /etc/gpib.conf 2>&1 | grep -vE '^\s*\*' | head -40
sec "dmesg gpib";       (dmesg 2>/dev/null || sudo -n dmesg 2>/dev/null) | grep -iE 'gpib|bitbang' | tail -25 || echo "(dmesg not readable: rerun with sudo)"
sec "gpio";             ls /dev/gpiochip* 2>&1; command -v pinctrl >/dev/null && pinctrl get 2-27 2>/dev/null | head -30
sec "python";           python3 --version
python3 - <<'EOF'
mods = ["Gpib", "gpib", "numpy", "pyqtgraph", "PyQt6", "pytest"]   # GUI uses PyQt6
import importlib
for m in mods:
    try:
        x = importlib.import_module(m)
        print(f"  {m:10s} OK   {getattr(x, '__version__', '')} {getattr(x, '__file__', '')}")
    except Exception as e:
        print(f"  {m:10s} --   {e}")
EOF
sec "display / touch"
echo "XDG_SESSION_TYPE=$XDG_SESSION_TYPE WAYLAND_DISPLAY=$WAYLAND_DISPLAY DISPLAY=$DISPLAY"
for f in /sys/class/drm/*/modes; do [ -s "$f" ] && echo "$f: $(head -1 "$f")"; done
grep -B1 -A4 -iE 'touch|ft5|goodix|ili|ads7846' /proc/bus/input/devices 2>/dev/null | grep -E '^(N|H):' || echo "(no touch device found)"
sec "ando_osa self-test"
python3 -m pytest -q 2>&1 | tail -3
echo; echo "report written to $(pwd)/$LOG"
