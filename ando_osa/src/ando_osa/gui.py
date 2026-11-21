"""Touch-screen front end for the ANDO AQ6315 / AQ6317 OSAs (Raspberry Pi + GPIB4PI).

    python3 -m ando_osa.gui --mock                 # simulator, windowed
    python3 -m ando_osa.gui --address 1 --fullscreen
    python3 -m ando_osa.gui --mock --screenshot shot.png   # render one frame and exit (CI / docs)

Design notes
  * every GPIB call runs on one worker thread (GpibWorker) so the UI never freezes; calls are
    serialised through a queue, which also matches GPIB being a single shared bus.
  * big touch targets (>= 56 px), numeric entry via an on-screen keypad, no keyboard needed.
  * "REPEAT" is done as a GUI loop of single sweeps (SGL + wait + read), because the instrument's
    own RPT mode gives no per-sweep completion signal to read the trace on.
  * Qt binding comes through pyqtgraph.Qt, so PyQt6 (apt: python3-pyqt6), PyQt5 or PySide6 all work.
  * status / marker lines are ElidedLabels: long text (file paths, error messages) is shortened
    with "…" instead of widening the layout, which on the 800 px screen pushed the button column
    off-screen.
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import logging
import logging.handlers
import os
import queue
import re
import shutil
import sys
import threading
import time
import traceback

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from . import LinuxGpibTransport, MockTransport, Osa
from .errors import OsaError, OsaTimeout
from .commands import COMMANDS
from .simulator import SimOsa

GUI_VERSION = "2026-11-19f"       # shown in the status line at start-up and in logs/gui.log

# logs/gui.log next to src/: GPIB traffic, errors, touch/mouse events on the plot, input devices
LOG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs", "gui.log"))
log = logging.getLogger("ando_osa.gui")
NO_DATA_DBM = -200.0              # AQ6317B reports -210 dBm for points below its measuring range
FLOOR_MARGIN_DB = 3.0             # such points are drawn as dips to a floor this far below the data
REPEAT_POLL_MS = 50               # pause between REPEAT poll jobs
REPEAT_STB_POLL_S = 0.1           # serial-poll interval while waiting for the sweep-end bit
REPEAT_READ_TIMEOUT_S = 120.0     # GPIB timeout for trace reads in REPEAT


def setup_log():
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        h = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=2)
    except OSError:
        return
    h.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(message)s", "%H:%M:%S"))
    log.addHandler(h)
    log.setLevel(logging.INFO)


def trace_transport(t):
    """Log every GPIB write/read (long replies shortened) and non-zero serial polls."""
    w, r, sp = t.write, t.read, t.serial_poll

    def write(text):
        log.info("> %s", text)
        w(text)

    def read():
        try:
            txt = r()
        except Exception as e:  # noqa: BLE001
            log.info("< ERROR %s: %s", type(e).__name__, e)
            raise
        log.info("< %s", txt if len(txt) <= 120 else f"{txt[:100]} ... ({len(txt)} chars)")
        return txt

    def serial_poll():
        v = sp()
        if v:
            log.info("stb %#04x", v)
        return v

    t.write, t.read, t.serial_poll = write, read, serial_poll

Signal = getattr(QtCore, "Signal", None) or QtCore.pyqtSignal

BG, PANEL, ACCENT, TEXT, MUTED, WARN = "#11161c", "#1b232c", "#3fb5ff", "#e8eef4", "#8a97a6", "#ff8a4c"
TRACE_COLORS = {"A": "#ffd23f", "B": "#ff6ad5", "C": "#5fe08a"}
TRACE_COLOR = TRACE_COLORS["A"]
LINE_MARKER_COLOR = "#b98cff"     # L1 / L2 line markers
# linear display units: name, factor from mW, OSA unit code (REFL? prefix / REFLx setter)
LIN_UNITS = [("mW", 1.0, "MW"), ("µW", 1e3, "UW"), ("nW", 1e6, "NW"), ("pW", 1e9, "PW")]
LIN_SETTER = {"MW": "ref_level_mw", "UW": "ref_level_uw", "NW": "ref_level_nw", "PW": "ref_level_pw"}

STYLE = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-size: 17px; }}
QPushButton {{ background: {PANEL}; border: 1px solid #2c3743; border-radius: 10px;
              min-height: 54px; padding: 2px 8px; font-weight: 600; }}
QPushButton:pressed {{ background: #24303c; border-color: {ACCENT}; }}
QPushButton:disabled {{ color: #4d5966; }}
QPushButton#primary {{ background: {ACCENT}; color: #04121d; border: none; }}
QPushButton#primary:pressed {{ background: #2a8fcc; }}
QPushButton#stop {{ background: #3a1f1a; border-color: {WARN}; color: {WARN}; }}
QPushButton#tile {{ text-align: left; padding: 6px 8px; font-size: 15px; }}
QLabel#status {{ color: {MUTED}; font-size: 14px; }}
QPushButton#row4 {{ padding: 2px 2px; font-size: 15px; }}
QLabel#meas {{ background: rgba(17, 22, 28, 225); border: 1px solid {ACCENT}; border-radius: 6px;
              padding: 2px 6px; font-size: 13px; color: {TEXT}; }}
QLabel#readout {{ font-size: 19px; font-weight: 600; color: {TRACE_COLOR}; }}
QDialog {{ background: {BG}; }}
QLineEdit {{ background: {PANEL}; border: 1px solid #2c3743; border-radius: 8px; font-size: 28px;
            min-height: 56px; padding: 0 10px; }}
QPushButton#loc {{ min-height: 46px; font-size: 15px; }}
QPushButton#loc:checked {{ border: 2px solid {ACCENT}; color: {ACCENT}; }}
QPushButton#small {{ min-height: 30px; max-height: 30px; font-size: 14px; padding: 0 10px; border-radius: 8px; }}
QPushButton#small:checked {{ border: 2px solid {ACCENT}; color: {ACCENT}; }}
QLabel#rowlabel {{ color: {MUTED}; font-size: 15px; }}
QPushButton#key {{ min-height: 40px; padding: 0; font-size: 18px; border-radius: 6px; }}
QLineEdit#name {{ font-size: 22px; min-height: 44px; }}
"""


# ============================================================================ elided label
class ElidedLabel(QtWidgets.QLabel):
    """Single-line label that never asks for more width than it is given.

    A plain QLabel's minimum width is its full text width, so a long status message (e.g. the
    saved file path) widened the plot column and pushed the fixed-width button column
    off-screen. This one shortens the text with "…" in the middle instead; the full text is
    kept in text() and shown as a tooltip.
    """

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)

    def setText(self, text):
        super().setText(text)
        self.setToolTip(text)

    def minimumSizeHint(self):
        return QtCore.QSize(0, super().minimumSizeHint().height())

    def sizeHint(self):
        return QtCore.QSize(0, super().sizeHint().height())

    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        r = self.contentsRect()
        t = self.fontMetrics().elidedText(self.text(), QtCore.Qt.TextElideMode.ElideMiddle, r.width())
        self.style().drawItemText(p, r, self.alignment() | QtCore.Qt.AlignmentFlag.AlignVCenter,
                                  self.palette(), self.isEnabled(), t, QtGui.QPalette.ColorRole.WindowText)
        p.end()


# ============================================================================ touch zoom / pan
class TouchNav(QtCore.QObject):
    """Finger navigation for a pyqtgraph PlotWidget (pyqtgraph itself only handles the mouse).

    one finger drag   -> pan
    two-finger pinch  -> zoom; spreading the fingers horizontally zooms wavelength, vertically
                         zooms level, diagonally both
    short tap         -> `tapped(scene_pos)` (used for the marker)

    Accepting the touch events stops Qt from also turning them into mouse events, so pyqtgraph's
    own mouse pan/zoom (still active for a real mouse or wheel) does not act twice.
    """
    tapped = Signal(object)

    TAP_MOVE_PX = 12        # finger movement below this still counts as a tap
    TAP_TIME_S = 0.6
    MIN_AXIS_SPREAD_PX = 40  # fingers closer than this along an axis do not zoom that axis

    def __init__(self, plot: pg.PlotWidget):
        super().__init__(plot)
        self.plot, self.vb = plot, plot.plotItem.vb
        vp = plot.viewport()
        vp.setAttribute(QtCore.Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        vp.installEventFilter(self)
        self._prev: dict = {}
        self._start = None
        self._t0 = 0.0
        self._moved = False
        self._max_fingers = 0
        self._pans = self._pinches = 0
        self.passthrough = False     # True in box-zoom mode: Qt turns the touch into a mouse drag

    def _view(self, p: QtCore.QPointF) -> QtCore.QPointF:
        return self.vb.mapSceneToView(self.plot.mapToScene(p.toPoint()))

    def eventFilter(self, obj, ev):
        T = QtCore.QEvent.Type
        t = ev.type()
        if t == T.MouseButtonPress:
            # if the touch screen only ever shows up here, it reaches Qt as a mouse (no pinch possible)
            log.info("plot: mouse press from %s (%s)", ev.pointingDevice().name(), ev.pointingDevice().type().name)
            return False
        if t not in (T.TouchBegin, T.TouchUpdate, T.TouchEnd, T.TouchCancel) or self.passthrough:
            return False
        released = QtGui.QEventPoint.State.Released
        # local position from the global one: always filled in (position() can be empty in
        # synthesised events), and the viewport is what the event filter watches
        active = {p.id(): obj.mapFromGlobal(p.globalPosition()) for p in ev.points() if p.state() != released}
        if t == T.TouchBegin:
            self._prev, self._t0, self._moved = active, time.monotonic(), False
            self._start = next(iter(active.values()), None)
            self._max_fingers = len(active)
            self._pans = self._pinches = 0
            log.info("plot: touch begin, %d finger(s), device %s", len(active), ev.pointingDevice().name())
        elif t == T.TouchUpdate:
            self._max_fingers = max(self._max_fingers, len(active))
            self._update(active)
            self._prev = active
        else:
            if (t == T.TouchEnd and not self._moved and self._max_fingers == 1
                    and time.monotonic() - self._t0 < self.TAP_TIME_S and self._start is not None):
                self.tapped.emit(self.plot.mapToScene(self._start.toPoint()))
            log.info("plot: touch %s, max %d finger(s), pan steps %d, pinch steps %d, view %s",
                     t.name, self._max_fingers, self._pans, self._pinches,
                     [[round(v, 2) for v in r] for r in self.vb.viewRange()])
            self._prev, self._start = {}, None
        ev.accept()
        return True

    def _update(self, active: dict):
        ids = [i for i in active if i in self._prev]
        if len(active) >= 2 and len(ids) >= 2:
            self._moved = True
            self._pinches += 1
            a, b = ids[:2]
            self._pinch(self._prev[a], self._prev[b], active[a], active[b])
        elif len(active) == 1 and len(ids) == 1:
            cur = active[ids[0]]
            if not self._moved:
                d = cur - self._start
                if abs(d.x()) + abs(d.y()) < self.TAP_MOVE_PX:
                    return
                self._moved = True
            self._pans += 1
            self.vb.disableAutoRange()
            v0, v1 = self._view(self._prev[ids[0]]), self._view(cur)
            self.vb.translateBy(x=v0.x() - v1.x(), y=v0.y() - v1.y())

    def _pinch(self, a0, b0, a1, b1):
        def factor(old, new):          # >1 = zoom out (fingers closer), <1 = zoom in
            if old < self.MIN_AXIS_SPREAD_PX or new < self.MIN_AXIS_SPREAD_PX:
                return 1.0
            return min(max(old / new, 0.5), 2.0)
        sx = factor(abs(a0.x() - b0.x()), abs(a1.x() - b1.x()))
        sy = factor(abs(a0.y() - b0.y()), abs(a1.y() - b1.y()))
        c0, c1 = (a0 + b0) / 2, (a1 + b1) / 2
        self.vb.disableAutoRange()
        self.vb.scaleBy(x=sx, y=sy, center=self._view(c1))
        v0, v1 = self._view(c0), self._view(c1)      # follow the fingers' midpoint (two-finger pan)
        self.vb.translateBy(x=v0.x() - v1.x(), y=v0.y() - v1.y())


# ============================================================================ worker thread
class GpibWorker(QtCore.QObject):
    """Runs callables f(osa) one at a time on a background thread."""
    done = Signal(object, object)          # (callback, result)
    failed = Signal(str)
    busy = Signal(bool)

    def __init__(self, osa: Osa):
        super().__init__()
        self.osa = osa
        self.q: queue.Queue = queue.Queue()
        self.cancel_flag = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def submit(self, fn, callback=None):
        self.q.put((fn, callback))

    def _run(self):
        while True:
            fn, cb = self.q.get()
            if fn is None:
                return
            self.busy.emit(True)
            try:
                res = fn(self.osa)
                self.done.emit(cb, res)
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                log.exception("worker job failed")
                self.failed.emit(f"{type(e).__name__}: {e}")
            finally:
                self.busy.emit(not self.q.empty())

    def stop(self, wait: float = 0.0):
        """End the worker after the queued jobs; optionally wait for it (so GPIB is idle on exit)."""
        self.q.put((None, None))
        if wait:
            self._t.join(wait)


# ============================================================================ touch keypad
class Keypad(QtWidgets.QDialog):
    """Full-screen-friendly numeric entry with unit, range hint and +/- step buttons.

    start_empty=True: the field starts empty so a new number can be typed straight away; the
    current value is shown greyed out in the field and is where the +/- step keys start from."""

    def __init__(self, parent, title: str, value: float, lo: float, hi: float, unit: str,
                 decimals: int, step: float, special=(), start_empty: bool = False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.lo, self.hi, self.decimals, self.step, self.special = lo, hi, decimals, step, special
        self.current = value
        self.result_value = None
        lay = QtWidgets.QVBoxLayout(self)
        head = QtWidgets.QLabel(f"<b>{title}</b>  <span style='color:{MUTED}'>{lo:g} … {hi:g} {unit}</span>")
        lay.addWidget(head)
        self.edit = QtWidgets.QLineEdit("" if start_empty else f"{value:.{decimals}f}")
        if start_empty:
            self.edit.setPlaceholderText(f"now {value:.{decimals}f} {unit}".rstrip())
        self.edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        lay.addWidget(self.edit)
        self.err = QtWidgets.QLabel("")
        self.err.setStyleSheet(f"color:{WARN}")
        lay.addWidget(self.err)
        grid = QtWidgets.QGridLayout()
        keys = ["7", "8", "9", "⌫", "4", "5", "6", "−step", "1", "2", "3", "+step", "±", "0", ".", "C"]
        for i, k in enumerate(keys):
            b = QtWidgets.QPushButton(k.replace("step", f" {step:g}"))
            b.setMinimumSize(80, 64)
            b.clicked.connect(lambda _=False, k=k: self._key(k))
            grid.addWidget(b, i // 4, i % 4)
        lay.addLayout(grid)
        row = QtWidgets.QHBoxLayout()
        cancel = QtWidgets.QPushButton("Cancel")
        ok = QtWidgets.QPushButton("Set")
        ok.setObjectName("primary")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)

    def _val(self):
        try:
            return float(self.edit.text().replace("−", "-"))
        except ValueError:
            return None

    def _key(self, k):
        t = self.edit.text()
        if k == "⌫":
            self.edit.setText(t[:-1])
        elif k == "C":
            self.edit.setText("")
        elif k == "±":
            self.edit.setText(t[1:] if t.startswith("-") else "-" + t)
        elif k in ("+step", "−step"):
            v = self._val()
            if v is None:                         # empty field: step from the current value
                v = self.current
            v += self.step if k == "+step" else -self.step
            self.edit.setText(f"{min(max(v, self.lo), self.hi):.{self.decimals}f}")
        else:
            self.edit.setText(t + k)

    def _accept(self):
        if not self.edit.text().strip() and self.edit.placeholderText():
            self.reject()                         # nothing typed: keep the current value
            return
        v = self._val()
        if v is None or (not (self.lo <= v <= self.hi) and v not in self.special):
            self.err.setText(f"enter a number in {self.lo:g} … {self.hi:g}")
            return
        self.result_value = v
        self.accept()


class ChoiceDialog(QtWidgets.QDialog):
    def __init__(self, parent, title, options, current):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.choice = None
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel(f"<b>{title}</b>"))
        grid = QtWidgets.QGridLayout()
        cols = 2 if len(options) > 5 else 1          # e.g. 8 resolutions: two columns fit 480 px
        for i, (label, value) in enumerate(options):
            b = QtWidgets.QPushButton(("● " if value == current else "") + label)
            b.clicked.connect(lambda _=False, v=value: self._pick(v))
            grid.addWidget(b, i // cols, i % cols)
        lay.addLayout(grid)
        c = QtWidgets.QPushButton("Cancel")
        c.clicked.connect(self.reject)
        lay.addWidget(c)

    def _pick(self, v):
        self.choice = v
        self.accept()


# ============================================================================ save dialog
DEFAULT_DIR = os.path.expanduser("~/osa_traces")
# Pi OS auto-mounts USB sticks under /media/<user>/<label>; the others cover other distros.
MEDIA_ROOTS = [f"/media/{getpass.getuser()}", "/media", f"/run/media/{getpass.getuser()}"]
_BAD_NAME_CHARS = re.compile(r"[^A-Za-z0-9_.\-]")


def removable_drives() -> list[str]:
    """Mounted, writable removable drives (USB sticks)."""
    found: list[str] = []
    for root in MEDIA_ROOTS:
        try:
            entries = sorted(os.scandir(root), key=lambda e: e.name)
        except OSError:
            continue
        for e in entries:
            try:
                if e.path not in found and e.is_dir() and os.path.ismount(e.path) and os.access(e.path, os.W_OK):
                    found.append(e.path)
            except OSError:
                pass
    return found


def clean_base(name: str) -> str:
    """Base file name: drop a typed '.csv', replace anything unsafe for FAT/exFAT sticks with '_'."""
    name = name.strip()
    if name.lower().endswith(".csv"):
        name = name[:-4]
    return _BAD_NAME_CHARS.sub("_", name)


def next_index(folder: str, base: str) -> int:
    """1 + the highest existing <base>_NNN.csv index in folder (1 if none)."""
    pat = re.compile(re.escape(base) + r"_(\d+)\.csv$", re.IGNORECASE)
    n = 0
    try:
        for f in os.listdir(folder):
            m = pat.match(f)
            if m:
                n = max(n, int(m.group(1)))
    except OSError:
        pass
    return n + 1


def indexed_name(folder: str, base: str) -> str:
    return f"{base}_{next_index(folder, base):03d}.csv"


def _free_text(path: str) -> str:
    try:
        return f"{shutil.disk_usage(path).free / 1e9:.1f} GB free"
    except OSError:
        return ""


class SaveDialog(QtWidgets.QDialog):
    """Pick a location (Pi folder or USB stick) and a base name; an index _NNN is always appended,
    continuing from the files already in the chosen folder, so consecutive saves never overwrite."""

    ROWS = ["1234567890", "qwertyuiop", "asdfghjkl⌫", "⇧zxcvbnm_-"]

    def __init__(self, parent, folder: str, base: str):
        super().__init__(parent)
        self.setWindowTitle("Save trace")
        self.path = self.folder = self.base = None
        self._shift = False
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(5)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("<b>Save to</b>"))
        self.loc_row = QtWidgets.QHBoxLayout()
        top.addLayout(self.loc_row, 1)
        refresh = QtWidgets.QPushButton("↻")
        refresh.setObjectName("loc")
        refresh.setFixedWidth(56)
        refresh.clicked.connect(lambda: self._fill_locations(self._folder()))
        top.addWidget(refresh)
        lay.addLayout(top)
        self.loc_group = QtWidgets.QButtonGroup(self)
        self.loc_group.setExclusive(True)
        self.loc_group.buttonClicked.connect(lambda _: self._update())
        self._fill_locations(folder)

        row = QtWidgets.QHBoxLayout()
        self.edit = QtWidgets.QLineEdit(base)
        self.edit.setObjectName("name")
        self.edit.textChanged.connect(self._update)
        row.addWidget(self.edit, 1)
        reset = QtWidgets.QPushButton("Default")
        reset.setObjectName("loc")
        reset.clicked.connect(lambda: self.edit.setText(default_base()))
        row.addWidget(reset)
        lay.addLayout(row)
        self.preview = ElidedLabel("")
        self.preview.setObjectName("status")
        lay.addWidget(self.preview)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(4)
        self.letter_keys = []
        for r, keys in enumerate(self.ROWS):
            for c, k in enumerate(keys):
                b = QtWidgets.QPushButton(k)
                b.setObjectName("key")
                b.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)   # keep the cursor in the name field
                b.clicked.connect(lambda _=False, k=k: self._key(k))
                grid.addWidget(b, r, c)
                if k.isalpha() and k not in "⌫⇧":
                    self.letter_keys.append(b)
        lay.addLayout(grid)

        row = QtWidgets.QHBoxLayout()
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.ok = QtWidgets.QPushButton("Save")
        self.ok.setObjectName("primary")
        self.ok.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)
        self.edit.setFocus()
        self.edit.end(False)
        self._update()

    def showEvent(self, ev):
        super().showEvent(ev)
        # Qt selects the whole field on focus; put the cursor at the end so a key appends instead
        QtCore.QTimer.singleShot(0, lambda: (self.edit.deselect(), self.edit.end(False)))

    # -- locations
    def _fill_locations(self, current):
        for b in self.loc_group.buttons():
            self.loc_group.removeButton(b)
            b.deleteLater()
        locs = [(DEFAULT_DIR, f"Pi: {os.path.basename(DEFAULT_DIR)}")]
        locs += [(p, f"USB: {os.path.basename(p)}  {_free_text(p)}") for p in removable_drives()]
        if current not in [p for p, _ in locs]:
            current = DEFAULT_DIR                   # e.g. the stick used last time was removed
        for p, label in locs:
            b = QtWidgets.QPushButton(label)
            b.setObjectName("loc")
            b.setCheckable(True)
            b.setChecked(p == current)
            b.setProperty("folder", p)
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
            self.loc_group.addButton(b)
            self.loc_row.addWidget(b)
        if hasattr(self, "preview"):
            self._update()

    def _folder(self):
        b = self.loc_group.checkedButton()
        return b.property("folder") if b else DEFAULT_DIR

    # -- keyboard
    def _key(self, k):
        if k == "⌫":
            self.edit.backspace()
        elif k == "⇧":
            self._shift = not self._shift
            for b in self.letter_keys:
                b.setText(b.text().upper() if self._shift else b.text().lower())
        else:
            self.edit.insert(k.upper() if self._shift and k.isalpha() else k)

    # -- result
    def _update(self, *_):
        base = clean_base(self.edit.text())
        self.ok.setEnabled(bool(base))
        if base:
            self.preview.setText(f"→ {os.path.join(self._folder(), indexed_name(self._folder(), base))}")
        else:
            self.preview.setText("enter a file name")

    def _accept(self):
        base = clean_base(self.edit.text())
        folder = self._folder()
        if not base:
            return
        self.folder, self.base = folder, base
        self.path = os.path.join(folder, indexed_name(folder, base))
        self.accept()


def default_base() -> str:
    return f"trace_{datetime.date.today():%Y%m%d}"


# ============================================================================ parameter tiles
# tile name -> label; "wl_range" and "trace" open menus, the rest edit one OSA setting
TILES = [
    ("wl_range", "Wavelength range"),
    ("trace", "Trace"),
    ("ref_level", "Ref level"),
    ("level_scale", "Scale"),
    ("resolution", "Resolution"),          # 1-2-5 list instead of keypad
    ("sensitivity", "Sensitivity"),        # choice
    ("averaging", "Average"),
    ("sampling_points", "Points"),
]
RANGE_ITEMS = [("center_wl", "Center"), ("span", "Span"),
               ("start_wl", "Start WL"), ("stop_wl", "Stop WL")]
STEPS = {"center_wl": 1.0, "span": 1.0, "start_wl": 1.0, "stop_wl": 1.0, "ref_level": 5.0,
         "level_scale": 1.0, "averaging": 1.0, "sampling_points": 100.0}
# GUI setting name -> key in the dict returned by read_state()
SETTING_KEYS = {"center_wl": "center_nm", "span": "span_nm", "start_wl": "start_nm", "stop_wl": "stop_nm",
                "ref_level": "ref_level_dbm", "level_scale": "level_scale_db_div", "resolution": "resolution_nm",
                "averaging": "averaging", "sampling_points": "sampling_points", "sensitivity": "sensitivity"}
RES_STEPS = [0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
SENS_LABELS = [("NORM HOLD", "norm_hold"), ("NORM AUTO", "norm_auto"),
               ("HIGH 1", "high1"), ("HIGH 2", "high2"), ("HIGH 3", "high3")]


def _short(v: float) -> str:
    """1550.00 -> '1550', 1550.25 -> '1550.25' (keeps the wavelength-range tile on one line)."""
    return f"{v:.2f}".rstrip("0").rstrip(".")


# Optional queries (trace state). If one fails it is not asked again in this session: an
# unanswered query costs a full timeout and would freeze every settings refresh.
OPTIONAL_QUERIES = (("active_trace", "get_active_trace"), ("mode_A", "get_trace_a_mode"),
                    ("mode_B", "get_trace_b_mode"), ("mode_C", "get_trace_c_mode"))
UNSUPPORTED: set = set()
OPTIONAL_TIMEOUT_S = 2.0


def optional_query(o: Osa, name: str):
    if name in UNSUPPORTED:
        return None
    old = o.t.timeout
    try:
        o.t.set_timeout(OPTIONAL_TIMEOUT_S)
        return getattr(o, name)()
    except OsaError as e:
        UNSUPPORTED.add(name)
        log.info("%s failed (%s) - not asked again this session", name, e)
        o.status_byte()                     # clear the error bit so the next setter is not blamed
        return None
    finally:
        o.t.set_timeout(old)


def read_state(o: Osa) -> dict:
    """get_settings() plus start/stop wavelength and trace state (worker thread).
    Start/stop are center -/+ span/2 (how the OSA defines them), so they cost no extra query."""
    s = o.get_settings()
    c, sp = s.get("center_nm"), s.get("span_nm")
    s["start_nm"] = s["stop_nm"] = None
    if c is not None and sp is not None:
        s["start_nm"], s["stop_nm"] = round(c - sp / 2, 3), round(c + sp / 2, 3)
    s["linear"] = s.get("level_scale_db_div") == 0          # LSCL? returns 0 in LIN scale
    s["ref_lin"] = None
    if s["linear"]:
        try:
            s["ref_lin"] = o.get_ref_level_any()                # e.g. (10.0, "UW")
        except OsaError:
            o.status_byte()
    for key, name in OPTIONAL_QUERIES:
        s[key] = optional_query(o, name)
    log.info("state: %s", {k: s.get(k) for k in ("center_nm", "span_nm", "start_nm", "stop_nm",
                                                 "active_trace", "mode_A", "mode_B", "mode_C")})
    return s


# ============================================================================ trace menu
class TraceDialog(QtWidgets.QDialog):
    """Trace menu: active trace, its write mode, which traces are shown, trace copies.
    Every tap is sent at once; the dialog stays open and is refreshed from the instrument."""

    MODES = {"A": [("WRITE", "write_a"), ("FIX", "fix_a"), ("MAX HOLD", "max_hold_a"), ("ROLL AVG", "roll_avg_a")],
             "B": [("WRITE", "write_b"), ("FIX", "fix_b"), ("MIN HOLD", "min_hold_b"), ("ROLL AVG", "roll_avg_b")],
             "C": [("WRITE", "write_c"), ("FIX", "fix_c"), ("C = A−B", "c_eq_a_minus_b"),
                   ("C = B−A", "c_eq_b_minus_a")]}
    COPIES = [("A → B", "copy_a_to_b"), ("B → A", "copy_b_to_a"), ("A → C", "copy_a_to_c"), ("C → A", "copy_c_to_a")]

    def __init__(self, win: "MainWindow"):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Trace")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.addWidget(QtWidgets.QLabel("<b>Trace</b>"))
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(6)
        for col in range(1, 5):
            grid.setColumnStretch(col, 1)
            grid.setColumnMinimumWidth(col, 116)

        def row(r, label, items, slot, checkable=True):
            lab = QtWidgets.QLabel(label)
            lab.setObjectName("rowlabel")
            grid.addWidget(lab, r, 0)
            btns = []
            for i, text in enumerate(items):
                b = QtWidgets.QPushButton(text)
                b.setObjectName("loc")
                b.setCheckable(checkable)
                b.clicked.connect(lambda _=False, i=i: slot(i))
                grid.addWidget(b, r, i + 1)
                btns.append(b)
            return btns

        self.active_btns = row(0, "Active", list("ABC"), self._active)
        self.mode_btns = row(1, "Mode", [m for m, _ in self.MODES["A"]], self._mode)
        self.show_btns = row(2, "Show", list("ABC"), self._show)
        self.copy_btns = row(3, "Copy", [c for c, _ in self.COPIES], self._copy, checkable=False)
        lay.addLayout(grid)
        hint = QtWidgets.QLabel("Mode applies to the active trace. Show = plotted here and displayed on the OSA.")
        hint.setObjectName("status")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        close = QtWidgets.QPushButton("Close")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        lay.addWidget(close)
        self.refresh()

    def refresh(self):
        s = self.win.state
        act = s.get("active_trace") if s.get("active_trace") in ("A", "B", "C") else "A"
        for t, b in zip("ABC", self.active_btns):
            b.setChecked(t == act)
        mode = s.get(f"mode_{act}")
        idx = None
        if mode is not None:
            idx = min(int(mode), 3) if act in "AB" else (int(mode) if int(mode) <= 3 else None)
        for i, (b, (label, _)) in enumerate(zip(self.mode_btns, self.MODES[act])):
            b.setText(label + ("…" if label == "ROLL AVG" else ""))
            b.setChecked(i == idx)
        for t, b in zip("ABC", self.show_btns):
            b.setChecked(self.win.shown[t])

    def _active_trace(self):
        a = self.win.state.get("active_trace")
        return a if a in ("A", "B", "C") else "A"

    def _active(self, i):
        t = "ABC"[i]
        self.win.state["active_trace"] = t           # optimistic; corrected by the read-back
        self.refresh()
        self.win.trace_action(lambda o: o.set_active_trace(t))

    def _mode(self, i):
        act = self._active_trace()
        label, method = self.MODES[act][i]
        self.refresh()                               # undo the button's own toggle until read-back
        if method.startswith("roll_avg"):
            d = Keypad(self, f"Roll average, trace {act}", 10, 2, 100, "sweeps", 0, 1.0)
            if not (d.exec() and d.result_value is not None):
                return
            n = int(d.result_value)
            self.win.trace_action(lambda o: getattr(o, f"set_{method}")(n))
        else:
            self.win.trace_action(lambda o: getattr(o, method)(), refresh_traces=act == "C")

    def _show(self, i):
        t = "ABC"[i]
        self.win.set_shown(t, not self.win.shown[t])
        self.refresh()

    def _copy(self, i):
        method = self.COPIES[i][1]
        self.win.trace_action(lambda o: getattr(o, method)(), refresh_traces=True)


# ============================================================================ measurements
# The OSA's own analysis functions. ANA? reply layout as assumed below has NOT been confirmed on
# the AQ6317B yet (manual Table 9-4 was not transcribed): replies are checked for plausibility and
# shown raw if they don't fit, and every raw reply is logged.
#   key -> (button label, Osa action method, threshold parameter or None)
WIDTH_METHODS = {
    "thresh": ("THRESH", "spec_width_thresh", "thresh_th"),
    "envelope": ("ENVELOPE", "spec_width_envelope", "env_th1"),
    "rms": ("RMS", "spec_width_rms", None),
    "peak_rms": ("PEAK RMS", "spec_width_peak_rms", None),
    "notch": ("NOTCH", "spec_width_notch", "notch_th"),
}
THRESH_PARAMS = [("thresh_th", "THRESH"), ("env_th1", "ENVELOPE"), ("notch_th", "NOTCH")]
_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


class MeasureDialog(QtWidgets.QDialog):
    """MEAS menu. Tapping a measurement runs it on the active trace and closes the menu; the
    result is drawn on the plot and repeated after every sweep until 'Clear result'."""

    def __init__(self, win: "MainWindow", params: dict):
        super().__init__(win)
        self.win, self.choice = win, None
        self.setWindowTitle("Measurements")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.addWidget(QtWidgets.QLabel("<b>Measurements</b> <span style='color:%s'>(OSA analysis of the active trace)</span>" % MUTED))
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(6)

        def label(r, text):
            lab = QtWidgets.QLabel(text)
            lab.setObjectName("rowlabel")
            grid.addWidget(lab, r, 0)

        label(0, "Spectral width")
        for i, (key, (text, _, _)) in enumerate(WIDTH_METHODS.items()):
            b = QtWidgets.QPushButton(text)
            b.setObjectName("loc")
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            grid.addWidget(b, 0, i + 1)
        label(1, "Thresholds")
        self.param_btns = {}
        for i, (name, text) in enumerate(THRESH_PARAMS):
            v = params.get(name)
            b = QtWidgets.QPushButton(f"{text} {v:g} dB" if v is not None else f"{text} — dB")
            b.setObjectName("loc")
            b.clicked.connect(lambda _=False, n=name, t=text: self._edit_param(n, t))
            grid.addWidget(b, 1, i + 1)
            self.param_btns[name] = (b, text)
        self.params = dict(params)
        label(2, "Power")
        b = QtWidgets.QPushButton("Power L1–L2")
        b.setObjectName("loc")
        b.clicked.connect(lambda: self._pick("power"))
        grid.addWidget(b, 2, 1, 1, 2)
        lay.addLayout(grid)
        hint = QtWidgets.QLabel("Power is integrated between line markers L1 and L2 (set them in MARKERS; "
                                "whole span if none are set).")
        hint.setObjectName("status")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        row = QtWidgets.QHBoxLayout()
        clear = QtWidgets.QPushButton("Clear result")
        clear.clicked.connect(lambda: self._pick("clear"))
        close = QtWidgets.QPushButton("Close")
        close.setObjectName("primary")
        close.clicked.connect(self.reject)
        row.addWidget(clear)
        row.addWidget(close)
        lay.addLayout(row)

    def _pick(self, k):
        self.choice = k
        self.accept()

    def _edit_param(self, name, text):
        c = COMMANDS[name]
        d = Keypad(self, f"{text} threshold", self.params.get(name) or 3.0, c.lo, c.hi, c.unit, c.decimals, 0.5)
        if d.exec() and d.result_value is not None:
            v = d.result_value
            self.params[name] = v
            self.param_btns[name][0].setText(f"{text} {v:g} dB")
            self.win.worker.submit(lambda o: getattr(o, f"set_{name}")(v))


# ============================================================================ markers
SEARCHES = {"peak": ("PEAK", "PKSR"), "next": ("NEXT PEAK", "NSR"),
            "left": ("◀ NEXT LEFT", "NSRL"), "right": ("NEXT RIGHT ▶", "NSRR")}


class MarkerDialog(QtWidgets.QDialog):
    """MARKERS menu: line markers L1/L2 (set by tapping the plot) and the OSA's peak searches."""

    def __init__(self, win: "MainWindow"):
        super().__init__(win)
        self.choice = None
        self.setWindowTitle("Markers")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.addWidget(QtWidgets.QLabel("<b>Markers</b>"))
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(6)
        for col in range(1, 5):
            grid.setColumnStretch(col, 1)

        def label(r, text):
            lab = QtWidgets.QLabel(text)
            lab.setObjectName("rowlabel")
            grid.addWidget(lab, r, 0)

        def btn(r, c, text, key):
            b = QtWidgets.QPushButton(text)
            b.setObjectName("loc")
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            grid.addWidget(b, r, c)

        label(0, "Line markers")
        for i in (1, 2):
            v = win.lmarkers.get(i)
            btn(0, i, f"Set L{i}" + (f"  ({v:.3f})" if v is not None else ""), f"L{i}")
        btn(0, 3, "Clear L1/L2", "clear")
        label(1, "Peak search")
        for i, (key, (text, _)) in enumerate(SEARCHES.items()):
            btn(1, i + 1, text, key)
        lay.addLayout(grid)
        hint = QtWidgets.QLabel("Set L1 / L2: then tap the plot where the marker should go. "
                                "L1–L2 is the range for Power and is sent to the OSA.")
        hint.setObjectName("status")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        close = QtWidgets.QPushButton("Close")
        close.setObjectName("primary")
        close.clicked.connect(self.reject)
        lay.addWidget(close)

    def _pick(self, k):
        self.choice = k
        self.accept()


# ============================================================================ main window
class MainWindow(QtWidgets.QWidget):
    def __init__(self, osa: Osa, title: str):
        super().__init__()
        self.setWindowTitle(title)
        self.osa_title = title
        self.values: dict = {}
        self.state: dict = {}
        self.traces: dict = {}            # trace letter -> (wl, lv) currently plotted
        self.shown = {"A": True, "B": False, "C": False}
        self.local_linear = False         # linear display done by the GUI (OSA refused LSCLLIN)
        self._last_db_div = 10.0          # dB/div restored when switching back to log
        self._lin_unit = LIN_UNITS[0]     # current linear display unit
        self.lmarkers = {1: None, 2: None}  # line markers L1 / L2 (nm), as read back from the OSA
        self.lm_items: dict = {}
        self.pick_line = None             # 1 or 2 while waiting for a tap that places L1 / L2
        self.meas_kind = None             # active measurement (WIDTH_METHODS key or "power")
        self._auto_ana = None             # measurement the OSA re-runs itself after each sweep (ATANA1)
        self.meas_items: list = []        # plot items drawing the result
        self.repeating = False            # OSA is running its own REPEAT sweep (RPT)
        self._poll_pending = False        # a REPEAT trace read is queued or running
        self._wl_cache: dict = {}         # trace -> ((start, stop), wavelength axis)
        self.trace_dialog = None
        self.save_dir = DEFAULT_DIR       # last location / base name used, offered again next save
        self.save_base = None             # None -> today's default name
        self.worker = GpibWorker(osa)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_error)
        self.worker.busy.connect(self._on_busy)
        self._build()
        self.worker.submit(read_state, self._show_settings)
        self.worker.submit(self._read_line_markers, self._set_line_markers)

    # ---------------------------------------------------------------- layout
    def _build(self):
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        left = QtWidgets.QVBoxLayout()
        left.setSpacing(4)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(self._btn("Exit OSA", self.exit_app, "small"))
        self.status = ElidedLabel(f"{self.osa_title} · ready · gui {GUI_VERSION}")
        self.status.setObjectName("status")
        top.addWidget(self.status, 1)
        left.addLayout(top)

        self.plot = pg.PlotWidget(background=BG)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Wavelength", units="nm")
        self.plot.setLabel("left", "Level", units="dBm")
        self.plot.getAxis("bottom").enableAutoSIPrefix(False)
        self.plot.getAxis("left").enableAutoSIPrefix(False)
        self.legend = self.plot.addLegend(offset=(-6, 6), brush=pg.mkBrush(17, 22, 28, 210),
                                          labelTextColor=TEXT, labelTextSize="10pt")
        self.curves = {t: self.plot.plot([], [], pen=pg.mkPen(c, width=2)) for t, c in TRACE_COLORS.items()}
        self.legend.clear()
        self.marker = pg.ScatterPlotItem(size=14, brush=pg.mkBrush(ACCENT), pen=pg.mkPen("w"))
        self.plot.addItem(self.marker)
        self.plot.scene().sigMouseClicked.connect(self._plot_tap)
        self.plot.setMenuEnabled(False)          # no right-click / long-press context menu
        self.plot.hideButtons()                  # pyqtgraph's tiny "A" auto-range button
        self.touch = TouchNav(self.plot)
        self.touch.tapped.connect(self._marker_at)
        self.b_reset_zoom = self._btn("Reset zoom", self.reset_zoom, "small")
        self.b_box_zoom = self._btn("Box zoom", None, "small")
        self.b_box_zoom.setCheckable(True)
        self.b_box_zoom.toggled.connect(self.set_box_zoom)
        for b in (self.b_box_zoom, self.b_reset_zoom):
            b.setParent(self.plot)
            b.raise_()
        self.b_scale = self._btn("Lin. scale", self.toggle_lin_log, "small")
        self.b_scale.setParent(self.plot)
        self.b_scale.raise_()
        self.meas_label = QtWidgets.QLabel(self.plot)      # measurement result, top-left of the data
        self.meas_label.setObjectName("meas")
        self.meas_label.hide()
        self.plot.plotItem.vb.sigResized.connect(self._place_reset_zoom)
        self.plot.plotItem.vb.sigRangeChangedManually.connect(lambda *_: self._zoom_changed())
        left.addWidget(self.plot, 1)
        self.readout = ElidedLabel("Marker: —")
        self.readout.setObjectName("readout")
        left.addWidget(self.readout)
        root.addLayout(left, 1)

        side = QtWidgets.QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(6)
        row = QtWidgets.QHBoxLayout()
        self.b_single = self._btn("SINGLE", self.single, "primary")
        self.b_repeat = self._btn("REPEAT", self.toggle_repeat)
        self.b_stop = self._btn("STOP", self.stop, "stop")
        for b in (self.b_single, self.b_repeat, self.b_stop):
            row.addWidget(b)
        side.addLayout(row)
        row = QtWidgets.QHBoxLayout()
        for text, slot in (("PEAK", self.peak), ("MARKERS", self.open_markers),
                           ("MEAS", self.open_measurements), ("SAVE", self.save_csv)):
            row.addWidget(self._btn(text, slot, "row4"))
        side.addLayout(row)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(6)
        self.tiles = {}
        for i, (name, label) in enumerate(TILES):
            b = QtWidgets.QPushButton(f"{label}\n—")
            b.setObjectName("tile")
            b.clicked.connect(lambda _=False, n=name: self.edit_param(n))
            self.tiles[name] = b
            grid.addWidget(b, i // 2, i % 2)
        side.addLayout(grid)
        side.addStretch(1)
        w = QtWidgets.QWidget()
        w.setLayout(side)
        w.setFixedWidth(320)
        root.addWidget(w)

    def _btn(self, text, slot, obj=None):
        b = QtWidgets.QPushButton(text)
        if obj:
            b.setObjectName(obj)
        if slot is not None:
            b.clicked.connect(slot)
        return b

    # ---------------------------------------------------------------- worker results
    def _on_done(self, cb, res):
        if cb:
            cb(res)

    def _warn(self, msg):
        self.status.setText(f"⚠ {msg}")
        self.status.setStyleSheet(f"color:{WARN}")

    def _on_error(self, msg):
        self._end_repeat()
        self._warn(msg)

    def _on_busy(self, b):
        self.b_single.setEnabled(not b or self.repeating)

    def _ok(self, text):
        self.status.setStyleSheet("")
        self.status.setText(f"{self.osa_title} · {text} · {datetime.datetime.now():%H:%M:%S}")

    # ---------------------------------------------------------------- settings
    def _show_settings(self, s: dict):
        if not s.get("linear") and (s.get("level_scale_db_div") or 0) > 0:
            self._last_db_div = s["level_scale_db_div"]
        was_linear = self._is_linear()
        old = (self.state.get("start_nm"), self.state.get("stop_nm"))
        self.state = s
        if self.state and None not in old and old != (s.get("start_nm"), s.get("stop_nm")):
            self.reset_zoom()           # new wavelength range on the OSA: zoomed view would be stale
        self.values = {name: s.get(key) for name, key in SETTING_KEYS.items()}
        for name, label in TILES:
            if name == "wl_range":
                lo, hi = self.values.get("start_wl"), self.values.get("stop_wl")
                txt = f"{_short(lo)}–{_short(hi)} nm" if lo is not None and hi is not None else "—"
            elif name == "trace":
                act = s.get("active_trace") or "?"
                txt = f"active {act} · {''.join(t for t in 'ABC' if self.shown[t]) or 'none'}"
            elif name == "ref_level" and self._is_linear():
                txt = self._ref_lin_text()
            elif name == "level_scale" and self._is_linear():
                txt = "linear"
            else:
                v, c = self.values.get(name), COMMANDS[name]
                if isinstance(v, str):
                    txt = dict((b, a) for a, b in SENS_LABELS).get(v, v)
                elif v is None:
                    txt = "—"
                else:
                    txt = f"{v:.{c.decimals}f} {c.unit}".strip()
            self.tiles[name].setText(f"{label}\n{txt}")
        if self.trace_dialog is not None:
            self.trace_dialog.refresh()
        self.b_scale.setText("Log scale" if self._is_linear() else "Lin. scale")
        if was_linear != self._is_linear():
            self._scale_changed()
        self._ok("settings read")

    def edit_param(self, name):
        if name == "ref_level" and self.state.get("linear") and self.state.get("ref_lin"):
            return self._edit_ref_linear()
        if name == "wl_range":
            return self.edit_range()
        if name == "trace":
            return self.edit_trace()
        cur = self.values.get(name)
        if name == "sensitivity":
            d = ChoiceDialog(self, "Sensitivity", SENS_LABELS, cur)
            if d.exec() and d.choice:
                self._apply(lambda o: o.set_sensitivity(d.choice))
            return
        if name == "resolution":
            d = ChoiceDialog(self, "Resolution (nm)", [(f"{r:g} nm", r) for r in RES_STEPS], cur)
            if d.exec() and d.choice:
                self._apply(lambda o: o.set_resolution(d.choice))
            return
        self._edit_number(name, dict(TILES)[name])

    def edit_range(self):
        """Wavelength range: pick how to set it (center / span / low / high), then the keypad."""
        opts = []
        for name, label in RANGE_ITEMS:
            v, c = self.values.get(name), COMMANDS[name]
            opts.append((f"{label}   {v:.{c.decimals}f} {c.unit}" if v is not None else label, name))
        d = ChoiceDialog(self, "Wavelength range", opts, None)
        if d.exec() and d.choice:
            self._edit_number(d.choice, dict(RANGE_ITEMS)[d.choice])

    def _edit_number(self, name, title):
        c = COMMANDS[name]
        cur = self.values.get(name)
        d = Keypad(self, title, cur if cur is not None else c.lo, c.lo, c.hi, c.unit, c.decimals,
                   STEPS.get(name, 1.0), c.special,
                   start_empty=name in dict(RANGE_ITEMS))   # center, span, start, stop: type afresh
        if not (d.exec() and d.result_value is not None):
            return
        v = d.result_value
        lo, hi = self.values.get("start_wl"), self.values.get("stop_wl")
        if name == "start_wl" and hi is not None and v >= hi:
            return self._warn(f"Start WL must be below Stop WL ({hi:g} nm)")
        if name == "stop_wl" and lo is not None and v <= lo:
            return self._warn(f"Stop WL must be above Start WL ({lo:g} nm)")
        setter = getattr(Osa, f"set_{name}")
        self._apply(lambda o: setter(o, int(v) if c.reply == "int" else v))

    def _apply(self, fn):
        def job(o):
            fn(o)
            return read_state(o)
        self.worker.submit(self._paused(job), self._show_settings)

    # ---------------------------------------------------------------- traces
    def edit_trace(self):
        self.trace_dialog = TraceDialog(self)
        try:
            self.trace_dialog.exec()
        finally:
            self.trace_dialog = None

    def trace_action(self, fn, refresh_traces=False):
        """Run a trace command, re-read the trace state (and the plotted traces if asked)."""
        def job(o):
            fn(o)
            o.check_errors()
            return read_state(o), (self._read_traces(o, only_changed=False) if refresh_traces else None)
        self.worker.submit(self._paused(job), self._after_trace_action)

    def _after_trace_action(self, res):
        s, traces = res
        self._show_settings(s)
        if traces is not None:
            self._show_traces(traces, sweep=False)

    def set_shown(self, t, on):
        """Show/hide a trace: here on the plot and on the OSA screen (DSPx / BLKx)."""
        self.shown[t] = on
        if not on:
            self.traces.pop(t, None)
            self._redraw()
        code = ("DSP" if on else "BLK") + t
        self.trace_action(lambda o: o.send(code), refresh_traces=on)

    def _read_traces(self, o: Osa, only_changed=True):
        """Read the shown traces (worker thread).

        only_changed=True (after a sweep / during REPEAT):
          * B and C in FIX already on the plot are skipped: they cannot have changed;
          * the wavelength axis (WDATx, as long to transfer as the levels) is re-used when the
            wavelength range and the number of points are unchanged, so only LDATx is read.
        """
        out = {}
        rng = (self.state.get("start_nm"), self.state.get("stop_nm"))
        for t in "ABC":
            if not self.shown[t]:
                continue
            if only_changed and t != "A" and t in self.traces and self.state.get(f"mode_{t}") == 1:
                continue
            try:
                lv = np.asarray(o.get_trace_levels(t), float)
                cached = self._wl_cache.get(t)
                if only_changed and cached and cached[0] == rng and len(cached[1]) == len(lv):
                    wl = cached[1]
                else:
                    wl = np.asarray(o.get_trace_wavelengths(t), float)
                    self._wl_cache[t] = (rng, wl)
            except OsaError as e:
                if self.repeating and isinstance(e, OsaTimeout):
                    raise                     # REPEAT: let the poll loop decide, don't skip silently
                o.status_byte()
                continue
            if len(wl) and len(wl) == len(lv):
                out[t] = (wl, lv)
        return out

    def _show_traces(self, traces, sweep=True):
        for t, data in traces.items():
            if self.shown[t]:
                self.traces[t] = data
        self._redraw()
        if sweep:
            n = max((len(wl) for wl, _ in self.traces.values()), default=0)
            self._ok(f"sweep · {n} pts")

    def _redraw(self):
        self._update_level_axis()
        self.legend.clear()
        act = self.state.get("active_trace")
        for t, curve in self.curves.items():
            curve.setZValue(10 if t == act else 1)      # active trace drawn on top
            if t in self.traces and self.shown[t]:
                wl, lv = self.traces[t]
                ok, y = self._display_levels(lv)
                # line through the real points only: a real point between two no-data points stays
                # connected to its real neighbours instead of vanishing
                curve.setData(wl[ok], y[ok])
                self.legend.addItem(curve, f"Trace {t}")
            else:
                curve.setData([], [])
        # legend only when more than one trace is plotted
        self.legend.setVisible(len(self.legend.items) > 1)

    @staticmethod
    def _plot_levels(lv):
        """Levels with the points the OSA reports as -210 dBm (below its measuring range) moved to a
        floor just under the lowest real point; used to place the tap marker on such a point (the
        line itself joins the real points only). Rounded down to 5 dB so it does not jump."""
        nd = lv <= NO_DATA_DBM
        if not nd.any():
            return lv
        if nd.all():
            return np.full_like(lv, np.nan)
        floor = 5.0 * np.floor((lv[~nd].min() - FLOOR_MARGIN_DB) / 5.0)
        return np.where(nd, floor, lv)

    # ---------------------------------------------------------------- sweeping
    def _sweep_job(self, o: Osa):
        if self.worker.cancel_flag.is_set():        # STOP pressed while this job was queued
            return None
        o.single_sweep(wait=False)
        try:
            o.wait_sweep_done(timeout=600, cancel=self.worker.cancel_flag.is_set)
        except OsaError as e:
            if "cancelled" in str(e):
                return None
            raise
        self._wait_sweep_stopped(o)
        traces = self._read_traces(o)
        for t, (wl, lv) in traces.items():
            nd = int(np.sum(lv <= NO_DATA_DBM))
            log.info("trace %s: %d pts %.3f..%.3f nm, %d no-data points", t, len(wl), wl[0], wl[-1], nd)
        return traces

    def _wait_sweep_stopped(self, o: Osa, timeout: float = 60.0):
        """The sweep-done status bit alone is not trusted: reading a trace while the OSA is still
        sweeping returns -210 dBm (no data) for the part not yet measured. Wait for SWEEP? = 0."""
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout and not self.worker.cancel_flag.is_set():
            st = optional_query(o, "get_sweep_status")
            if st is None or st == 0:
                return
            log.info("SWEEP? = %s after the done bit; waiting", st)
            time.sleep(0.2)

    def single(self):
        if self.repeating:                       # SINGLE while REPEAT runs: stop it first
            self._end_repeat()
            self.worker.submit(lambda o: o.stop_sweep())
        self.worker.cancel_flag.clear()
        self.status.setStyleSheet("")
        self.status.setText("sweeping…")
        self.worker.submit(self._sweep_job, self._sweep_done)

    def _sweep_done(self, res):
        if res is None:
            return
        self._show_traces(res, sweep=True)
        self._warn_if_a_fixed()
        self._rerun_measurement()

    def _warn_if_a_fixed(self):
        if self.shown["A"] and self.state.get("mode_A") == 1:
            self._warn("trace A is FIX, so the sweep did not update it: Trace → Mode → WRITE")
            return True
        return False

    # REPEAT uses the OSA's own repeat mode (RPT): the instrument sweeps continuously and the GUI
    # keeps reading the trace. Settings changed meanwhile are sent as STP, change, RPT (_paused),
    # because codes received during a sweep may be ignored (manual p. 9-50).
    def toggle_repeat(self):
        if self.repeating:
            return self.stop()
        self.repeating = True
        self._poll_pending = False
        self.b_repeat.setText("REPEAT ■")
        self.worker.cancel_flag.clear()
        self.status.setStyleSheet("")
        self.status.setText("repeat sweep on the OSA…")
        self._last_sweep_end = None
        self._sweep_period = None
        log.info("repeat: start (RPT)")

        def start(o):
            o.send("SRQ1")              # sweep-end -> status bit 0 (manual p. 9-49)
            o.status_byte()             # clear old bits
            o.repeat_sweep()
        self.worker.submit(start, lambda _: self._poll_repeat())

    def _poll_repeat(self):
        if self.repeating and not self._poll_pending:
            self._poll_pending = True
            self.worker.submit(self._repeat_read_job, self._repeat_data)

    def _repeat_read_job(self, o: Osa):
        """Wait for the OSA's sweep-end bit (cheap serial polls), then read the trace once.
        Reading continuously instead slowed the AQ6317B's sweep ~4x (it serves each transfer at the
        expense of sweeping) and caught half-finished sweeps."""
        if not self.repeating or self.worker.cancel_flag.is_set():
            return None
        t0 = time.monotonic()
        limit = max(5.0, 3 * self._sweep_period) if self._sweep_period else 60.0
        while True:
            if not self.repeating or self.worker.cancel_flag.is_set():
                return None
            if not self.worker.q.empty():
                return "busy"            # a setting change etc. is waiting: let it run first
            if o.status_byte() & 0x01:
                break
            if time.monotonic() - t0 > limit:
                log.info("repeat: no sweep-end bit for %.1f s, reading anyway", limit)
                break
            time.sleep(REPEAT_STB_POLL_S)
        now = time.monotonic()
        if self._last_sweep_end is not None:
            self._sweep_period = now - self._last_sweep_end
            log.info("repeat: sweep end, %.2f s since the previous one", self._sweep_period)
        self._last_sweep_end = now
        old = o.t.timeout
        o.t.set_timeout(REPEAT_READ_TIMEOUT_S)
        try:
            return self._read_traces(o)
        finally:
            o.t.set_timeout(old)

    def _repeat_data(self, res):
        self._poll_pending = False
        if not self.repeating:
            return
        if res == "busy":
            res = None
        if res:
            self._show_traces(res, sweep=True)
            self._warn_if_a_fixed()
            self._rerun_measurement()
        QtCore.QTimer.singleShot(REPEAT_POLL_MS, self._poll_repeat)

    def _end_repeat(self):
        if self._auto_ana:
            self.worker.submit(self._auto_analysis_off)
        self.repeating = False
        self._poll_pending = False
        self.b_repeat.setText("REPEAT")

    def _paused(self, fn):
        """Wrap a job so that, while REPEAT runs, the OSA is stopped for it and restarted after."""
        if not self.repeating:
            return fn

        def job(o):
            o.stop_sweep()
            try:
                return fn(o)
            finally:
                if self.repeating:
                    o.repeat_sweep()
                    self._last_sweep_end = self._sweep_period = None   # sweep time may change
        return job

    def stop(self):
        self._end_repeat()
        self.worker.cancel_flag.set()
        log.info("stop (STP)")
        self.status.setStyleSheet("")
        self.status.setText("stopping…")        # waits for a trace read already in progress
        self.worker.submit(lambda o: o.stop_sweep(), lambda _: self._ok("stopped"))

    def peak(self):
        self.worker.submit(lambda o: o.peak_search_marker(), self._show_marker)

    def peak_center(self):
        self._apply(lambda o: o.peak_to_center())

    def _show_marker(self, m):
        """Marker dot + readout. In linear display the level comes from the trace point at the
        marker wavelength (the OSA's marker reply may be in dBm or W)."""
        x, y = m["x"], m["y"]
        t, wl, lv = self._active_trace_data()
        if wl is not None and len(wl):
            i = int(np.argmin(np.abs(wl - x)))
            ok, yd = self._display_levels(lv)
            if self._is_linear():
                text = f"{yd[i]:.4g} {self._lin_unit[0]}" if ok[i] else "below range"
                self.marker.setData([x], [yd[i] if ok[i] else 0.0])
                self.readout.setText(f"Marker: {x:.3f} nm   {text}")
                return
            if y <= NO_DATA_DBM or y >= 0 and not (lv < 0).any():
                y = yd[i] if ok[i] else NO_DATA_DBM
            y_plot = yd[i] if ok[i] else float(self._plot_levels(np.where(ok, yd, -210.0))[i])
            self.marker.setData([x], [y if y > NO_DATA_DBM else y_plot])
        else:
            self.marker.setData([x], [y])
        level = "below range" if y <= NO_DATA_DBM else f"{y:.2f} dBm"
        self.readout.setText(f"Marker: {x:.3f} nm   {level}")

    # ---------------------------------------------------------------- zoom
    def _place_reset_zoom(self, *_):
        """Keep the Reset zoom button in the bottom-right corner of the data area."""
        r = self.plot.mapFromScene(self.plot.plotItem.vb.sceneBoundingRect()).boundingRect()
        x = r.right() - 6
        for b in (self.b_reset_zoom, self.b_box_zoom):          # right to left
            b.adjustSize()
            x -= b.width()
            b.move(x, r.bottom() - b.height() - 6)
            x -= 6
        self.b_scale.adjustSize()
        self.b_scale.move(int(r.left() + 6), int(r.top() + 6))
        self.meas_label.adjustSize()
        # bottom-left of the data area (peaks are at the top); above the zoom buttons if too wide
        lab = self.meas_label
        y = r.bottom() - lab.height() - 6
        if r.left() + 6 + lab.width() > self.b_box_zoom.x() - 6:
            y = self.b_box_zoom.y() - lab.height() - 6
        lab.move(int(r.left() + 6), int(y))

    def _zoom_changed(self):
        """Mouse drag/wheel/box zoom (pyqtgraph) - touch zoom calls disableAutoRange itself."""
        self.plot.plotItem.vb.disableAutoRange()
        if self.b_box_zoom.isChecked():          # one box per press of the button
            self.b_box_zoom.setChecked(False)

    def set_box_zoom(self, on: bool):
        """Box zoom: the next one-finger (or mouse) drag draws a rectangle and zooms into it.
        Works even when the touch screen only delivers mouse events."""
        vb = self.plot.plotItem.vb
        vb.setMouseMode(vb.RectMode if on else vb.PanMode)
        self.touch.passthrough = on
        log.info("box zoom %s", "on" if on else "off")

    def reset_zoom(self):
        vb = self.plot.plotItem.vb
        vb.autoRange()                # fit the data now ...
        vb.enableAutoRange()          # ... and keep auto-scaling on every following sweep

    def _plot_tap(self, ev):
        """Mouse click on the plot (touch taps come from TouchNav.tapped)."""
        self._marker_at(ev.scenePos())

    def _marker_at(self, scene_pos):
        """Put a local marker at the nearest point of the active trace (or the first plotted one);
        no GPIB traffic."""
        if not self.traces or not self.plot.plotItem.vb.sceneBoundingRect().contains(scene_pos):
            return
        if self.pick_line:
            return self._place_line_marker(self.plot.plotItem.vb.mapSceneToView(scene_pos).x())
        act = self.state.get("active_trace")
        t = act if act in self.traces else sorted(self.traces)[0]
        wl, lv = self.traces[t]
        p = self.plot.plotItem.vb.mapSceneToView(scene_pos)
        i = int(np.argmin(np.abs(wl - p.x())))
        self._show_marker({"x": float(wl[i]), "y": float(lv[i])})

    # ---------------------------------------------------------------- lin / log scale
    def _is_linear(self) -> bool:
        return bool(self.state.get("linear")) or self.local_linear

    def toggle_lin_log(self):
        """Switch the level axis. The OSA itself is switched (LSCLLIN / LSCL<dB/div>), so its screen,
        the reference level and the trace data follow. If the OSA refuses LSCLLIN, the GUI shows the
        linear plot itself (converted from dBm) and the OSA stays in log scale."""
        if self.local_linear:                        # GUI-only linear -> back to log
            self.local_linear = False
            self._after_scale_change()
            return
        if self._is_linear():
            db = self._last_db_div or 10.0
            log.info("scale: log (LSCL%.1f)", db)
            self._apply(lambda o: o.set_level_scale(db))
            return

        def job(o):
            if "LSCLLIN" not in UNSUPPORTED:
                o.send("LSCLLIN")
                try:
                    o.check_errors()
                    return read_state(o)
                except OsaError as e:
                    UNSUPPORTED.add("LSCLLIN")
                    log.info("LSCLLIN rejected (%s): linear display in the GUI only", e)
                    o.status_byte()
            return None
        log.info("scale: linear")
        self.worker.submit(self._paused(job), self._linear_result)

    def _linear_result(self, s):
        if s is None:
            self.local_linear = True
            self._after_scale_change()
            self._warn("OSA stays in log scale; linear shown by this display only")
        else:
            self._show_settings(s)

    def _after_scale_change(self):
        self._show_settings(self.state)
        self._scale_changed()

    def _scale_changed(self):
        """Values in the old units would distort the plot: drop the marker, redraw traces and
        measurement in the new units, fit the view."""
        self.marker.setData([], [])
        self.readout.setText("Marker: —")
        self._redraw()
        self._clear_measurement()
        self._rerun_measurement()
        self.reset_zoom()

    def _ref_lin_text(self) -> str:
        rl = self.state.get("ref_lin")
        if self.state.get("linear") and rl:
            v, code = rl
            name = next((n for n, _, c in LIN_UNITS if c == code), code)
            return f"{v:g} {name}"
        dbm = self.values.get("ref_level")             # GUI-only linear: dBm converted
        if dbm is None:
            return "—"
        name, f, _ = self._unit_for(10 ** (dbm / 10))
        return f"{10 ** (dbm / 10) * f:.3g} {name}"

    def _edit_ref_linear(self):
        v, code = self.state["ref_lin"]
        setter = LIN_SETTER.get(code)
        if setter is None:
            return self._warn(f"unknown ref level unit {code!r}")
        c = COMMANDS[setter]
        name = next((n for n, _, cc in LIN_UNITS if cc == code), code)
        d = Keypad(self, f"Ref level ({name})", v, c.lo, c.hi, name, c.decimals, 1.0)
        if d.exec() and d.result_value is not None:
            x = d.result_value
            self._apply(lambda o: getattr(o, f"set_{setter}")(x))

    @staticmethod
    def _unit_for(max_mw: float):
        """Linear unit that shows max_mw as 1 ... 999."""
        for unit in LIN_UNITS:
            if max_mw * unit[1] >= 1.0:
                return unit
        return LIN_UNITS[-1]

    def _display_levels(self, lv):
        """(valid mask, values) as plotted. Data may be dBm (log scale; -210 = below range) or W
        (OSA in linear scale); the display may be log (dBm) or linear (self._lin_unit)."""
        lv = np.asarray(lv, float)
        is_dbm = bool((lv < 0).any())
        if is_dbm:
            valid = lv > NO_DATA_DBM
            mw = np.where(valid, 10 ** (lv / 10), 0.0)
        else:
            valid = np.ones(lv.shape, bool)
            mw = lv * 1e3
        if not self._is_linear():
            if is_dbm:
                return valid, lv
            with np.errstate(divide="ignore"):
                return lv > 0, 10 * np.log10(np.maximum(mw, 1e-30))
        return valid, mw * self._lin_unit[1]

    def _update_level_axis(self):
        if self._is_linear():
            rl = self.state.get("ref_lin")
            unit = next((u for u in LIN_UNITS if rl and u[2] == rl[1]), None) if self.state.get("linear") else None
            if unit is None:                          # auto unit from the data
                mx = 0.0
                for wl, lv in self.traces.values():
                    lv = np.asarray(lv, float)
                    m = 10 ** (lv[lv > NO_DATA_DBM] / 10) if (lv < 0).any() else lv * 1e3
                    if len(m):
                        mx = max(mx, float(m.max()))
                unit = self._unit_for(mx) if mx > 0 else LIN_UNITS[0]
            self._lin_unit = unit
            self.plot.setLabel("left", "Level", units=unit[0])
        else:
            self.plot.setLabel("left", "Level", units="dBm")

    # ---------------------------------------------------------------- markers
    def open_markers(self):
        self.pick_line = None
        d = MarkerDialog(self)
        if not d.exec() or not d.choice:
            return
        c = d.choice
        if c in ("L1", "L2"):
            self.pick_line = int(c[1])
            self.b_box_zoom.setChecked(False)
            self.status.setStyleSheet(f"color:{LINE_MARKER_COLOR}")
            self.status.setText(f"tap the plot where {c} should go")
        elif c == "clear":
            def job(o):
                o.line_marker_clear()
                o.check_errors()
                return self._read_line_markers(o)
            self.worker.submit(job, lambda m: (self._set_line_markers(m), self._ok("line markers cleared")))
        else:
            label, code = SEARCHES[c]

            def job(o):
                o.send(code)
                o.check_errors()
                return o.get_marker()
            log.info("marker search %s (%s)", c, code)
            self.worker.submit(job, self._show_marker)

    def _place_line_marker(self, x):
        n, self.pick_line = self.pick_line, None
        wl = [w for w, _ in self.traces.values()]
        lo, hi = min(float(w.min()) for w in wl), max(float(w.max()) for w in wl)
        if not lo <= x <= hi:
            return self._warn(f"L{n} must be inside the trace ({lo:.2f}–{hi:.2f} nm)")
        x = round(x, 3)

        def job(o):
            getattr(o, f"set_line_marker{n}_nm")(x)
            return self._read_line_markers(o)
        log.info("set L%d = %.3f nm", n, x)
        self.worker.submit(job, lambda m: (self._set_line_markers(m), self._ok(f"L{n} = {x:.3f} nm")))

    def _read_line_markers(self, o: Osa) -> dict:
        """Worker thread: L1MK? / L2MK? (0 or empty = not set)."""
        out = {}
        for n in (1, 2):
            v = self._marker_nm(optional_query(o, f"get_line_marker{n}_nm"))
            out[n] = v if v is not None and v > 0 else None
        return out

    def _set_line_markers(self, m: dict):
        self.lmarkers = m
        for it in self.lm_items.values():
            self.plot.removeItem(it)
        self.lm_items = {}
        col = pg.mkColor(LINE_MARKER_COLOR)
        for n, x in m.items():
            if x is None:
                continue
            line = pg.InfiniteLine(pos=x, angle=90, pen=pg.mkPen(col, width=1.5, style=QtCore.Qt.PenStyle.DashLine),
                                   label=f"L{n}", labelOpts={"position": 0.93, "color": col,
                                                             "fill": pg.mkBrush(17, 22, 28, 210)})
            line.setZValue(15)
            self.plot.addItem(line, ignoreBounds=True)
            self.lm_items[n] = line
        if self.meas_kind == "power":
            self._rerun_measurement()

    # ---------------------------------------------------------------- measurements
    def open_measurements(self):
        """Read the current thresholds, then show the MEAS menu."""
        def params(o):
            return {n: optional_query(o, f"get_{n}") for n, _ in THRESH_PARAMS}
        self.worker.submit(params, self._measure_menu)

    def _measure_menu(self, params):
        d = MeasureDialog(self, params)
        if not d.exec() or not d.choice:
            return
        if d.choice == "clear":
            self.meas_kind = None
            self.worker.submit(self._auto_analysis_off)
            self._clear_measurement()
            self._ok("measurement cleared")
            return
        if not self.traces:
            return self._warn("no trace yet: run a sweep first")
        self.meas_kind = d.choice
        self._rerun_measurement()

    def _rerun_measurement(self):
        if self.meas_kind:
            kind = self.meas_kind
            self.worker.submit(lambda o: self._measure_job(o, kind), self._show_measurement)

    def _run_analysis(self, o: Osa, kind: str):
        """Start the analysis. In REPEAT a new sweep clears the result before ANA? can read it, so
        there the OSA's auto-analysis (ATANA1) is switched on once and re-runs it after every sweep."""
        action = "analyze_power" if kind == "power" else WIDTH_METHODS[kind][1]
        if self.repeating and "ATANA" not in UNSUPPORTED:
            if self._auto_ana == kind:
                return
            getattr(o, action)()
            o.check_errors()
            o.send("ATANA1")
            try:
                o.check_errors()
                self._auto_ana = kind
                log.info("auto-analysis on for %s", kind)
                return
            except OsaError as e:          # AQ6317B rejected ATANA1 (seen in the log, stb 0x48)
                UNSUPPORTED.add("ATANA")
                log.info("ATANA1 rejected (%s): analysing after every sweep instead", e)
        self._auto_analysis_off(o)
        getattr(o, action)()
        o.check_errors()

    def _auto_analysis_off(self, o: Osa):
        if self._auto_ana:
            o.send("ATANA0")
            self._auto_ana = None
            log.info("auto-analysis off")

    def _measure_job(self, o: Osa, kind: str) -> dict:
        """Worker thread: run the OSA analysis and read ANA? (plus thresholds / L1-L2 markers).
        An instrument error is returned as a result (shown in the box) instead of stopping REPEAT."""
        try:
            return self._measure_job_inner(o, kind)
        except OsaError as e:
            log.info("measurement %s failed: %s", kind, e)
            try:
                o.status_byte()            # clear the error bit
            except OsaError:
                pass
            return {"kind": kind, "error": str(e)}

    def _measure_job_inner(self, o: Osa, kind: str) -> dict:
        self._run_analysis(o, kind)
        if kind == "power":
            raw = o.analysis_raw()
            l1 = optional_query(o, "get_line_marker1_nm")
            l2 = optional_query(o, "get_line_marker2_nm")
            res = {"kind": kind, "raw": raw, "l1": l1, "l2": l2}
        else:
            th = WIDTH_METHODS[kind][2]
            raw = o.analysis_raw()
            res = {"kind": kind, "raw": raw, "th": optional_query(o, f"get_{th}") if th else None}
        log.info("measurement %s: ANA? -> %r %s", kind, res["raw"], {k: v for k, v in res.items() if k not in ("kind", "raw")})
        return res

    def _clear_measurement(self):
        for it in self.meas_items:
            self.plot.removeItem(it)
        self.meas_items = []
        self.meas_label.hide()

    def _active_trace_data(self):
        act = self.state.get("active_trace")
        t = act if act in self.traces else (sorted(self.traces)[0] if self.traces else None)
        if t is None:
            return None, None, None
        wl, lv = self.traces[t]
        return t, wl, lv

    def _show_measurement(self, res: dict):
        if not self.meas_kind or res.get("kind") != self.meas_kind:
            return                                  # cleared or changed meanwhile
        self._clear_measurement()
        name = "Power" if res["kind"] == "power" else WIDTH_METHODS[res["kind"]][0]
        if res.get("error"):
            err = "OSA rejected the command" if "command/data error" in res["error"] else res["error"][:60]
            return self._meas_text(f"<b>{name}</b>: {err}")
        raw = (res.get("raw") or "").strip()
        nums = [float(x) for x in _NUM.findall(raw)]
        if not raw:
            return self._meas_text(f"<b>{name}</b>: OSA returned no result<br>"
                                   "(no clear peak in the trace?)")
        t, wl, lv = self._active_trace_data()
        if lv is None:
            return self._meas_text("Measurement: no trace data")
        ok, yd = self._display_levels(lv)
        valid = yd[ok]
        if not len(valid):
            return self._meas_text("Measurement: no trace data")
        lo_wl, hi_wl = float(wl.min()), float(wl.max())
        top = float(valid.max())
        acc = pg.mkColor(ACCENT)
        if res["kind"] == "power":
            unit = re.search(r"\b(PW|NW|UW|MW|W|DBM)\b", raw.upper())
            unit = {"PW": "pW", "NW": "nW", "UW": "µW", "MW": "mW", "W": "W"}.get(unit.group(1), "dBm") if unit else "dBm"
            if not nums:
                return self._meas_text(f"Power: unexpected reply {raw!r}")
            l1, l2 = self._marker_nm(res.get("l1")), self._marker_nm(res.get("l2"))
            span = (l1 is not None and l2 is not None and lo_wl <= l1 < l2 <= hi_wl)
            a, b = (l1, l2) if span else (lo_wl, hi_wl)
            band = pg.LinearRegionItem((a, b), movable=False, brush=pg.mkBrush(63, 181, 255, 40),
                                       pen=pg.mkPen(acc, width=1, style=QtCore.Qt.PenStyle.DashLine))
            band.setZValue(-5)
            self._meas_add(band)
            where = f"L1–L2 {a:.2f}–{b:.2f} nm" if span else "whole span"
            return self._meas_text(f"<b>Power</b> · {where} · {t}<br><b style='font-size:17px'>{nums[0]:.2f} {unit}</b>")
        label, _, _ = WIDTH_METHODS[res["kind"]]
        center = nums[0] if nums else None
        width = nums[1] if len(nums) > 1 else None
        plausible = (center is not None and width is not None and width >= 0
                     and lo_wl - (hi_wl - lo_wl) <= center <= hi_wl + (hi_wl - lo_wl) and width <= 2 * (hi_wl - lo_wl))
        if not plausible:
            return self._meas_text(f"<b>{label}</b>: reply not recognised<br>{raw[:40]!r}")
        th = res.get("th")
        drop = th if th is not None else 3.0        # RMS methods: bar drawn at -3 dB for display only
        level = top * 10 ** (-drop / 10) if self._is_linear() else top - drop
        x1, x2 = center - width / 2, center + width / 2
        dash = pg.mkPen(acc, width=1, style=QtCore.Qt.PenStyle.DashLine)
        for x in (x1, x2):
            self._meas_add(pg.InfiniteLine(pos=x, angle=90, pen=dash))
        self._meas_add(pg.InfiniteLine(pos=center, angle=90, pen=pg.mkPen(acc, width=1, style=QtCore.Qt.PenStyle.DotLine)))
        self._meas_add(pg.PlotDataItem([x1, x2], [level, level], pen=pg.mkPen(acc, width=3),
                                       symbol="|", symbolSize=14, symbolPen=pg.mkPen(acc, width=3)))
        head = f"<b>Width {label}{f' {th:g} dB' if th is not None else ''}</b> · {t}"
        modes = f" · {nums[2]:g} mode{'s' if nums[2] != 1 else ''}" if len(nums) > 2 and res["kind"] != "notch" else ""
        self._meas_text(f"{head}<br>Δλ <b>{width:.3f}</b> nm{modes}<br>λc <b>{center:.3f}</b> nm")

    @staticmethod
    def _marker_nm(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        m = _NUM.findall(str(v))
        return float(m[0]) if m else None

    def _meas_add(self, item):
        item.setZValue(max(item.zValue(), 20) if not isinstance(item, pg.LinearRegionItem) else item.zValue())
        self.plot.addItem(item, ignoreBounds=True)
        self.meas_items.append(item)

    def _meas_text(self, html):
        self.meas_label.setText(html)
        self.meas_label.show()
        self.meas_label.raise_()
        self._place_reset_zoom()

    # ---------------------------------------------------------------- saving
    def save_csv(self):
        if not self.traces:
            self._warn("no trace yet")
            return
        # snapshot now: in REPEAT mode the traces may be replaced while the dialog is open
        traces = {t: (wl.copy(), lv.copy()) for t, (wl, lv) in sorted(self.traces.items())}
        values, stamp = dict(self.values), datetime.datetime.now()
        os.makedirs(DEFAULT_DIR, exist_ok=True)
        d = SaveDialog(self, self.save_dir, self.save_base or default_base())
        d.setGeometry(self.window().geometry())          # cover the whole 800x480 screen
        if not d.exec() or not d.path:
            return
        names = list(traces)
        unit = {t: ("dBm" if (traces[t][1] < 0).any() else "W") for t in names}   # raw OSA values
        wl0 = traces[names[0]][0]
        same_axis = all(len(traces[t][0]) == len(wl0) and np.allclose(traces[t][0], wl0) for t in names)
        if same_axis:      # one wavelength column, one level column per trace
            cols = ["wavelength_nm"] + [f"{t}_level_{unit[t]}" for t in names]
            rows = [",".join([f"{wl0[i]:.4f}"] + [f"{traces[t][1][i]:.4f}" for t in names])
                    for i in range(len(wl0))]
        else:              # e.g. a FIX trace from another range: wavelength/level pair per trace
            cols = [f"{t}_{k}" for t in names for k in ("wavelength_nm", f"level_{unit[t]}")]
            n = max(len(traces[t][0]) for t in names)
            rows = [",".join(f"{traces[t][0][i]:.4f},{traces[t][1][i]:.4f}" if i < len(traces[t][0]) else ","
                             for t in names) for i in range(n)]
        hdr = (f"# {self.osa_title}, {stamp:%Y-%m-%d %H:%M:%S}, traces={'+'.join(names)}, "
               + ", ".join(f"{k}={v}" for k, v in values.items()))
        try:
            with open(d.path, "w") as f:
                f.write(",".join(cols) + "\n" + hdr + "\n" + "\n".join(rows) + "\n")
                f.flush()
                os.fsync(f.fileno())
            if d.folder != DEFAULT_DIR:
                os.sync()                                # flush to the stick before it is pulled out
        except OSError as e:
            self._warn(f"save failed: {e}")
            return
        self.save_dir, self.save_base = d.folder, d.base
        where = "" if d.folder == DEFAULT_DIR else f" on USB {os.path.basename(d.folder)}"
        self._ok(f"saved {os.path.basename(d.path)}{where}")

    # ---------------------------------------------------------------- exit
    def exit_app(self):
        d = ChoiceDialog(self, "Exit the OSA program?", [("Exit", "exit")], None)
        if d.exec() and d.choice == "exit":
            self.close()

    def closeEvent(self, ev):
        if self.repeating:                      # don't leave the OSA sweeping in REPEAT
            self.worker.submit(lambda o: o.stop_sweep())
        self.repeating = False
        self.worker.cancel_flag.set()
        self.worker.stop(wait=5.0)     # let a running sweep stop so main() can return the OSA to LOCAL
        super().closeEvent(ev)


# ============================================================================ entry point
def main(argv=None):
    ap = argparse.ArgumentParser(description="ANDO AQ6315/AQ6317 touch-screen GUI")
    ap.add_argument("--mock", action="store_true", help="use the built-in simulator")
    ap.add_argument("--address", type=int, default=1, help="OSA GPIB address")
    ap.add_argument("--board", type=int, default=0)
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--size", default="800x480", help="window size when not fullscreen")
    ap.add_argument("--screenshot", help="render one sweep to PNG and exit")
    a = ap.parse_args(argv)

    if a.mock:
        tr, title = MockTransport(SimOsa(noise_db=0.3)), "OSA (simulator)"
    else:
        tr, title = LinuxGpibTransport(a.address, a.board), f"OSA @ GPIB{a.board}::{a.address}"
    setup_log()
    log.info("===== gui %s start: %s (%s)", GUI_VERSION, " ".join(sys.argv), __file__)
    trace_transport(tr)
    osa = Osa(tr)
    osa.connect()

    app = QtWidgets.QApplication(sys.argv[:1])
    app.setStyleSheet(STYLE)
    log.info("Qt platform: %s", app.platformName())
    for dev in QtGui.QInputDevice.devices():
        log.info("input device: %r type=%s", dev.name(), dev.type().name)
    win = MainWindow(osa, title)
    w, h = (int(x) for x in a.size.split("x"))
    win.resize(w, h)
    if a.fullscreen:
        win.showFullScreen()
        app.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.BlankCursor))
    else:
        win.show()

    if a.screenshot and a.screenshot.endswith("keypad.png"):
        def keypad():
            d = Keypad(win, "Center", 1550.0, 350, 1750, "nm", 2, 1.0)
            d.resize(w, h)
            d.show()
            QtCore.QTimer.singleShot(300, lambda: (d.grab().save(a.screenshot), app.quit()))
        QtCore.QTimer.singleShot(300, keypad)
    elif a.screenshot:
        def snap():
            win.peak()
            QtCore.QTimer.singleShot(600, lambda: (win.grab().save(a.screenshot), app.quit()))
        win.single()
        QtCore.QTimer.singleShot(800, snap)
    rc = app.exec()
    try:
        osa.close()
    except Exception:  # noqa: BLE001
        pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
