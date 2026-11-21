# OSA touch panel: Raspberry Pi + GPIB4PI for ANDO / Yokogawa optical spectrum analyzers

A Raspberry Pi 4B with the official 7" touch screen and a GPIB4PI board, used as a touch-screen front
panel for ANDO AQ6315A/B and AQ6317B optical spectrum analyzers over GPIB. It can run sweeps, set
parameters, use markers and analysis functions, zoom by touch, and save traces as CSV to the Pi
or a USB stick.

- `ando_osa/`: Python library (all ~200 GPIB program codes from manual chapter 9), touch GUI,
  simulator, tests, bring-up tools
- `install.sh`: one installer that takes a fresh Raspberry Pi OS to a working GUI, building the GPIB driver along the way
- `case/`: 3D-printable case (OpenSCAD) for display + Pi + GPIB4PI
- `docs/`: hardware assembly, troubleshooting

**Status:** in use with an AQ6317B. The AQ6315A/B command set is implemented from the manual
but has not been tested on a real instrument.

---

## What you need

| Part | Notes |
|---|---|
| Raspberry Pi 4 Model B | 2 GB is enough |
| GPIB4PI board, rev 2.x | [Lightside Instruments](https://lightside-instruments.com/product/gpib4pi/). Rev 1.1 also works with `--pin-map gpib4pi-1.1` |
| Official Raspberry Pi 7" Touch Display (v1, 800×480) | other screens work: change `GUI_ARGS` in `~/.config/ando_osa/launch.conf` |
| microSD card, 16 GB or larger | |
| Pi 4 power supply (USB-C, 5.1 V 3 A) | |
| GPIB cable | |
| Optional: USB stick, USB keyboard | for saving traces / maintenance |

Assembly details are in [docs/HARDWARE.md](docs/HARDWARE.md).

## Install

### 1. Flash Raspberry Pi OS

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to flash **Raspberry Pi OS (64-bit)**
(the desktop version, not Lite). In the Imager's settings, choose a user name and password, and
set up Wi-Fi/SSH if you want to work on the Pi remotely.

### 2. First boot: update and reboot

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

The reboot matters: the GPIB driver is built against the *running* kernel, so the kernel has to be
the new one before the installer runs.

### 3. Get the software and run the installer

```bash
sudo apt install -y git
cd ~/Documents
git clone https://github.com/mikkonarhi/osa-touch-pi.git osa-touch-pi
cd osa-touch-pi
sudo ./install.sh                  # OSA at GPIB address 1
```

The installer takes about 10 minutes on a Pi 4, most of it compiling linux-gpib. Common options:

```bash
sudo ./install.sh --address 5            # the OSA's GPIB address (OSA: SYSTEM > MY ADRS)
sudo ./install.sh --autostart            # start the GUI full screen when the Pi boots
sudo ./install.sh --pin-map gpib4pi-1.1  # only for the old GPIB4PI rev 1.1 board
sudo ./install.sh --help                 # all options
```

### 4. Reboot and check

```bash
sudo reboot
cd ~/Documents/osa-touch-pi
bash ando_osa/tools/pi_check.sh                           # status report -> ando_osa/logs/pi_check.log
python3 ando_osa/tools/bringup.py --no-instrument --yes   # driver + GPIB4PI, OSA not needed
```

### 5. Connect the OSA

Power **both** the Pi and the OSA off before you plug or unplug the GPIB cable (manual p. 9-3). Then:

```bash
python3 ando_osa/tools/bringup.py --address 1             # step-by-step connection test
```

Start **ANDO OSA** from the menu or the desktop icon. To try the GUI without hardware, run
`bash ando_osa/tools/run_gui.sh --mock`.

## What the installer does

Each stage can be run on its own (`--only`, `--skip`). Work that is already done is detected and
skipped, so the installer is safe to run again.

| Stage | What it does |
|---|---|
| `preflight` | Checks the board, OS, architecture and free disk space, and warns if I2C/SPI/UART are enabled on GPIO pins the GPIB4PI uses |
| `deps` | Installs build tools and kernel headers through apt (the headers metapackage, so headers follow kernel upgrades) |
| `gpib-user` | Downloads [linux-gpib](https://linux-gpib.sourceforge.io/) 4.3.7 and builds and installs `libgpib`, `gpib_config` and the Python `Gpib` module |
| `gpib-kernel` | Builds and installs the `gpib_bitbang` kernel module. Skipped if the kernel already ships the driver (Linux ≥ 6.13 has it in-tree when enabled) |
| `config` | Writes `/etc/gpib.conf`, the pin map, module autoload, the `gpib` group and udev rule. Sets up a boot service that configures the board, and one that rebuilds the module after a kernel upgrade |
| `python` | Installs through apt: numpy, pyqtgraph, PyQt6, the Qt Wayland plugin (needed for pinch zoom) and pytest |
| `app` | Adds the menu entry, desktop icon and optional autostart, plus `~/osa_traces` and `~/.config/ando_osa/launch.conf` |
| `check` | Loads the driver, runs the self-tests and writes the status report |

Everything goes to `logs/install.log`. An existing `/etc/gpib.conf` is backed up before it is replaced.

**Kernel updates:** `apt full-upgrade` can install a new kernel, which has no GPIB module yet. On the
next boot, `ando-osa-gpib-rebuild.service` notices this and rebuilds the module (a few minutes, once),
and the GUI then works as before.

**Offline install:** put `linux-gpib-4.3.7.tar.gz` in `installer/` and the installer uses it instead of downloading.
Apt packages still need a network connection.

## Updating

```bash
cd ~/Documents/osa-touch-pi
git pull
sudo ./install.sh --only python,app    # only needed if dependencies or the launcher changed
```

## Uninstall

```bash
sudo ./uninstall.sh                # services, config, launchers
sudo ./uninstall.sh --purge-gpib   # also remove the linux-gpib build
```

## Repository layout

| Path | Contents |
|---|---|
| `install.sh`, `uninstall.sh` | Pi setup |
| `installer/` | config templates, systemd units, module rebuild script, optional linux-gpib patches |
| `ando_osa/src/ando_osa/` | library (`osa.py`, `commands.py`, `transport.py`, ...) and `gui.py` |
| `ando_osa/tools/` | `run_gui.sh`, `launch_osa.sh`, `bringup.py`, `pi_check.sh` |
| `ando_osa/docs/COMMANDS.md` | every GPIB command, its Python method, range and manual page |
| `ando_osa/README.md` | library and GUI details |
| `case/` | OpenSCAD case and print notes |
| `docs/HARDWARE.md`, `docs/TROUBLESHOOTING.md` | assembly, fixing problems |

## Licenses

linux-gpib (GPL-2.0) is downloaded from SourceForge during installation and is not included here.
