"""GPIB transports. Same small interface, three back ends:

    LinuxGpibTransport  linux-gpib Python bindings (Raspberry Pi + GPIB4PI, gpib_bitbang driver)
    PyVisaTransport     any VISA GPIB adapter (NI, Keysight, ... ) on a laptop
    MockTransport       in-process SimOsa, no hardware

NOT yet exercised on real hardware: LinuxGpibTransport and PyVisaTransport follow the documented
APIs but need the bring-up ladder (tools/bringup.py) to confirm.

v0.2 fixes (review against linux-gpib 4.3.x python bindings):
  * timeout table: 0.3 s is T300ms = 10 (was 8 = T30ms)
  * serial poll is Gpib.serial_poll() (no rsp() method); result normalised to 0..255
  * a linux-gpib read timeout says "Connection timed out" (errno 110) / iberr EABO=6, not "timeout"
  * close() calls Gpib.close() once (its __del__ closes again, guarded by _own); local() via ibloc()
  (all checked against ~/gpib-build/.../language/python/Gpib.py + gpibinter.c on the Pi)
"""
from __future__ import annotations

import abc
from typing import Optional

from .errors import OsaError, OsaTimeout

# linux-gpib timeout codes (gpib_user.h):
# T10ms=7 T30ms=8 T100ms=9 T300ms=10 T1s=11 T3s=12 T10s=13 T30s=14 T100s=15 T300s=16 T1000s=17
_LGPIB_TMO = [(0.01, 7), (0.03, 8), (0.1, 9), (0.3, 10), (1, 11), (3, 12), (10, 13), (30, 14),
              (100, 15), (300, 16)]
_EABO = 6          # iberr: I/O aborted (this is what a timeout looks like)


def _lgpib_timeout_code(seconds: float) -> int:
    for limit, code in _LGPIB_TMO:
        if seconds <= limit:
            return code
    return 17  # T1000s


def _stb_to_int(r) -> int:
    if isinstance(r, (bytes, bytearray)):
        return r[0] if r else 0
    if isinstance(r, str):
        return ord(r[0]) if r else 0
    return int(r)


def _is_timeout(e: Exception) -> bool:
    s = str(e).lower()
    return ("timeout" in s or "timed out" in s or "errno: 110" in s
            or getattr(e, "code", None) == _EABO or "eabo" in s)


class Transport(abc.ABC):
    terminator = "\r\n"
    timeout: float = 10.0

    @abc.abstractmethod
    def open(self) -> None: ...

    @abc.abstractmethod
    def close(self) -> None: ...

    @abc.abstractmethod
    def write(self, text: str) -> None: ...

    @abc.abstractmethod
    def read(self) -> str:
        """Read one reply block (until EOI) and return it without trailing CR/LF."""

    @abc.abstractmethod
    def serial_poll(self) -> int: ...

    def clear(self) -> None:
        """Selected device clear (SDC). On the AQ6315 this equals a power-on reset (manual 9-49)."""

    def local(self) -> None:
        """Return the instrument to local (GTL)."""

    def set_timeout(self, seconds: float) -> None:
        self.timeout = seconds

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()


class LinuxGpibTransport(Transport):
    """linux-gpib via its 'Gpib' Python module (Debian package python3-gpib)."""

    def __init__(self, address: int = 1, board: int = 0, timeout: float = 10.0, sad: int = 0):
        self.address, self.board, self.sad, self.timeout = address, board, sad, timeout
        self._dev = None

    def open(self) -> None:
        import Gpib  # type: ignore  (provided by python3-gpib)
        # Gpib(name_or_board, pad, sad, timeout, send_eoi, eos_mode)
        self._dev = Gpib.Gpib(self.board, self.address, self.sad,
                              _lgpib_timeout_code(self.timeout), 1, 0)

    def close(self) -> None:
        """Close exactly once. Gpib.Gpib.__del__ also calls close(), so after closing we disarm
        it; otherwise libgpib prints 'invalid descriptor' and GpibError at garbage collection."""
        dev, self._dev = self._dev, None
        if dev is None:
            return
        try:
            dev.close()
        except Exception:  # noqa: BLE001
            pass
        dev.close = lambda: None

    def set_timeout(self, seconds: float) -> None:
        self.timeout = seconds
        if self._dev is not None:
            self._dev.timeout(_lgpib_timeout_code(seconds))

    def _call(self, fn, *a):
        if self._dev is None:
            raise OsaError("transport not open")
        try:
            return fn(*a)
        except Exception as e:  # gpib.GpibError
            if _is_timeout(e):
                raise OsaTimeout(str(e)) from e
            raise OsaError(f"GPIB error: {e}") from e

    def write(self, text: str) -> None:
        self._call(self._dev.write, (text + self.terminator).encode("ascii"))

    def read(self) -> str:
        data = self._call(self._dev.read, 200000)          # returns at EOI
        return data.decode("ascii", "replace").strip("\r\n ")

    def serial_poll(self) -> int:
        # Gpib.py (linux-gpib 4.3.6) has serial_poll(); there is no rsp() method
        return _stb_to_int(self._call(self._dev.serial_poll)) & 0xFF

    def clear(self) -> None:
        self._call(self._dev.clear)

    def local(self) -> None:
        if self._dev is None:
            return
        try:
            self._dev.ibloc()
        except Exception:  # noqa: BLE001
            pass


class PyVisaTransport(Transport):
    def __init__(self, resource: str = "GPIB0::1::INSTR", timeout: float = 10.0, backend: str = ""):
        self.resource, self.timeout, self.backend = resource, timeout, backend
        self._rm = self._inst = None

    def open(self) -> None:
        import pyvisa
        self._rm = pyvisa.ResourceManager(self.backend) if self.backend else pyvisa.ResourceManager()
        self._inst = self._rm.open_resource(self.resource)
        self._inst.timeout = int(self.timeout * 1000)
        self._inst.write_termination = "\r\n"
        self._inst.read_termination = None

    def close(self) -> None:
        if self._inst:
            self._inst.close()
        if self._rm:
            self._rm.close()

    def set_timeout(self, seconds: float) -> None:
        self.timeout = seconds
        if self._inst:
            self._inst.timeout = int(seconds * 1000)

    def write(self, text: str) -> None:
        self._inst.write(text)

    def read(self) -> str:
        import pyvisa
        try:
            return self._inst.read_raw().decode("ascii", "replace").strip("\r\n ")
        except pyvisa.VisaIOError as e:
            raise OsaTimeout(str(e)) from e

    def serial_poll(self) -> int:
        return int(self._inst.read_stb())

    def clear(self) -> None:
        self._inst.clear()


class MockTransport(Transport):
    def __init__(self, sim=None):
        from .simulator import SimOsa
        self.sim = sim or SimOsa()

    def open(self) -> None: ...
    def close(self) -> None: ...

    def write(self, text: str) -> None:
        self.sim.write(text)

    def read(self) -> str:
        try:
            return self.sim.read()
        except TimeoutError as e:
            raise OsaTimeout(str(e)) from e

    def serial_poll(self) -> int:
        return self.sim.serial_poll()
