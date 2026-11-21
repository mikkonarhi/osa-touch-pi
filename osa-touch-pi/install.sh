#!/bin/bash
# ando_osa installer: fresh Raspberry Pi OS (64-bit) + GPIB4PI board  ->  working OSA touch GUI.
#
#   sudo ./install.sh                          # everything; OSA at GPIB address 1
#   sudo ./install.sh --address 5 --autostart  # OSA at address 5, GUI starts when the desktop starts
#   sudo ./install.sh --only config,app        # re-run some stages only
#   sudo ./install.sh --help
#
# Stages, in this order. Each one can be re-run; work that is already done is detected and skipped.
#   preflight    checks: Pi model, OS, 64-bit, kernel headers, GPIO pins claimed by other interfaces
#   deps         apt: build tools + kernel headers (the metapackage, so headers follow kernel upgrades)
#   gpib-user    linux-gpib user space from source: libgpib, gpib_config, Python 'Gpib' module
#   gpib-kernel  linux-gpib kernel modules (gpib_bitbang) from source; skipped if the kernel has them
#   config       /etc/gpib.conf, pin map, module autoload, gpib group, udev rule, boot services
#                (incl. automatic rebuild of the module after a kernel upgrade)
#   python       apt: numpy, pyqtgraph, PyQt6, Qt Wayland plugin, pytest
#   app          menu + desktop launcher (+ optional autostart), ~/osa_traces, launcher settings
#   check        loads the driver now and runs the self-tests (no instrument needed)
#
# Everything is logged to logs/install.log.
set -Eeuo pipefail

REPO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OSA_DIR=$REPO_DIR/ando_osa
ALL_STAGES="preflight deps gpib-user gpib-kernel config python app check"

# ------------------------------------------------------------------ defaults (all overridable)
ADDRESS=${OSA_ADDRESS:-1}                  # OSA GPIB address (OSA front panel: SYSTEM > MY ADRS)
PIN_MAP=${PIN_MAP:-elektronomikon}         # GPIB4PI rev 2.x; old rev 1.1 board: gpib4pi-1.1
GPIB_VERSION=${GPIB_VERSION:-4.3.7}
GPIB_SOURCE=${GPIB_SOURCE:-tarball}        # tarball | git
KERNEL_SRC=${KERNEL_SRC:-}                 # use an already unpacked linux-gpib-kernel tree
USER_SRC=${USER_SRC:-}                     # use an already unpacked linux-gpib-user tree
AUTOSTART=0
FORCE_GPIB=0
STAGES=$ALL_STAGES
TARGET_USER=${SUDO_USER:-}

SRC_ROOT=/usr/local/src/ando-osa-linux-gpib
GPIB_TARBALL_URL="https://sourceforge.net/projects/linux-gpib/files/linux-gpib%20for%203.x.x%20and%202.6.x%20kernels/${GPIB_VERSION}/linux-gpib-${GPIB_VERSION}.tar.gz/download"
GPIB_GIT_URL=https://git.code.sf.net/p/linux-gpib/git

usage() {
    cat <<EOF
Usage: sudo ./install.sh [options]

  --address N        OSA GPIB address (default $ADDRESS)
  --pin-map NAME     gpib_bitbang pin map (default $PIN_MAP; old GPIB4PI rev 1.1: gpib4pi-1.1)
  --autostart        start the GUI full screen when the desktop starts
  --only a,b,...     run only these stages   ($ALL_STAGES)
  --skip a,b,...     run all stages except these
  --force-gpib       rebuild linux-gpib even if it is already installed
  --gpib-version V   linux-gpib release to build (default $GPIB_VERSION)
  --gpib-git         build linux-gpib from its git repository instead of the release tarball
  --kernel-src DIR   use this unpacked linux-gpib-kernel source tree (no download)
  --user-src DIR     use this unpacked linux-gpib-user source tree (no download)
  --user NAME        install the launcher for this user (default: the user who ran sudo)
  -h, --help         this help
EOF
}

while [ $# -gt 0 ]; do
    case $1 in
        --address) ADDRESS=$2; shift ;;
        --pin-map) PIN_MAP=$2; shift ;;
        --autostart) AUTOSTART=1 ;;
        --only) STAGES=${2//,/ }; shift ;;
        --skip) skip=" ${2//,/ } "; STAGES=""
                for s in $ALL_STAGES; do [[ $skip == *" $s "* ]] || STAGES+="$s "; done; shift ;;
        --force-gpib) FORCE_GPIB=1 ;;
        --gpib-version) GPIB_VERSION=$2; shift
                GPIB_TARBALL_URL="https://sourceforge.net/projects/linux-gpib/files/linux-gpib%20for%203.x.x%20and%202.6.x%20kernels/${GPIB_VERSION}/linux-gpib-${GPIB_VERSION}.tar.gz/download" ;;
        --gpib-git) GPIB_SOURCE=git ;;
        --kernel-src) KERNEL_SRC=$(realpath "$2"); shift ;;
        --user-src) USER_SRC=$(realpath "$2"); shift ;;
        --user) TARGET_USER=$2; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option: $1"; usage; exit 1 ;;
    esac
    shift
done

# ------------------------------------------------------------------ helpers
[ "$(id -u)" = 0 ] || { echo "Run with sudo:  sudo ./install.sh"; exit 1; }
if [ -z "$TARGET_USER" ] || [ "$TARGET_USER" = root ]; then
    echo "Run this as your normal user through sudo (sudo ./install.sh), or pass --user NAME."
    exit 1
fi
HOME_DIR=$(getent passwd "$TARGET_USER" | cut -d: -f6)
[ -d "$HOME_DIR" ] || { echo "user $TARGET_USER has no home directory"; exit 1; }
[[ $ADDRESS =~ ^[0-9]+$ ]] && [ "$ADDRESS" -ge 1 ] && [ "$ADDRESS" -le 30 ] \
    || { echo "--address must be 1..30"; exit 1; }
KVER=$(uname -r)

mkdir -p "$REPO_DIR/logs"
chown "$TARGET_USER": "$REPO_DIR/logs"
LOG=$REPO_DIR/logs/install.log
exec > >(tee -a "$LOG") 2>&1
echo; echo "===== install.sh $(date '+%Y-%m-%d %H:%M:%S')  stages: $STAGES"

CURRENT_STAGE=""
WARNINGS=()
log()  { echo -e "\n\033[1;36m>>> $*\033[0m"; }
info() { echo "    $*"; }
warn() { echo -e "    \033[1;33mWARNING:\033[0m $*"; WARNINGS+=("$*"); }
die()  { echo -e "\n\033[1;31mERROR in stage '$CURRENT_STAGE':\033[0m $*\n    log: $LOG"; exit 1; }
trap 'echo -e "\n\033[1;31mFAILED\033[0m in stage \"$CURRENT_STAGE\" (line $LINENO): $BASH_COMMAND\n    log: $LOG\n    see docs/TROUBLESHOOTING.md"' ERR
as_user() { runuser -u "$TARGET_USER" -- "$@"; }

boot_config() {      # Bookworm/Trixie keep it in /boot/firmware, older releases in /boot
    for f in /boot/firmware/config.txt /boot/config.txt; do [ -f "$f" ] && { echo "$f"; return 0; }; done
    return 0
}

python_has_gpib() { (cd / && python3 -c 'import Gpib, gpib') >/dev/null 2>&1; }

have_userspace() {
    command -v gpib_config >/dev/null && ldconfig -p | grep -q 'libgpib\.so' && python_has_gpib
}

module_path() { modinfo -n -k "$KVER" gpib_bitbang 2>/dev/null; }

# Download / unpack linux-gpib once into $SRC_ROOT and apply local patches.
fetch_sources() {
    if [ -n "$KERNEL_SRC" ] && [ -n "$USER_SRC" ]; then return; fi
    mkdir -p "$SRC_ROOT"
    if [ "$GPIB_SOURCE" = git ]; then
        local d=$SRC_ROOT/git
        if [ -d "$d/.git" ]; then git -C "$d" pull --ff-only; else git clone --depth 1 "$GPIB_GIT_URL" "$d"; fi
        : "${KERNEL_SRC:=$d/linux-gpib-kernel}"
        : "${USER_SRC:=$d/linux-gpib-user}"
    else
        local d=$SRC_ROOT/linux-gpib-$GPIB_VERSION tgz=$SRC_ROOT/linux-gpib-$GPIB_VERSION.tar.gz
        if [ ! -d "$d/linux-gpib-kernel-$GPIB_VERSION" ] || [ ! -d "$d/linux-gpib-user-$GPIB_VERSION" ]; then
            if [ -f "$REPO_DIR/installer/linux-gpib-$GPIB_VERSION.tar.gz" ]; then
                info "using installer/linux-gpib-$GPIB_VERSION.tar.gz (offline copy)"
                cp "$REPO_DIR/installer/linux-gpib-$GPIB_VERSION.tar.gz" "$tgz"
            elif [ ! -s "$tgz" ]; then
                info "downloading linux-gpib $GPIB_VERSION from SourceForge"
                curl -fL --retry 3 --connect-timeout 20 -o "$tgz.part" "$GPIB_TARBALL_URL" \
                    || die "download failed. Check the network, or put linux-gpib-$GPIB_VERSION.tar.gz in installer/"
                mv "$tgz.part" "$tgz"
            fi
            tar xzf "$tgz" -C "$SRC_ROOT"
            tar xzf "$d/linux-gpib-kernel-$GPIB_VERSION.tar.gz" -C "$d"
            tar xzf "$d/linux-gpib-user-$GPIB_VERSION.tar.gz" -C "$d"
        fi
        : "${KERNEL_SRC:=$d/linux-gpib-kernel-$GPIB_VERSION}"
        : "${USER_SRC:=$d/linux-gpib-user-$GPIB_VERSION}"
    fi
    apply_patches kernel "$KERNEL_SRC"
    apply_patches user "$USER_SRC"
}

# installer/patches/{kernel,user}/*.patch, -p1 relative to the source tree root. Applied once.
apply_patches() {
    local kind=$1 dir=$2 p
    for p in "$REPO_DIR"/installer/patches/"$kind"/*.patch; do
        [ -f "$p" ] || continue
        local mark
        mark="$dir/.ando-osa-applied-$(basename "$p")"
        [ -f "$mark" ] && continue
        info "applying $kind patch $(basename "$p")"
        patch -d "$dir" -p1 -N --batch < "$p" || die "patch $(basename "$p") does not apply to $dir"
        touch "$mark"
    done
}

# ------------------------------------------------------------------ stages
stage_preflight() {
    local model os arch cfg
    model=$({ tr -d '\0' < /proc/device-tree/model; } 2>/dev/null || echo unknown)
    os=$(. /etc/os-release && echo "$PRETTY_NAME")
    arch=$(dpkg --print-architecture)
    info "board:  $model"
    info "os:     $os ($arch), kernel $KVER"
    info "user:   $TARGET_USER  ($HOME_DIR)"
    info "repo:   $REPO_DIR"
    info "osa:    GPIB address $ADDRESS, pin map $PIN_MAP"
    [[ $model == *"Raspberry Pi"* ]] || warn "this does not look like a Raspberry Pi"
    [[ $model == *"Raspberry Pi 4"* || $model == *"Raspberry Pi 400"* ]] \
        || warn "tested on a Pi 4B; the GPIB4PI bit-bang driver may behave differently on other models"
    [ "$arch" = arm64 ] || warn "OS architecture is $arch: tested on 64-bit (arm64) Raspberry Pi OS only"
    case $REPO_DIR in /tmp/*|/media/*|/run/*) warn "the repo is in $REPO_DIR; the launcher runs the GUI from here, so keep it somewhere permanent (e.g. ~/Documents)";; esac
    [ -d "$OSA_DIR/src/ando_osa" ] || die "$OSA_DIR/src/ando_osa not found: is this the complete repo?"

    # GPIB4PI drives GPIO 2..27 directly. Interfaces on those pins stop the driver from claiming them.
    cfg=$(boot_config)
    if [ -n "$cfg" ]; then
        local hits
        hits=$(grep -nE '^[[:space:]]*(dtparam=(i2c_arm|i2c|spi)=on|enable_uart=1|dtoverlay=(w1-gpio|spi|i2c|uart|pwm))' "$cfg" || true)
        if [ -n "$hits" ]; then
            warn "$cfg enables interfaces on GPIO pins used by the GPIB4PI board:"
            echo "$hits" | sed 's/^/        /'
            info "    turn them off (raspi-config > Interface Options, or comment the lines) and reboot"
        fi
    fi

    if dpkg -s libgpib0 >/dev/null 2>&1; then
        info "linux-gpib is already installed from .deb packages (user space build will be skipped)"
    fi
    local avail
    avail=$(df -Pm /usr/local | awk 'NR==2{print $4}')
    [ "${avail:-0}" -gt 800 ] || warn "only ${avail} MB free in /usr/local; the build needs ~500 MB"
}

stage_deps() {
    apt-get update
    apt-get install -y build-essential autoconf automake libtool bison flex pkg-config \
        python3-dev python3-setuptools python3-pip curl ca-certificates git patch kmod
    # kernel headers: exact match for the running kernel + the flavour metapackage that keeps
    # following kernel upgrades (Pi OS kernels are named like 6.12.47+rpt-rpi-v8 -> flavour v8)
    local flavour=${KVER##*-rpi-}
    if [ "$flavour" != "$KVER" ]; then
        apt-get install -y "linux-headers-rpi-$flavour" || warn "linux-headers-rpi-$flavour not available"
    fi
    if [ ! -d "/lib/modules/$KVER/build" ]; then
        apt-get install -y "linux-headers-$KVER" || true
    fi
    if [ ! -d "/lib/modules/$KVER/build" ]; then
        die "no kernel headers for the running kernel $KVER.
    Usually the kernel was upgraded but the Pi was not rebooted yet: run
        sudo apt full-upgrade -y && sudo reboot
    and then run the installer again."
    fi
    info "kernel headers: /lib/modules/$KVER/build"
}

stage_gpib_user() {
    if [ "$FORCE_GPIB" = 0 ] && have_userspace; then
        info "linux-gpib user space already works (gpib_config, libgpib, Python Gpib): skipping"
        return
    fi
    fetch_sources
    log "building linux-gpib user space in $USER_SRC"
    cd "$USER_SRC"
    if [ ! -x configure ]; then ./bootstrap; fi
    # sysconfdir=/etc: the library then looks for /etc/gpib.conf (not /usr/local/etc/gpib.conf).
    # The Python binding is installed separately below (its make-install step is fragile with
    # current setuptools and may land outside Debian's module path).
    ./configure --prefix=/usr/local --sysconfdir=/etc --disable-python-binding \
        --disable-guile-binding --disable-tcl-binding --disable-php-binding --disable-perl-binding \
        --disable-documentation
    make -j"$(nproc)"
    make install
    ldconfig

    if ! python_has_gpib; then
        log "installing the linux-gpib Python binding (Gpib module)"
        cd "$USER_SRC/language/python"
        pip3 install --break-system-packages --root-user-action=ignore --no-build-isolation . \
            || pip3 install --root-user-action=ignore --no-build-isolation .
    fi
    python_has_gpib || die "Python cannot import the linux-gpib binding (import Gpib)"
    command -v gpib_config >/dev/null || die "gpib_config was not installed"
    info "user space OK: $(command -v gpib_config), Python Gpib module importable"
}

stage_gpib_kernel() {
    local p
    if [ "$FORCE_GPIB" = 0 ] && p=$(module_path); then
        info "gpib_bitbang is already available for $KVER: $p"
        [[ $p == */kernel/drivers/* ]] && info "(this is the driver shipped with the kernel; no build needed)"
        remember_kernel_src
        return
    fi
    [ -d "/lib/modules/$KVER/build" ] || die "kernel headers for $KVER missing: run the deps stage (or reboot after a kernel upgrade)"
    fetch_sources
    log "building linux-gpib kernel modules for $KVER (takes a few minutes on a Pi 4)"
    make -C "$KERNEL_SRC" clean >/dev/null 2>&1 || true
    make -C "$KERNEL_SRC" -j"$(nproc)" LINUX_SRCDIR="/lib/modules/$KVER/build"
    make -C "$KERNEL_SRC" install LINUX_SRCDIR="/lib/modules/$KVER/build"
    depmod -a "$KVER"
    p=$(module_path) || die "gpib_bitbang.ko was built but modinfo cannot find it for $KVER"
    info "installed: $p"
    remember_kernel_src
}

# Where the kernel module source lives, for the automatic rebuild after kernel upgrades.
remember_kernel_src() {
    local src=$KERNEL_SRC
    if [ -z "$src" ]; then
        for c in "$SRC_ROOT/linux-gpib-$GPIB_VERSION/linux-gpib-kernel-$GPIB_VERSION" \
                 "$SRC_ROOT/git/linux-gpib-kernel" "$HOME_DIR/gpib-build/gpib/kernel"; do
            [ -f "$c/Makefile" ] && { src=$c; break; }
        done
    fi
    if [ -n "$src" ]; then
        echo "GPIB_KERNEL_SRC=\"$src\"" > /etc/default/ando-osa-gpib
        info "module source for automatic rebuilds: $src"
    elif [[ $(module_path) != */kernel/drivers/* ]]; then
        warn "no linux-gpib kernel source found: the module will not be rebuilt automatically after a kernel upgrade (re-run: sudo ./install.sh --only gpib-kernel --force-gpib)"
    fi
}

stage_config() {
    log "writing /etc/gpib.conf (OSA address $ADDRESS) and module options (pin map $PIN_MAP)"
    if [ -f /etc/gpib.conf ] && ! grep -q 'ando_osa' /etc/gpib.conf; then
        cp /etc/gpib.conf "/etc/gpib.conf.bak.$(date +%Y%m%d%H%M%S)"
        info "existing /etc/gpib.conf backed up"
    fi
    sed "s/@OSA_ADDRESS@/$ADDRESS/" "$REPO_DIR/installer/gpib.conf.in" > /etc/gpib.conf
    # some linux-gpib builds look in /usr/etc (built with the default sysconfdir): link both
    mkdir -p /usr/etc
    ln -sf /etc/gpib.conf /usr/etc/gpib.conf

    echo "options gpib_bitbang pin_map=$PIN_MAP" > /etc/modprobe.d/gpib_bitbang.conf
    echo "gpib_bitbang" > /etc/modules-load.d/gpib.conf

    getent group gpib >/dev/null || groupadd gpib
    usermod -aG gpib "$TARGET_USER"
    getent group gpio >/dev/null && usermod -aG gpio "$TARGET_USER"
    install -m 644 "$REPO_DIR/installer/98-gpib-ando.rules" /etc/udev/rules.d/98-gpib-ando.rules
    udevadm control --reload-rules || true

    install -m 755 "$REPO_DIR/installer/ando-osa-gpib-rebuild" /usr/local/sbin/ando-osa-gpib-rebuild
    install -m 644 "$REPO_DIR/installer/systemd/ando-osa-gpib-rebuild.service" /etc/systemd/system/
    install -m 644 "$REPO_DIR/installer/systemd/gpib-config.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable ando-osa-gpib-rebuild.service gpib-config.service
    info "boot services enabled: ando-osa-gpib-rebuild (only acts after a kernel upgrade), gpib-config"
}

stage_python() {
    apt-get install -y python3-numpy python3-pyqtgraph python3-pyqt6 python3-pytest
    # native Wayland for Qt: needed for multi-touch (pinch zoom) on the Pi desktop
    apt-get install -y qt6-wayland || warn "qt6-wayland not available: pinch zoom will not work (single touch does)"
}

stage_app() {
    local conf_dir=$HOME_DIR/.config/ando_osa apps=$HOME_DIR/.local/share/applications desktop
    chmod +x "$OSA_DIR"/tools/*.sh
    as_user mkdir -p "$conf_dir" "$apps" "$HOME_DIR/osa_traces"

    if [ ! -f "$conf_dir/launch.conf" ] || ! grep -q '^OSA_ADDRESS=' "$conf_dir/launch.conf"; then
        as_user tee "$conf_dir/launch.conf" >/dev/null <<EOF
# Settings for the OSA launcher (tools/launch_osa.sh). Written by install.sh; edit freely.
OSA_ADDRESS=$ADDRESS          # GPIB address of the OSA
GUI_ARGS="--fullscreen"       # e.g. "--fullscreen", or "--size 1024x600" for another screen
EOF
    else
        as_user sed -i "s/^OSA_ADDRESS=[0-9]*/OSA_ADDRESS=$ADDRESS/" "$conf_dir/launch.conf"
    fi
    info "launcher settings: $conf_dir/launch.conf"

    desktop=$(sed -e "s|@OSA_DIR@|$OSA_DIR|g" "$REPO_DIR/installer/ando-osa.desktop.in")
    echo "$desktop" | as_user tee "$apps/ando-osa.desktop" >/dev/null
    info "menu entry: $apps/ando-osa.desktop"
    if [ -d "$HOME_DIR/Desktop" ]; then
        echo "$desktop" | as_user tee "$HOME_DIR/Desktop/ando-osa.desktop" >/dev/null
        chmod +x "$HOME_DIR/Desktop/ando-osa.desktop"
        info "desktop icon: $HOME_DIR/Desktop/ando-osa.desktop"
    fi
    if [ "$AUTOSTART" = 1 ]; then
        as_user mkdir -p "$HOME_DIR/.config/autostart"
        echo "$desktop" | as_user tee "$HOME_DIR/.config/autostart/ando-osa.desktop" >/dev/null
        info "autostart: GUI starts full screen when the desktop starts"
    fi
    chown -R "$TARGET_USER": "$REPO_DIR"
}

stage_check() {
    log "loading the driver now (a reboot does the same automatically)"
    if modprobe gpib_bitbang 2>&1; then
        systemctl restart gpib-config.service && info "gpib-config.service: board configured" \
            || warn "gpib-config.service failed: systemctl status gpib-config.service"
        [ -e /dev/gpib0 ] && info "/dev/gpib0 present" || warn "/dev/gpib0 missing"
    else
        warn "modprobe gpib_bitbang failed (dmesg | grep -i gpib)"
    fi
    log "self-tests (simulator, no instrument)"
    (cd "$OSA_DIR" && as_user python3 -m pytest -q 2>&1 | tail -3) || warn "self-tests failed"
    log "status report (logs/pi_check.log)"
    as_user bash "$OSA_DIR/tools/pi_check.sh" >/dev/null 2>&1 || true
    info "written to $OSA_DIR/logs/pi_check.log"
}

# ------------------------------------------------------------------ run
for s in $STAGES; do
    case $s in preflight|deps|gpib-user|gpib-kernel|config|python|app|check) ;;
        *) echo "unknown stage: $s (stages: $ALL_STAGES)"; exit 1 ;; esac
done
for s in $STAGES; do
    CURRENT_STAGE=$s
    log "[$s]"
    "stage_${s//-/_}"
done
CURRENT_STAGE="done"

echo
if [ ${#WARNINGS[@]} -gt 0 ]; then
    echo -e "\033[1;33mFinished with ${#WARNINGS[@]} warning(s):\033[0m"
    for w in "${WARNINGS[@]}"; do echo "  - $w"; done
else
    echo -e "\033[1;32mFinished without warnings.\033[0m"
fi
cat <<EOF

Next steps
  1. sudo reboot                     (group membership and boot services take effect)
  2. bash ando_osa/tools/pi_check.sh                         status report
     python3 ando_osa/tools/bringup.py --no-instrument --yes  driver + GPIB4PI, OSA not needed
     python3 ando_osa/tools/bringup.py --address $ADDRESS            with the OSA connected
  3. Start "ANDO OSA" from the menu or the desktop icon.
     Simulator without hardware: bash ando_osa/tools/run_gui.sh --mock

Log of this run: $LOG
EOF
