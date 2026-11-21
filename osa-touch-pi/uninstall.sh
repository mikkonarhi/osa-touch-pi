#!/bin/bash
# Undo what install.sh set up. linux-gpib itself and the apt packages stay unless --purge-gpib.
#   sudo ./uninstall.sh                 # services, config, udev rule, launchers
#   sudo ./uninstall.sh --purge-gpib    # also remove the linux-gpib build installed by install.sh
set -uo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
USER_NAME=${SUDO_USER:-}
HOME_DIR=$( [ -n "$USER_NAME" ] && getent passwd "$USER_NAME" | cut -d: -f6 )
PURGE=0; [ "${1:-}" = --purge-gpib ] && PURGE=1

systemctl disable --now gpib-config.service ando-osa-gpib-rebuild.service 2>/dev/null
rm -f /etc/systemd/system/gpib-config.service /etc/systemd/system/ando-osa-gpib-rebuild.service \
      /usr/local/sbin/ando-osa-gpib-rebuild /etc/default/ando-osa-gpib \
      /etc/modprobe.d/gpib_bitbang.conf /etc/modules-load.d/gpib.conf \
      /etc/udev/rules.d/98-gpib-ando.rules
systemctl daemon-reload
if grep -q 'ando_osa' /etc/gpib.conf 2>/dev/null; then
    mv /etc/gpib.conf "/etc/gpib.conf.removed.$(date +%Y%m%d%H%M%S)"
    [ -L /usr/etc/gpib.conf ] && rm -f /usr/etc/gpib.conf
    echo "/etc/gpib.conf moved aside (earlier backups: /etc/gpib.conf.bak.*)"
fi
if [ -n "$HOME_DIR" ]; then
    rm -f "$HOME_DIR/.local/share/applications/ando-osa.desktop" "$HOME_DIR/Desktop/ando-osa.desktop" \
          "$HOME_DIR/.config/autostart/ando-osa.desktop"
    echo "launchers removed; kept ~/.config/ando_osa and ~/osa_traces"
fi
if [ "$PURGE" = 1 ]; then
    modprobe -r gpib_bitbang 2>/dev/null
    for d in /usr/local/src/ando-osa-linux-gpib/*/linux-gpib-user* /usr/local/src/ando-osa-linux-gpib/git/linux-gpib-user; do
        [ -f "$d/Makefile" ] && make -C "$d" uninstall >/dev/null && echo "removed linux-gpib user space ($d)"
    done
    pip3 uninstall -y --break-system-packages gpib 2>/dev/null
    # out-of-tree modules only; drivers shipped with the kernel (kernel/drivers/...) are left alone
    find /lib/modules -name 'gpib*.ko*' -not -path '*/kernel/drivers/*' -print -delete
    depmod -a
    rm -rf /usr/local/src/ando-osa-linux-gpib
    ldconfig
fi
echo "done (reboot to unload everything)"
