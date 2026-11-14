#!/bin/sh
# Run only on this port's existing OpenWrt, files under /tmp/mf297d-ram.
set -eu
cd /tmp/mf297d-ram
[ "$(cat /tmp/sysinfo/board_name)" = 'zte,mf297d' ]
[ "$(uname -r)" = '6.18.55' ] || { echo 'This recipe was tested from native 6.18.55 only.'; exit 1; }
[ "$(cat /sys/kernel/kexec_loaded)" = '0' ]
grep -q 'mf297d.permanent=1' /proc/cmdline
grep -q 'mf297d.nss_lab=20261114' bootargs.txt
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
