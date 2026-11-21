# Hardware assembly

> Items marked **TODO** are specific to this build and still need to be filled in from the
> working unit (photos are welcome too).

## Parts

- Raspberry Pi 4 Model B
- GPIB4PI rev 2.x ([Lightside Instruments](https://lightside-instruments.com/product/gpib4pi/))
- Official Raspberry Pi 7" Touch Display (v1, 800×480, DSI)
- microSD card ≥ 16 GB, Pi 4 USB-C power supply (5.1 V 3 A)
- GPIB cable to the OSA
- Case: `case/` (print the template first, see `case/README.md`)

## Assembly order

1. **Display + Pi.** Mount the Pi on the back of the display and connect the DSI ribbon cable
   (display adapter board → the Pi's DISPLAY connector, contacts as in the display's leaflet).
2. **Display power.** **TODO:** describe how this unit powers the display. The GPIB4PI
   covers the GPIO header, so the usual 5 V / GND jumper wires to GPIO pins 2 and 6 need another
   route: the GPIB4PI's pass-through pins (if your board has them), or the display's own power input.
3. **GPIB4PI** on the 40-pin GPIO header. Line up pin 1 and push the board fully onto the header.
   **TODO:** any jumpers or solder bridges set on this board.
4. **Case:** see `case/README.md` (hardware list, print orientation, checks).

## GPIB4PI pin map

The `gpib_bitbang` driver needs to know how the board is wired to the GPIO pins:

| Board revision | Pin map | Installer option |
|---|---|---|
| rev 2.x | `elektronomikon` (driver default, REN on GPIO27) | (default) |
| rev 1.1 | `gpib4pi-1.1` (REN on GPIO0) | `--pin-map gpib4pi-1.1` |

To change it later: `sudo ./install.sh --only config --pin-map NAME`, then reboot.

The board uses most of GPIO 2–27, so leave I2C, SPI, serial (UART) and 1-Wire **disabled** in
`raspi-config` → *Interface Options*. They are off on a fresh Raspberry Pi OS, and the installer
warns if any of them are on. The display's touch controller doesn't use these pins: it is connected
through the DSI cable.

## Connecting the OSA

- Power **both** instruments off before plugging or unplugging the GPIB cable (AQ6315 manual p. 9-3).
- The Pi is the system controller at GPIB address 0. Set the OSA to another address
  (*SYSTEM → MY ADRS*, default 1 here) and give the installer the same number with `--address`. To
  change it later, either re-run `sudo ./install.sh --only config,app --address N` or edit
  `~/.config/ando_osa/launch.conf` and `/etc/gpib.conf`.
- The first time, run `python3 ando_osa/tools/bringup.py --address N`. It goes up the ladder
  (driver → interface → instrument → simple query → sweep) and stops at the first step that fails,
  with hints.
