# Troubleshooting

Start with these two. Both write logs you can send to someone else:

```bash
bash ando_osa/tools/pi_check.sh                          # -> ando_osa/logs/pi_check.log
python3 ando_osa/tools/bringup.py --no-instrument --yes  # -> ando_osa/logs/bringup.log
```

Other logs: `logs/install.log` (installer), `ando_osa/logs/gui.log` (GUI + all GPIB traffic),
`ando_osa/logs/launcher.log` (start-up errors of the menu launcher).

## Installer

**"no kernel headers for the running kernel"**
The kernel was upgraded but the Pi was not rebooted. Run `sudo reboot`, then run the installer again.

**linux-gpib download fails**
SourceForge is sometimes slow or down. Run the installer again later, or download
`linux-gpib-4.3.7.tar.gz` on another computer and put it in `installer/`.

**kernel module build fails** (`gpib-kernel` stage, compiler errors)
A newer Raspberry Pi kernel can be ahead of the linux-gpib release. In order of preference:
1. `sudo ./install.sh --only gpib-kernel --gpib-git` builds the latest linux-gpib from git.
2. Put a fix in `installer/patches/kernel/` (see the README there) and re-run with `--force-gpib`.
3. Check whether the kernel has the driver built in: `modinfo gpib_bitbang`. If it does, the
   installer uses it and skips the build.

**Python cannot import Gpib**
`sudo ./install.sh --only gpib-user --force-gpib`. Check with `python3 -c "import Gpib"`. Run it
from your home folder, not from inside the linux-gpib source tree.

## Driver / interface

**`/dev/gpib0` missing after a reboot**
- `lsmod | grep gpib`: no output means the module didn't load. Try `sudo modprobe gpib_bitbang`, then
  `sudo dmesg | grep -i gpib`. "Failed to get GPIO" or "busy" means another interface (I2C, SPI,
  UART, 1-Wire) owns those pins: disable it in `raspi-config` and reboot.
- After a kernel upgrade the first boot rebuilds the module. `systemctl status ando-osa-gpib-rebuild`
  shows how that went.

**`gpib-config.service` failed**
`systemctl status gpib-config.service`. The usual cause is a syntax error in `/etc/gpib.conf`
(option names use hyphens: `set-reos`, `set-eot`). Rewrite it with `sudo ./install.sh --only config`.

**Permission denied on `/dev/gpib0`**
Your user must be in the `gpib` group (`id` shows the groups). The installer adds it, but it only
takes effect after you log out and back in, or reboot.

## Instrument

**Timeouts / no answer from the OSA**
- The GPIB address on the OSA (*SYSTEM → MY ADRS*) must match `--address` / `launch.conf`.
- Check the cable. Plug or unplug it only with both instruments off.
- Wrong pin map for the board revision: rev 2.x uses `elektronomikon`, rev 1.1 uses `gpib4pi-1.1`.
- `python3 ando_osa/tools/bringup.py --address N` shows the step that fails.

## GUI

**Menu icon does nothing**
Look in `ando_osa/logs/launcher.log`. Running `bash ando_osa/tools/launch_osa.sh` from a terminal
shows the same output.

**Touch works but pinch zoom doesn't**
Qt is running through X11. Install the Wayland plugin with `sudo apt install qt6-wayland` and start
the GUI again (`run_gui.sh` picks Wayland automatically).

**GUI doesn't start at boot with `--autostart`**
Check that `~/.config/autostart/ando-osa.desktop` exists. Desktop auto-login must be on
(`raspi-config` → *System Options* → *Boot / Auto Login* → *Desktop Autologin*).
