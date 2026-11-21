"""Simulated AQ6315 for developing/testing without hardware.

Understands the command table in commands.py (range checks, queries, sweep + status byte,
LDATA/WDATA). It is deliberately simple: not a model of the real optics, and reply
formatting follows Table 9-4 only as well as the scan could be read.
"""
from __future__ import annotations

import math
import time
import random
import re
from collections import deque

from .commands import BY_CODE, COMMANDS, Cmd, SENS_SET, LIGHT_SET

_SENS_NUM = {"SHI1": 1, "SHI2": 2, "SHI3": 3, "SNHD": 4, "SNAT": 5}
_QUERIES = {c.query: c for c in COMMANDS.values() if c.query}
_CODES_BY_LEN = sorted(BY_CODE, key=len, reverse=True)

_DEFAULTS = {
    "CTRWL": 1550.0, "STAWL": 1500.0, "STPWL": 1600.0, "SPAN": 100.0, "REFL": -20.0, "LSCL": 10.0,
    "RESLN": 1.0, "AVG": 1, "SMPL": 501, "SENS": 4, "MONO": 0, "CHOP": 0, "SEGP": 101, "LSUNT": 0,
    "SD": 0, "BD": 0, "HD": 0, "SRQ": 0, "SRMSK": 0, "LDTDIG": 2, "ATREF": 0, "ATCTR": 0, "ATSR": 0,
    "MKUNT": 0, "ZSWPT": 0, "SWPI": 0, "MESWL": 0, "CWPLS": 1, "ACTV": 0,
    "THRTH": 3.0, "ENVT1": 3.0, "NCHTH": 3.0, "RMSTH": 20.0, "PRMTH": 20.0, "THRK": 1.0,
}
# trace actions: (kind, trace, value). Modes follow TRA?/TRB?/TRC?: 0 WRITE, 1 FIX, 2 MAX/MIN HOLD or C=A-B,
# 3 ROLL AVG or C=B-A.
_TRACE_ACTIONS = {
    "WRTA": ("mode", "A", 0), "FIXA": ("mode", "A", 1), "MAXA": ("mode", "A", 2),
    "WRTB": ("mode", "B", 0), "FIXB": ("mode", "B", 1), "MINB": ("mode", "B", 2),
    "WRTC": ("mode", "C", 0), "FIXC": ("mode", "C", 1), "A-BC": ("mode", "C", 2), "B-AC": ("mode", "C", 3),
    "B=A": ("copy", "A", "B"), "C=A": ("copy", "A", "C"), "A=B": ("copy", "B", "A"),
    "C=B": ("copy", "B", "C"), "A=C": ("copy", "C", "A"), "B=C": ("copy", "C", "B"),
    "CLR": ("clear", None, None),
}


class SimOsa:
    def __init__(self, peaks=((1550.0, -10.0, 0.4), (1530.0, -35.0, 0.3)), noise_db: float = 0.0):
        self.s = dict(_DEFAULTS)
        self.peaks = peaks            # (wavelength nm, level dBm, fwhm nm)
        self.noise_db = noise_db      # random ripple added per sweep (GUI demo); 0 for tests
        self.out: deque[str] = deque()
        self.stb = 0                  # status byte without RQS
        self.sweeping = False
        self.log: list[str] = []      # every code received, for tests
        self.trace_a: list[float] = []
        self.wl: list[float] = []
        self.traces = {t: ([], []) for t in "ABC"}     # (wavelengths, levels) per trace
        self.mode = {"A": 0, "B": 1, "C": 1}           # A WRITE, B and C FIX after power-on
        self.repeat = False                            # RPT running: sweeps every sweep_time_s
        self.sweep_time_s = 0.3
        self._last_sweep = 0.0
        self.below_floor_dbm = None                    # e.g. -60: points below it read as -210
        self.marker = None

    # -- bus-level API used by the mock transport --------------------------------------------
    def write(self, text: str) -> None:
        text = text.replace("\r", "").replace("\n", "").replace(" ", "")
        for tok in [t for t in text.split(",") if t]:
            self.log.append(tok)
            self._exec(tok)

    def read(self) -> str:
        if not self.out:
            raise TimeoutError("simulator: nothing to read")
        return self.out.popleft()

    def serial_poll(self) -> int:
        if self.repeat and time.monotonic() - self._last_sweep >= self.sweep_time_s:
            self._sweep()                              # REPEAT: next sweep finished -> bit 0
        stb = self.stb
        if self.s["SRQ"] and stb:
            stb |= 0x40
        self.stb = 0
        return stb

    # -- internals ----------------------------------------------------------------------------
    def _cmderr(self):
        self.stb |= 0x08

    def _fmt(self, v: float, dec: int) -> str:
        return f"{v:.{dec}f}"

    def _exec(self, tok: str) -> None:
        if self._exec_data(tok):
            return
        if tok.endswith("?"):
            return self._query(tok)
        if tok.startswith("LBL"):
            return
        if tok in _SENS_NUM:
            self.s["SENS"] = _SENS_NUM[tok]
            return
        if tok in LIGHT_SET.values():
            self.s["CWPLS"] = 1 if tok == "CLMES" else 0
            return
        if tok == "LSCLLIN":                           # linear level scale: LSCL? -> 0, data in W
            self.s["LSCL"] = 0.0
            return
        m = re.fullmatch(r"REFL([PNUM])([0-9.]+)", tok)
        if m:                                          # linear ref level, e.g. REFLU10.00
            exp = {"P": -9, "N": -6, "U": -3, "M": 0}[m.group(1)]
            self.s["REFL"] = 10 * math.log10(float(m.group(2)) * 10 ** exp)
            return
        for code in _CODES_BY_LEN:
            if tok.startswith(code):
                return self._set(BY_CODE[code], code, tok[len(code):])
        self._cmderr()

    def _set(self, c: Cmd, code: str, arg: str) -> None:
        if c.kind == "action":
            if arg:
                return self._cmderr()
            if code in ("SGL", "RPT", "AUTO", "SMEAS"):
                self.repeat = code == "RPT"
                self._sweep()
            elif code == "STP":
                self.sweeping = False
                self.repeat = False
            elif code == "CTR=P":
                self.s["CTRWL"] = max(self.peaks, key=lambda p: p[1])[0]
                self._recompute_range("CTRWL")
            elif code == "REF=P":
                self.s["REFL"] = max(self.peaks, key=lambda p: p[1])[1]
            elif code in ("MKR1", "PKSR", "NSR", "NSRR", "NSRL"):
                self._search(code)
            elif code == "MKCL":
                self.marker = None
            elif code == "LMKCL":
                self.s.pop("L1MK", None)
                self.s.pop("L2MK", None)
            elif code in ("SWTHR", "SWENV", "SWRMS", "SWPRM", "SWNCH", "PWR"):
                self.last_analysis = code
                self._analyze(code)
            elif code in _TRACE_ACTIONS:
                self._trace_action(*_TRACE_ACTIONS[code])
            return
        try:
            v = float(arg)
        except ValueError:
            return self._cmderr()
        if c.kind == "number":
            ok = (c.lo <= v <= c.hi) or v in c.special
            if not ok:
                return self._cmderr()
        elif c.kind == "choice" and c.enum and v not in c.enum.values():
            return self._cmderr()
        self.s[code] = v
        if code in ("RAVA", "RAVB"):
            self.mode[code[-1]] = 3
        self._recompute_range(code)

    def _recompute_range(self, code: str) -> None:
        if code in ("SPAN", "CTRWL"):
            self.s["STAWL"] = self.s["CTRWL"] - self.s["SPAN"] / 2
            self.s["STPWL"] = self.s["CTRWL"] + self.s["SPAN"] / 2
        if code in ("STAWL", "STPWL"):
            self.s["CTRWL"] = (self.s["STAWL"] + self.s["STPWL"]) / 2
            self.s["SPAN"] = self.s["STPWL"] - self.s["STAWL"]

    def _sweep(self):
        n = int(self.s["SMPL"])
        start, stop = self.s["STAWL"], self.s["STPWL"]
        self.wl = [start + (stop - start) * i / (n - 1) for i in range(n)]
        floor = -80.0
        res = max(self.s["RESLN"], 0.05)
        lv = []
        for w in self.wl:
            p = 10 ** (floor / 10)
            for (w0, l0, fwhm) in self.peaks:
                sigma = math.hypot(fwhm, res) / 2.355
                p += 10 ** (l0 / 10) * math.exp(-0.5 * ((w - w0) / sigma) ** 2)
            v = 10 * math.log10(p)
            if self.noise_db:
                v += random.gauss(0, self.noise_db)
            if self.below_floor_dbm is not None and v < self.below_floor_dbm:
                v = -210.0                             # AQ6317B: below the measuring range
            lv.append(v)
        for t, hold in (("A", max), ("B", min)):
            m = self.mode[t]
            old_wl, old_lv = self.traces[t]
            if m == 2 and len(old_lv) == len(lv):
                self.traces[t] = (list(self.wl), [hold(a, b) for a, b in zip(old_lv, lv)])
            elif m != 1:                               # WRITE / ROLL AVG (no real averaging here)
                self.traces[t] = (list(self.wl), list(lv))
        self._update_c()
        self.trace_a = self.traces["A"][1]
        self._last_sweep = time.monotonic()
        # like the AQ6317B (as seen in the log): a new sweep clears the analysis result, unless
        # auto-analysis (ATANA1) re-runs the last selected analysis after each sweep
        if self.s.get("ATANA") == 1 and getattr(self, "last_analysis", None):
            self._analyze(self.last_analysis)
        else:
            self.ana = ""
        self.sweeps = getattr(self, "sweeps", 0) + 1
        self.stb |= 0x01          # sweep done
        self.sweeping = False

    def _trace_action(self, kind, a, b):
        if kind == "mode":
            self.mode[a] = b
            self._update_c()
        elif kind == "copy":
            self.traces[b] = (list(self.traces[a][0]), list(self.traces[a][1]))
        elif kind == "clear":
            self.traces = {t: ([], []) for t in "ABC"}
            self.trace_a = []

    def _local_maxima(self):
        t = "ABC"[int(self.s.get("ACTV", 0))]
        wl, lv = self.traces[t]
        return [(wl[i], lv[i]) for i in range(1, len(lv) - 1)
                if lv[i] > -200 and lv[i] >= lv[i - 1] and lv[i] > lv[i + 1]]

    def _search(self, code):
        """Peak / next-peak searches on the active trace's local maxima."""
        peaks = self._local_maxima()
        if not peaks:                                  # nothing swept yet: built-in peak list
            peaks = [(w, lv) for w, lv, _ in self.peaks]
        m = self.marker
        if code in ("MKR1", "PKSR") or m is None:
            self.marker = max(peaks, key=lambda p: p[1])
        elif code == "NSR":
            lower = [p for p in peaks if p[1] < m[1]]
            if lower:
                self.marker = max(lower, key=lambda p: p[1])
        else:
            side = [p for p in peaks if (p[0] > m[0] if code == "NSRR" else p[0] < m[0])]
            if side:
                self.marker = max(side, key=lambda p: p[1])

    def _analyze(self, code):
        """Analysis on the active trace. ANA? reply format assumed (not yet confirmed on the AQ6317B):
        spectral width -> 'center_nm,width_nm,modes'; PWR -> 'power_dBm'."""
        t = "ABC"[int(self.s.get("ACTV", 0))]
        wl, lv = self.traces[t]
        pts = [(w, v) for w, v in zip(wl, lv) if v > -200]
        if not pts:
            self.ana = ""
            return
        if code == "PWR":
            l1, l2 = self.s.get("L1MK"), self.s.get("L2MK")
            if l1 is not None and l2 is not None and l1 < l2:
                pts = [(w, v) for w, v in pts if l1 <= w <= l2] or pts
            p = sum(10 ** (v / 10) for _, v in pts)
            self.ana = f"{10 * math.log10(p):.2f}"
            return
        th = {"SWTHR": "THRTH", "SWENV": "ENVT1", "SWNCH": "NCHTH"}.get(code)
        top = max(v for _, v in pts)
        if code == "SWNCH":
            level = top - self.s["NCHTH"]
            below = [w for w, v in pts if v < level]
            lo, hi = (min(below), max(below)) if below else (pts[0][0], pts[0][0])
            self.ana = f"{(lo + hi) / 2:.3f},{hi - lo:.3f}"
            return
        level = top - (self.s[th] if th else 3.0)
        above = [w for w, v in pts if v >= level]
        lo, hi = min(above), max(above)
        modes = sum(1 for i in range(1, len(pts) - 1)
                    if pts[i][1] >= level and pts[i][1] >= pts[i - 1][1] and pts[i][1] > pts[i + 1][1])
        self.ana = f"{(lo + hi) / 2:.3f},{hi - lo:.3f},{max(modes, 1)}"

    def _update_c(self):
        m = self.mode["C"]
        (wa, la), (wb, lb) = self.traces["A"], self.traces["B"]
        if m == 0:
            self.traces["C"] = (list(wa), list(la))
        elif m in (2, 3) and la and len(la) == len(lb):
            sign = 1 if m == 2 else -1
            self.traces["C"] = (list(wa), [sign * (x - y) for x, y in zip(la, lb)])

    def _data(self, tok: str, vals: list[float], dec: int) -> None:
        m = re.search(r"R(\d+)-R(\d+)", tok)
        a, b = (int(m.group(1)), int(m.group(2))) if m else (1, len(vals))
        part = vals[a - 1:b]
        sd = "," if self.s["SD"] == 0 else "\r\n"
        hdr = "DBM " if self.s["HD"] else " "
        self.out.append(hdr + sd.join([str(len(part))] + [self._fmt(v, dec) for v in part]))

    def _query(self, tok: str) -> None:
        c = _QUERIES.get(tok)
        if c is None:
            return self._cmderr()
        key = c.code
        if tok == "ANA?":
            self.out.append(getattr(self, "ana", ""))
            return
        if tok in ("TRA?", "TRB?", "TRC?"):
            self.out.append(str(self.mode[tok[2]]))
        elif tok == "SWEEP?":
            self.out.append("2" if self.repeat else "0")
        elif tok == "REFL?" and self.s["LSCL"] == 0:
            mw = 10 ** (self.s["REFL"] / 10)
            for unit, f in (("MW", 1.0), ("UW", 1e-3), ("NW", 1e-6), ("PW", 1e-9)):
                if mw >= f or unit == "PW":
                    self.out.append(f"{unit}{mw / f:7.2f}")
                    break
        elif tok == "SENS?":
            self.out.append(str(int(self.s["SENS"])))
        elif tok in ("MKR?", "MKR1?", "MKR2?"):
            if self.marker:
                self.out.append(f"{self.marker[0]:.3f},{self.marker[1]:.2f}")
            else:
                self.out.append("")
        elif tok == "WARN?":
            self.out.append("0")
        elif key in self.s:
            v = self.s[key]
            self.out.append(self._fmt(v, c.decimals) if c.reply in ("float", "str") else str(int(v)))
        else:
            self.out.append("0")

    # LDATA/WDATA are write-then-read without '?': intercept before generic dispatch
    def _exec_data(self, tok: str) -> bool:
        if len(tok) >= 5 and tok[:4] in ("LDAT", "WDAT") and tok[4] in "ABC":
            wl, lv = self.traces[tok[4]]
            if tok[0] == "L":
                if self.s["LSCL"] == 0:                # LIN: level data in W (exponent format)
                    lin = [0.0 if v <= -200 else 10 ** (v / 10) * 1e-3 for v in lv]
                    m = re.search(r"R(\d+)-R(\d+)", tok)
                    a, b = (int(m.group(1)), int(m.group(2))) if m else (1, len(lin))
                    part = lin[a - 1:b]
                    self.out.append(" " + ",".join([str(len(part))] + [f"{v:.3E}" for v in part]))
                    return True
                self._data(tok, lv, 3 if self.s["LDTDIG"] == 3 else 2)
            else:
                self._data(tok, wl, 3)
            return True
        return False
