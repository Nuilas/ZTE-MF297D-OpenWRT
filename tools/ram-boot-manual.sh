#!/bin/sh
# Run only on this port's existing OpenWrt, files under /tmp/mf297d-ram.
set -eu
cd /tmp/mf297d-ram
[ "$(cat /tmp/sysinfo/board_name)" = 'zte,mf297d' ]
case "$(uname -r)" in 6.18.55|6.18.60) ;; *) echo 'Unsupported source kernel'; exit 1;; esac
if command -v nss-status >/dev/null && nss-status -j | grep -q '"state":"active"'; then
 echo 'NSS is active. Disable NSS, reboot once, then retry the RAM step.' >&2
 exit 1
fi
[ "$(cat /sys/kernel/kexec_loaded)" = '0' ]
grep -q 'mf297d.permanent=1' /proc/cmdline
[ "$(cat /sys/devices/system/cpu/online)" = 0 ] || {
 echo 'Prepare a clean single-CPU boot using tools/prepare_ram_boot.py first.' >&2
 exit 1
}
! grep -q '^ath11k ' /proc/modules || {
 echo 'Wi-Fi has already started; use the one-shot clean boot procedure.' >&2
 exit 1
}
grep -Eq 'mf297d.nss_lab=20261114|mf297d.public_ram=1' bootargs.txt
grep -q 'root=/dev/ram0' bootargs.txt
! grep -q 'ubi.mtd=' bootargs.txt
sha256sum -c SHA256SUMS
chmod 500 kexec-aarch64
[ ! -x /etc/init.d/mf297d-wifi ] || /etc/init.d/mf297d-wifi stop
wifi down
ifdown lte >/dev/null 2>&1 || true
if grep -q '^ath11k_ahb ' /proc/modules; then rmmod ath11k_ahb; fi
if grep -q '^ath11k ' /proc/modules; then rmmod ath11k; fi
for r in /sys/class/remoteproc/remoteproc*; do
 [ -r "$r/state" ] || continue
 [ "$(cat "$r/state")" = offline ] || { echo 'Radio processor is not offline; stopping.'; exit 1; }
done
./kexec-aarch64 -c -l Image --dtb=mf297d.dtb --append="$(cat bootargs.txt)"
[ "$(cat /sys/kernel/kexec_loaded)" = 1 ]
sync
mount -o remount,ro /overlay
./kexec-aarch64 -c -e
