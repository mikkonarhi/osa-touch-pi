"""High-level AQ6315A/B control. Most methods are generated from commands.COMMANDS."""
from __future__ import annotations

import time
from typing import Optional

from . import parsing
from .commands import COMMANDS, Cmd, LIGHT_SET, SENS_REPLY, SENS_SET
from .errors import CommandError, OsaError, OsaTimeout
from .transport import Transport

try:
    import numpy as _np
except ImportError:                              # numpy optional
    _np = None

MAX_BUFFER = 512     # manual 9-4: receive buffer is 512 bytes (blanks excluded)


class Osa:
    """Control an ANDO/Yokogawa AQ6315A/B over GPIB.

    >>> osa = Osa(MockTransport()); osa.connect()
    >>> osa.set_center_span(1550, 20); osa.single_sweep()
    >>> wl, lv = osa.get_trace()
    """

    model = "AQ6315"

    def __init__(self, transport: Transport, check_errors: bool = True):
        self.t = transport
        self.check_errors_after_set = check_errors

    # ------------------------------------------------------------------ connection
    def connect(self, log_digits: int = 3) -> None:
        """Open the bus and put the instrument in a known talker state.

        Sends SD0 (',' string delimiter), BD0 (CRLF+EOI), HD0 (no header), LDTDIG, SRQ1, then
        reads (and clears) the status byte as required by manual 9.2.8(4).
        """
        self.t.open()
        self.send("SD0", "BD0", "HD0", f"LDTDIG{log_digits}", "SRQ1")
        self.status_byte()

    def close(self) -> None:
        try:
            self.t.local()
        finally:
            self.t.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    def identify(self) -> str:
        """The AQ6315 manual (ch. 9) lists no *IDN?, so identify via a harmless query.
        Tries *IDN? first (newer firmware/models), falls back to CTRWL?."""
        old = self.t.timeout
        try:
            self.t.set_timeout(2.0)
            try:
                self.t.write("*IDN?")
                return self.t.read()
            except OsaError:
                pass
        finally:
            self.t.set_timeout(old)
            self.status_byte()          # unsupported *IDN? sets the command-error bit; clear it
        return f"(no *IDN?; CTRWL? = {self.get_center_wl()} nm)"

    # ------------------------------------------------------------------ raw access
    def send(self, *codes: str) -> None:
        """Send one or more program codes (joined with ',' as in manual 9.2.5(2))."""
        msg = ",".join(codes)
        if len(msg.replace(" ", "")) > MAX_BUFFER:
            raise CommandError(f"command string > {MAX_BUFFER} bytes; split it")
        self.t.write(msg)

    send_raw = send

    def query_raw(self, code: str) -> str:
        self.t.write(code)
        return self.t.read()

    def status_byte(self) -> int:
        return self.t.serial_poll()

    def check_errors(self) -> None:
        """Serial-poll; raise CommandError on bit 3 (command/data error)."""
        stb = self.status_byte()
        flags = parsing.parse_status_byte_flags(stb)
        if flags["command_error"]:
            raise CommandError(f"instrument flagged a command/data error (status byte {stb:#04x})")
        if flags["buffer_overflow"]:
            raise CommandError("instrument receive buffer overflow")

    def warning(self) -> int:
        return int(parsing.first_number(self.query_raw("WARN?")))

    # ------------------------------------------------------------------ sweeping
    def single_sweep(self, wait: bool = True, timeout: float = 120.0) -> None:
        """Start a single sweep. With wait=True blocks until the sweep-done SRQ bit is seen.

        Sequence follows the manual's example (p. 9-52): SRQ1 -> clear status byte -> SGL -> poll.
        """
        self.send("SRQ1")
        self.status_byte()                      # clear any stale status
        self.send("SGL")
        if wait:
            self.wait_sweep_done(timeout)

    def repeat_sweep(self) -> None:
        self.send("RPT")

    def auto_sweep(self) -> None:
        self.send("AUTO")

    def stop_sweep(self) -> None:
        self.send("STP")

    def wait_sweep_done(self, timeout: float = 120.0, poll: float = 0.1, cancel=None) -> None:
        """Poll the status byte until bit 0 (sweep done). `cancel` is an optional callable
        returning True to abort (used by the GUI's Stop button)."""
        t0 = time.monotonic()
        while True:
            stb = self.status_byte()
            if stb & 0x08:
                raise CommandError(f"command error during sweep (status byte {stb:#04x})")
            if stb & 0x01:
                return
            if cancel is not None and cancel():
                self.stop_sweep()
                raise OsaError("sweep cancelled")
            if time.monotonic() - t0 > timeout:
                raise OsaTimeout(f"sweep not finished after {timeout} s")
            time.sleep(poll)

    # ------------------------------------------------------------------ convenience setters
    def set_center_span(self, center_nm: float, span_nm: float) -> None:
        self.set_center_wl(center_nm)
        self.set_span(span_nm)

    def set_range(self, start_nm: float, stop_nm: float) -> None:
        if stop_nm <= start_nm:
            raise ValueError("stop must be > start")
        self.set_start_wl(start_nm)
        self.set_stop_wl(stop_nm)

    def set_label(self, text: str) -> None:
        if len(text) > 50 or "'" in text:
            raise ValueError("label: max 50 chars, no quote")
        self.send(f"LBL'{text}'")

    def get_settings(self) -> dict:
        return {
            "center_nm": self.get_center_wl(),
            "span_nm": self.get_span(),
            "ref_level_dbm": self.get_ref_level(),
            "level_scale_db_div": self.get_level_scale(),
            "resolution_nm": self.get_resolution(),
            "averaging": self.get_averaging(),
            "sampling_points": self.get_sampling_points(),
            "sensitivity": self.get_sensitivity(),
            "monochromator": self.get_monochromator(),
        }

    # ------------------------------------------------------------------ data
    def _fetch(self, code: str) -> list[float]:
        self.t.write(code)
        return parsing.parse_trace(self.t.read())

    def get_trace_levels(self, trace: str = "A", first: Optional[int] = None, last: Optional[int] = None):
        """Level data (dBm in LOG, W in LIN) of trace A, B or C (LDATA/LDATB/LDATC)."""
        return self._fetch(self._data_code("LDAT", trace, first, last))

    def get_trace_wavelengths(self, trace: str = "A", first: Optional[int] = None, last: Optional[int] = None):
        """Wavelength axis in nm (WDATA/WDATB/WDATC)."""
        return self._fetch(self._data_code("WDAT", trace, first, last))

    def get_trace(self, trace: str = "A"):
        """(wavelength_nm, level) for the trace; numpy arrays if numpy is installed, else lists."""
        wl = self.get_trace_wavelengths(trace)
        lv = self.get_trace_levels(trace)
        if len(wl) != len(lv):
            raise OsaError(f"wavelength ({len(wl)}) and level ({len(lv)}) point counts differ")
        return (_np.array(wl), _np.array(lv)) if _np else (wl, lv)

    @staticmethod
    def _data_code(stem: str, trace: str, first, last) -> str:
        t = trace.upper()
        if t not in "ABC" or len(t) != 1:
            raise ValueError("trace must be A, B or C")
        code = f"{stem}{t}"                       # LDATA / WDATB ...
        if first is not None or last is not None:
            a = 1 if first is None else first
            b = 1001 if last is None else last
            if not (1 <= a <= b <= 1001):
                raise ValueError("range must satisfy 1 <= first <= last <= 1001")
            code += f"R{a}-R{b}"
        return code

    def get_memory_trace(self, memory: int, which: str = "level"):
        if not 0 <= memory <= 31:
            raise ValueError("memory 0..31")
        return self._fetch(("LMEM" if which == "level" else "WMEM") + f"{memory}")

    # ------------------------------------------------------------------ markers / analysis
    def get_marker(self) -> dict:
        return parsing.parse_marker(self.query_raw("MKR?"))

    def peak_search_marker(self) -> dict:
        """Peak search, then read the moving marker."""
        self.send("PKSR")
        return self.get_marker()

    def analysis_raw(self) -> str:
        """ANA? reply as text; format depends on which analysis (SMSR, WDM, ...) was executed."""
        return self.query_raw("ANA?")

    # ------------------------------------------------------------------ reference level
    def get_ref_level_any(self) -> tuple[float, str]:
        return parsing.parse_ref_level(self.query_raw("REFL?"))


# ====================================================================== method generation
def _fmt_number(c: Cmd, v: float) -> str:
    return f"{v:.{c.decimals}f}"


def _make_action(c: Cmd):
    def f(self: Osa):
        self.send(c.code)
    f.__name__ = c.name
    f.__doc__ = f"{c.doc}  [sends {c.code}; manual p. {c.page}]"
    return f


def _check_range(c: Cmd, v: float) -> None:
    if (c.lo is not None and c.hi is not None and not (c.lo <= v <= c.hi)) and v not in c.special:
        raise ValueError(f"{c.name}: {v} outside {c.lo}..{c.hi}{c.unit and ' ' + c.unit}"
                         f"{' (or ' + ', '.join(map(str, c.special)) + ')' if c.special else ''}")


def _make_number_setter(c: Cmd):
    def f(self: Osa, value: float):
        _check_range(c, float(value))
        self.send(f"{c.code}{_fmt_number(c, float(value))}")
        if self.check_errors_after_set:
            self.check_errors()
    f.__name__ = f"set_{c.name}"
    f.__doc__ = f"{c.doc} Range {c.lo}..{c.hi} {c.unit}. [sends {c.code}<value>; manual p. {c.page}]"
    return f


def _make_choice_setter(c: Cmd):
    def f(self: Osa, value):
        if c.enum and value not in c.enum and value not in c.enum.values():
            raise ValueError(f"{c.name}: {value!r} not in {sorted(map(str, c.enum))}")
        key = value if value in c.enum else {v: k for k, v in c.enum.items()}[value]
        if c.name == "sensitivity":
            code = SENS_SET[key]
        elif c.name == "light_mode":
            code = LIGHT_SET[key]
        else:
            code = f"{c.code}{c.enum[key]}"
        self.send(code)
        if self.check_errors_after_set:
            self.check_errors()
    f.__name__ = f"set_{c.name}"
    f.__doc__ = f"{c.doc} Options: {list(c.enum)}. [manual p. {c.page}]"
    return f


def _make_getter(c: Cmd):
    def f(self: Osa):
        txt = self.query_raw(c.query)
        if c.name == "sensitivity":
            return SENS_REPLY[int(parsing.first_number(txt))]
        if c.reply == "str":
            return txt
        v = parsing.first_number(txt)
        if c.reply == "int":
            v = int(v)
        if c.reply == "enum" or (c.enum and c.reply == "int"):
            rev = {val: k for k, val in c.enum.items()}
            return rev.get(int(v), int(v))
        return v
    f.__name__ = f"get_{c.name}"
    f.__doc__ = f"Query {c.query}. {c.doc} [manual p. {c.page}]"
    return f


def _install() -> None:
    for c in COMMANDS.values():
        if c.kind == "action":
            if not hasattr(Osa, c.name):
                setattr(Osa, c.name, _make_action(c))
            continue
        if c.kind == "number" and c.name != "ref_level_any":
            setattr(Osa, f"set_{c.name}", _make_number_setter(c))
        elif c.kind == "choice":
            setattr(Osa, f"set_{c.name}", _make_choice_setter(c))
        if c.query and not hasattr(Osa, f"get_{c.name}"):
            setattr(Osa, f"get_{c.name}", _make_getter(c))


_install()
