#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
cd "$(dirname "$0")"
grep -q 'root=/dev/ram0' /proc/cmdline
grep -q 'mf297d.install_stock=1' /proc/cmdline
grep -q 'mf297d.owner_token=@TOKEN@' /proc/cmdline
[ "$(uname -r)" = 6.18.60 ]
[ "$(cat /tmp/sysinfo/board_name)" = zte,mf297d ]
[ "$(cat /sys/class/mtd/mtd21/name)" = maintenance_storage ]
[ "$(cat /sys/class/mtd/mtd21/size)" = 60817408 ]
[ "$(cat /sys/class/mtd/mtd10/flags)" = 0x400 ]
! grep -q ' ubifs ' /proc/mounts
sha256sum -c SHA256SUMS
sha256sum -c prefix.before.sha256
[ "$(sha256sum /dev/mtd10ro | cut -d' ' -f1)" = @ENV_BEFORE@ ]
[ ! -e /sys/class/ubi/ubi0/mtd_num ]
ubiattach /dev/ubi_ctrl -m 21 -d 0
[ "$(cat /sys/class/ubi/ubi0/volumes_count)" = 4 ]
for pair in '0 kernel' '1 wifi_fw' '2 bt_fw' '3 ubi_rootfs'; do
 set -- $pair
 [ "$(cat "/sys/class/ubi/ubi0_$1/name")" = "$2" ]
done
[ "$(sha256sum /dev/ubi0_0 | cut -d' ' -f1)" = @OLD0_SHA@ ]
[ "$(sha256sum /dev/ubi0_3 | cut -d' ' -f1)" = @OLD3_SHA@ ]
[ "$(sha256sum /dev/ubi0_1 | cut -d' ' -f1)" = @FW1_SHA@ ]
[ "$(sha256sum /dev/ubi0_2 | cut -d' ' -f1)" = @FW2_SHA@ ]
available=$(cat /sys/class/ubi/ubi0/avail_eraseblocks)
reserved=$(cat /sys/class/ubi/ubi0/reserved_for_bad)
extra=0; [ "$reserved" -ge 40 ] || extra=$((40-reserved))
[ $((available-extra)) -ge @RECOVERY_LEBS@ ]
[ ! -e /sys/class/ubi/ubi0_7/name ]
ubimkvol /dev/ubi0 -n 7 -N owrt_recovery -s $((@RECOVERY_LEBS@*126976)) -t static
ubiupdatevol /dev/ubi0_7 recovery.itb
[ "$(sha256sum /dev/ubi0_7 | cut -d' ' -f1)" = @RECOVERY_SHA@ ]
[ "$(sha256sum /dev/ubi0_0 | cut -d' ' -f1)" = @OLD0_SHA@ ]
[ "$(sha256sum /dev/ubi0_3 | cut -d' ' -f1)" = @OLD3_SHA@ ]
[ "$(sha256sum /dev/ubi0_1 | cut -d' ' -f1)" = @FW1_SHA@ ]
[ "$(sha256sum /dev/ubi0_2 | cut -d' ' -f1)" = @FW2_SHA@ ]
sync
ubidetach /dev/ubi_ctrl -d 0
./env-helper --selftest
./env-helper --check
# One fixed owner-bound ENV transition; no stock OS volume removed in phase A.
./env-helper --install
[ "$(sha256sum /dev/mtd10ro | cut -d' ' -f1)" = @ENV_AFTER@ ]
sha256sum -c prefix.after.sha256
sync
echo 'Recovery staged. Next: physical RESET boot and verification. Stock OS has NOT been removed.'
reboot
