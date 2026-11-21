#!/usr/bin/env python3
"""Hardware bring-up ladder for the AQ6315 on a Raspberry Pi + GPIB4PI (linux-gpib, gpib_bitbang).

Each step prints PASS/FAIL plus likely causes, and stops at the first failure so you fix things
in order.  Use --mock to dry-run the whole ladder against the simulator.

    python3 tools/bringup.py                    # interactive, linux-gpib, asks for options
    python3 tools/bringup.py --address 1 --yes  # non-interactive
    python3 tools/bringup.py --no-instrument    # steps 1-3 only (Pi + GPIB4PI, OSA not connected)
    python3 tools/bringup.py --mock

Output is also appended to logs/bringup.log so it can be reviewed remotely.
"""
import argparse
import datetime
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from ando_osa import LinuxGpibTransport, MockTransport, Osa, PyVisaTransport  # noqa: E402
from ando_osa.errors import OsaError  # noqa: E402

LOG = os.path.join(HERE, "..", "logs", "bringup.log")


def out(msg=""):
    print(msg)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def say(ok, msg, hints=()):
    out(("  PASS  " if ok else "  FAIL  ") + msg)
    if not ok:
        for h in hints:
            out("        - " + h)
    return ok


def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def ask(prompt, default, yes):
    if yes:
        return default
    v = input(f"{prompt} [{default}]: ").strip()
    return v or default


def step_system():
    out("\n[1] Kernel driver and device node")
    rc, txt = run("lsmod | grep -i gpib")
    if not say(bool(txt), "gpib kernel modules loaded" + (f" ({txt.splitlines()[0].split()[0]})" if txt else ""),
               ["Build/install the kernel module (see README 'Pi install'), then 'sudo modprobe gpib_bitbang'",
                "Check GPIB4PI wiring/pin setup against the vendor instructions"]):
        return False
    ok = os.path.exists("/dev/gpib0")
    return say(ok, "/dev/gpib0 exists", ["Run: sudo gpib_config", "Check /etc/gpib.conf (board_type gpib_bitbang)"])


def step_config():
    out("\n[2] /etc/gpib.conf and gpib_config")
    if not say(os.path.exists("/etc/gpib.conf"), "/etc/gpib.conf present", ["Create it using the GPIB4PI vendor example"]):
        return False
    rc, txt = run("systemctl is-active gpib-config.service")
    if txt.strip() == "active":
        return say(True, "board configured at boot (gpib-config.service active)")
    # not configured by the service: try ourselves (user in 'gpib' group usually suffices), then sudo -n
    cmd = "gpib_config --minor 0 --file /etc/gpib.conf"
    rc, txt = run(f"{cmd} 2>&1 || sudo -n {cmd} 2>&1")
    return say(rc == 0, "gpib_config ran without error" + ("" if rc == 0 else f": {txt[:300]}"),
               [f"Run it once by hand: sudo {cmd}",
                "Boot service status: systemctl status gpib-config.service",
                "Check dmesg for gpib_bitbang pin/IRQ errors"])


def step_open(tr):
    out("\n[3] Open the interface")
    try:
        tr.open()
        return say(True, "interface opened")
    except Exception as e:  # noqa: BLE001
        return say(False, f"open failed: {e}", ["python3-gpib not installed? (sudo apt install ./python3-gpib_*.deb)",
                                                 "Wrong board index / permissions (/dev/gpib0 group)"])


def step_ping(osa):
    out("\n[4] First contact: serial poll and a harmless query")
    try:
        stb = osa.status_byte()
        say(True, f"serial poll answered, status byte = {stb:#04x}")
    except Exception as e:  # noqa: BLE001
        return say(False, f"serial poll failed: {e}", [
            "Wrong GPIB address (check SYSTEM > MY ADRS on the OSA, 0..30)",
            "Cable loose / OSA off; connect cables only with power OFF",
            "OSA not in remote? (REMOTE lamp should light when addressed)"])
    try:
        osa.t.set_timeout(5)
        v = osa.get_center_wl()
        return say(True, f"CTRWL? -> {v} nm")
    except OsaError as e:
        return say(False, f"no reply to CTRWL?: {e}", [
            "Terminators: AQ6315 expects CRLF or EOI (manual 9.2.5)",
            "Check eos/eoi settings in /etc/gpib.conf", "Address mismatch"])


def step_setget(osa):
    out("\n[5] Set and read back")
    try:
        old = osa.get_center_wl()
        new = 1551.25 if abs(old - 1551.25) > 0.01 else 1550.0
        osa.set_center_wl(new)
        back = osa.get_center_wl()
        osa.set_center_wl(old)
        return say(abs(back - new) < 0.02, f"center wavelength {old} -> {new} -> read back {back} (restored {old})",
                   ["Set was ignored: is the OSA sweeping or in a mode that disables CTRWL? (manual 9.2.8(1))"])
    except OsaError as e:
        return say(False, f"set/get failed: {e}")


def step_sweep(osa):
    out("\n[6] Single sweep + trace readout")
    try:
        osa.set_center_span(float(osa.get_center_wl()), 20.0)
        t0 = time.time()
        osa.single_sweep(wait=True, timeout=180)
        say(True, f"sweep finished in {time.time() - t0:.1f} s (sweep-done status bit seen)")
        wl, lv = osa.get_trace("A")
        say(len(wl) == len(lv) and len(wl) > 10, f"trace A read: {len(wl)} points, "
            f"{wl[0]:.2f}-{wl[-1]:.2f} nm, max level {max(lv):.2f}")
        csv = os.path.join(HERE, "..", "logs", "bringup_trace.csv")
        with open(csv, "w") as f:
            f.write("wavelength_nm,level\n")
            f.writelines(f"{a},{b}\n" for a, b in zip(wl, lv))
        out(f"        saved {os.path.abspath(csv)} - compare against the trace on the OSA screen")
        return True
    except OsaError as e:
        return say(False, f"sweep/readout failed: {e}", [
            "Timeout during data read: raise timeout; long sweeps (high sensitivity) can take minutes",
            "Parse error: send 'HD0,SD0,BD0' and retry; capture raw reply with osa.query_raw('LDATA')"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["linux-gpib", "visa"], default="linux-gpib")
    ap.add_argument("--address", type=int)
    ap.add_argument("--board", type=int, default=0)
    ap.add_argument("--resource")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--yes", action="store_true", help="no prompts, use defaults")
    ap.add_argument("--skip-system", action="store_true")
    ap.add_argument("--no-instrument", action="store_true", help="stop after opening the interface")
    a = ap.parse_args()
    out(f"\n===== bringup {datetime.datetime.now().isoformat(timespec='seconds')} {' '.join(sys.argv[1:])}")

    if a.mock:
        tr = MockTransport()
    elif a.backend == "visa":
        res = a.resource or ask("VISA resource", "GPIB0::1::INSTR", a.yes)
        tr = PyVisaTransport(res, a.timeout)
    else:
        addr = a.address if a.address is not None else int(ask("OSA GPIB address (SYSTEM > MY ADRS)", "1", a.yes))
        tr = LinuxGpibTransport(addr, a.board, a.timeout)

    if not a.mock and a.backend == "linux-gpib" and not a.skip_system:
        if not (step_system() and step_config()):
            return 1
    if not step_open(tr):
        return 1
    if a.no_instrument:
        out("\nInterface OK. Stopping before instrument steps (--no-instrument).")
        tr.close()
        return 0
    osa = Osa(tr)
    try:
        if not step_ping(osa):
            return 1
        # configure talker format only after first contact worked
        osa.send("SD0", "BD0", "HD0", "SRQ1")
        osa.status_byte()
        if not step_setget(osa):
            return 1
        if not a.yes and input("\nRun a sweep now? (instrument must have light/fiber connected) [y/N]: ").lower() != "y":
            out("Stopped before sweep.")
            return 0
        return 0 if step_sweep(osa) else 1
    finally:
        try:
            osa.close()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    sys.exit(main())
