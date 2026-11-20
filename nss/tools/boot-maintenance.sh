#!/bin/sh
set -eu
cd "$(dirname "$0")"
router=root@@ROUTER@
ssh "$router" 'test "$(cat /tmp/sysinfo/board_name)" = zte,mf297d'
# NSS cannot be detached while running. Reboot once on the host path first.
if ssh "$router" 'nss-status -j 2>/dev/null' | grep -q '"state":"active"'; then
 ssh "$router" "uci set nss.general.enabled='0'; uci set nss.general.wifi_offload='0'; uci commit nss; sync; reboot" || true
 sleep 10
 count=0
 until ssh -o BatchMode=yes -o ConnectTimeout=3 "$router" true 2>/dev/null; do
  count=$((count+1)); [ "$count" -lt 45 ] || exit 1; sleep 3
 done
 ssh "$router" "uci set nss.general.enabled='1'; uci set nss.general.wifi_offload='1'; uci commit nss"
fi
if ssh "$router" 'nss-status -j 2>/dev/null' | grep -q '"state":"active"'; then
 echo 'NSS remains active; refusing kexec' >&2; exit 1
fi
ssh "$router" 'mkdir -p /tmp/mf297d-install' 
scp -O Image maintenance.dtb bootargs.txt kernel.bin rootfs.bin overlay.ubifs env-helper kexec SHA256SUMS install-from-ram.sh prefix.before.sha256 "$router:/tmp/mf297d-install/"
ssh "$router" 'set -e; cd /tmp/mf297d-install; sha256sum -c SHA256SUMS; chmod 500 kexec env-helper; if [ -x /etc/init.d/mf297d-wifi ]; then /etc/init.d/mf297d-wifi stop; fi; wifi down; ifdown lte || true; for m in ath11k_ahb ath11k; do if grep -q "^$m " /proc/modules; then rmmod "$m"; fi; done; kexec -c -l Image --dtb=maintenance.dtb --append="$(cat bootargs.txt)"; sync; mount -o remount,ro /overlay; kexec -c -e' || true
printf '\nRAM acilisi icin 60 saniye bekleyin. Sonra README NAND adimindaki yeni HostKeyAlias ile baglanin.\n'
