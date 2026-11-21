"""Tests against the simulator. They check the library's own logic and that the command
strings match the manual's examples (p. 9-52 / 9-57); they cannot prove the real instrument agrees.
"""
import pytest

from ando_osa import CommandError, MockTransport, Osa, OsaTimeout, ParseError
from ando_osa import parsing, transport
from ando_osa.commands import COMMANDS


@pytest.fixture
def osa():
    o = Osa(MockTransport())
    o.connect()
    o.identify()
    yield o
    o.close()


def sent(o):
    return o.t.sim.log


def test_manual_example_setup_strings(osa):
    """Manual p. 9-52 line 1110: CTRWL1550.00,SPAN20.0,REFL-15.0,LSCL5.0,RESLN0.1,AVG1,SNHD"""
    osa.t.sim.log.clear()
    osa.set_center_wl(1550)
    osa.set_span(20)
    osa.set_ref_level(-15)
    osa.set_level_scale(5)
    osa.set_resolution(0.1)
    osa.set_averaging(1)
    osa.set_sensitivity("norm_hold")
    assert sent(osa) == ["CTRWL1550.00", "SPAN20.0", "REFL-15.0", "LSCL5.0", "RESLN0.10", "AVG1", "SNHD"]


def test_trace_mode_codes_exist(osa):
    for name in ("write_a", "display_a", "fix_b", "blank_b", "fix_c", "blank_c"):
        getattr(osa, name)()
    assert sent(osa)[-6:] == ["WRTA", "DSPA", "FIXB", "BLKB", "FIXC", "BLKC"]


def test_range_validation(osa):
    with pytest.raises(ValueError):
        osa.set_center_wl(300)
    with pytest.raises(ValueError):
        osa.set_resolution(20)
    with pytest.raises(ValueError):
        osa.set_sampling_points(5)         # min is 11
    osa.set_span(0)                        # zero span explicitly allowed


def test_choice_validation(osa):
    with pytest.raises(ValueError):
        osa.set_sensitivity("ultra")


def test_choice_by_value(osa):
    """Choice setters accept the key or the numeric value (v0.1 crashed for light_mode by value)."""
    osa.set_light_mode(0)
    assert sent(osa)[-1] == "PLMES"
    osa.set_sensitivity(1)
    assert sent(osa)[-1] == "SHI1"
    osa.set_smsr_ref(2)
    assert sent(osa)[-1] == "SMSR2"
    osa.set_monochromator(1)
    assert sent(osa)[-1] == "MONO1"


def test_device_error_detected(osa):
    osa.send("SPAN9999")
    with pytest.raises(CommandError):
        osa.check_errors()


def test_sweep_and_trace(osa):
    osa.set_center_span(1550, 20)
    osa.set_sampling_points(101)
    osa.single_sweep()
    wl, lv = osa.get_trace()
    assert len(wl) == len(lv) == 101
    assert wl[0] == pytest.approx(1540.0) and wl[-1] == pytest.approx(1560.0)
    assert max(lv) == pytest.approx(-10.0, abs=0.5)


def test_sweep_cancel(osa):
    osa.t.sim._sweep = lambda: None          # sweep never finishes
    from ando_osa.errors import OsaError
    with pytest.raises(OsaError):
        osa.single_sweep(wait=False)
        osa.wait_sweep_done(timeout=5, poll=0.01, cancel=lambda: True)
    assert sent(osa)[-1] == "STP"


def test_partial_trace_range(osa):
    osa.single_sweep()
    part = osa.get_trace_levels("A", 10, 19)
    assert len(part) == 10
    assert sent(osa)[-1] == "LDATAR10-R19"


def test_bad_trace_args(osa):
    with pytest.raises(ValueError):
        osa.get_trace_levels("D")
    with pytest.raises(ValueError):
        osa.get_trace_levels("A", 0, 10)


def test_command_buffer_limit(osa):
    with pytest.raises(CommandError):
        osa.send(*(["CTRWL1550.00"] * 60))


def test_marker(osa):
    m = osa.peak_search_marker()
    assert m["x"] == pytest.approx(1550.0)


def test_getters_roundtrip(osa):
    osa.set_averaging(16)
    assert osa.get_averaging() == 16
    osa.set_monochromator("double")
    assert osa.get_monochromator() == "double"


def test_get_settings(osa):
    s = osa.get_settings()
    assert s["center_nm"] == pytest.approx(1550.0) and s["sensitivity"] == "norm_hold"


def test_parse_trace_variants():
    assert parsing.parse_trace(" 3,-1.50,-2.50,-3.50") == [-1.5, -2.5, -3.5]
    assert parsing.parse_trace("DBM 3,-1.50,-2.50,-3.50") == [-1.5, -2.5, -3.5]       # header on
    assert parsing.parse_trace("3\r\n-1.5\r\n-2.5\r\n-3.5") == [-1.5, -2.5, -3.5]     # SD1
    assert parsing.parse_trace("2,1.000E-06,2.500E-07") == [1e-6, 2.5e-7]               # LIN scale
    with pytest.raises(ParseError):
        parsing.parse_trace("5,1,2")


def test_ref_level_parse():
    assert parsing.parse_ref_level("-15.0") == (-15.0, "dBm")
    assert parsing.parse_ref_level("PW 1.00") == (1.0, "PW")


def test_status_flags():
    f = parsing.parse_status_byte_flags(65)
    assert f["rqs"] and f["sweep_done"] and not f["command_error"]


def test_table_sanity():
    assert len(COMMANDS) > 200
    assert COMMANDS["center_wl"].code == "CTRWL"
    for c in COMMANDS.values():
        if c.kind == "number":
            assert c.lo is not None and c.hi is not None and c.lo <= c.hi, c.name


# ---------------------------------------------------------------- linux-gpib transport helpers
def test_lgpib_timeout_codes():
    f = transport._lgpib_timeout_code
    assert f(0.3) == 10 and f(1) == 11 and f(2) == 12 and f(10) == 13 and f(120) == 16 and f(5000) == 17


def test_stb_conversion():
    assert transport._stb_to_int(b"\x41") == 0x41
    assert transport._stb_to_int(65) == 65
    assert transport._stb_to_int("A") == 65


def test_timeout_detection():
    class GpibError(Exception):
        pass
    assert transport._is_timeout(GpibError("read() error: Connection timed out (errno: 110)"))
    assert not transport._is_timeout(GpibError("write() error: No such device"))


class _FakeGpib:
    """Stands in for linux-gpib's Gpib.Gpib object."""
    def __init__(self, *a):
        self.args, self.id, self.buf, self.written = a, 3, [], []

    def write(self, b): self.written.append(b)
    def read(self, n): return self.buf.pop(0)
    def serial_poll(self): return 1
    def timeout(self, code): self.tmo = code
    def ibloc(self): pass
    def clear(self): pass

    def close(self):                     # real Gpib.close() fails if called on a closed id
        if self.id is None:
            raise RuntimeError("close() failed: invalid descriptor")
        self.id = None

    def __del__(self):                   # real Gpib.__del__ calls self.close()
        self.close()


def test_linux_gpib_transport_with_fake(monkeypatch):
    import sys, types
    fake_mod = types.ModuleType("Gpib")
    fake_mod.Gpib = _FakeGpib
    monkeypatch.setitem(sys.modules, "Gpib", fake_mod)
    monkeypatch.setitem(sys.modules, "gpib", types.SimpleNamespace(close=lambda i: None))
    t = transport.LinuxGpibTransport(address=1, timeout=10)
    t.open()
    assert t._dev.args == (0, 1, 0, 13, 1, 0)
    t._dev.buf.append(b"1550.00\r\n")
    t.write("CTRWL?")
    assert t._dev.written == [b"CTRWL?\r\n"] and t.read() == "1550.00"
    assert t.serial_poll() == 1
    dev = t._dev
    t.close()
    t.close()                                       # second close is a no-op
    assert dev.id is None
    dev.__del__()                                   # GC-time close must not raise
