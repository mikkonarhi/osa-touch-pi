# ando_osa

Python control of ANDO / Yokogawa **AQ6315A/B** optical spectrum analyzers over GPIB, with a
touch-screen GUI. Built for a Raspberry Pi 4B (Pi OS Trixie) + GPIB4PI (linux-gpib 4.3.6,
`gpib_bitbang`). Command codes come from manual chapter 9 (pages 9-3 .. 9-57).

**Status: v0.2. Library + GUI tested against the simulator. Not yet run on a real instrument.**

## Pi install (one time)

linux-gpib was built in `~/gpib-build` (user-space `.deb`s + kernel modules with the
`compat-timer-6.16.patch`). This installs those, writes the config, and adds the Python packages:

```bash
cd ~/Documents/ando_osa
sudo bash tools/pi_install.sh                       # GPIB4PI rev 2.1: default pin map
sudo reboot
bash tools/pi_check.sh                              # writes logs/pi_check.log
python3 tools/bringup.py --no-instrument --yes      # driver + interface, no OSA needed
```

`PIN_MAP` is the `gpib_bitbang` pin map. This setup uses a **GPIB4PI rev 2.1** board, which uses the
driver default `elektronomikon` (REN on GPIO27); only the old rev 1.1 board needs `PIN_MAP=gpib4pi-1.1`.
Display: official 7" touch screen, 800x480 (GUI default size). OSA GPIB address: 1 (to be confirmed). Stages can be run separately: `sudo bash tools/pi_install.sh config`.

## Quick start

```bash
bash tools/run_gui.sh --mock                    # GUI on the simulator
bash tools/run_gui.sh --address 1 --fullscreen  # GUI on the real OSA (GPIB address 1)
python3 -m pytest                               # 22 tests
python3 tools/bringup.py --mock --yes
```

```python
from ando_osa import Osa, LinuxGpibTransport, MockTransport
with Osa(LinuxGpibTransport(address=1)) as osa:     # or Osa(MockTransport())
    osa.set_center_span(1550, 20)
    osa.set_resolution(0.1)
    osa.set_sensitivity("high1")
    osa.single_sweep()                              # waits for the sweep-done status bit
    wl, lv = osa.get_trace("A")
    print(osa.get_settings(), osa.peak_search_marker())
```

All ~200 program codes in the table are callable: `docs/COMMANDS.md` lists every method
(`set_*`/`get_*` or plain action names), its GPIB string, range and manual page.
Anything missing: `osa.send("CODE")` / `osa.query_raw("CODE?")`.

## GUI

`src/ando_osa/gui.py` (PyQt6 via pyqtgraph). Fits the 800x480 7" display; `--size WxH` for others.
SINGLE / REPEAT / STOP, peak search, peak→center, CSV save to `~/osa_traces/`, and tiles for
center, span, ref level, scale, resolution, sensitivity, averaging and points (tap → on-screen
keypad). Tapping the plot drops a local marker. All GPIB traffic runs on one worker thread.

## Layout

| File | Purpose |
|---|---|
| `src/ando_osa/commands.py` | the command table (single source of truth, one entry per code) |
| `src/ando_osa/osa.py` | `Osa` class; methods generated from the table + hand-written sweep/trace helpers |
| `src/ando_osa/transport.py` | `LinuxGpibTransport`, `PyVisaTransport`, `MockTransport` |
| `src/ando_osa/parsing.py` | reply parsers (Table 9-4) |
| `src/ando_osa/simulator.py` | fake OSA for tests/GUI development |
| `src/ando_osa/gui.py` | touch-screen GUI |
| `tools/pi_install.sh` / `tools/pi_check.sh` | Pi setup / read-only status report |
| `tools/bringup.py` | hardware troubleshooting ladder (logs to `logs/bringup.log`) |

## Things the manual says that shape the design

- Commands can be chained with `,` but the receive buffer is **512 bytes** (p. 9-4); `send()` enforces it.
- Unknown codes are **silently ignored**; only status-byte bit 3 reveals an error. Setters therefore
  serial-poll after each set (`check_errors_after_set=True`).
- Codes sent while sweeping may be executed immediately or ignored (p. 9-50), so `single_sweep()` waits.
- Sweep completion uses SRQ: send `SRQ1`, read status byte once, send `SGL`, poll for bit 0 (p. 9-49/9-52).
- Talker data waits for sweep completion (p. 9-50). Defaults: string delimiter `,`, block delimiter CRLF+EOI.
- No `*IDN?` is listed for this model; `identify()` tries it and falls back to `CTRWL?`.

## Changes in v0.2

- linux-gpib transport: timeout code table fixed (0.3 s), `rsp()` bytes→int, timeout detection
  ("Connection timed out"), `close()` releases the descriptor, `local()` via `ibloc()`.
- Choice setters accept numeric values (`set_light_mode(0)` crashed before).
- `wait_sweep_done(cancel=...)` for a GUI STOP button.
- Code typos fixed (flagged unverified): `NSRL` (was `MSRL`), `WDMDIF` (set code was `WDMIF`).
- Added GUI, Pi install/check scripts, `bringup.py --no-instrument` and log file.

## Not verified / open items

- Everything on hardware (transport behaviour, EOI/terminator handling, timeouts).
- Unclear in the scan: `L3LN/L4LN` (scientific notation), `LBL'..'`, `DATE`/`TIME` set,
  `FPLD/DFBLD/LED` parameter setup (Table A1), linear-mode `REFL?` reply format, `NSRL`, `WDMDIF`.
- Floppy-disk, printer/plotter commands not implemented.
- Cross-check against `andrei-fedotov/ANDO_control` and the 6317B module is still to do.
- Connect/disconnect GPIB cables only with both instruments powered off (manual p. 9-3).
